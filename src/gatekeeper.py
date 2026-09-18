"""
project-vault gatekeeper — prototype access-control layer in front of the
hub's `src/server.py`.

Problem this solves: a session started from the hub (this repo's own root)
gets unrestricted cross-project access via server.py's SCOPED/_enforce_scope
mechanism, which only walls things off when launched from inside a specific
project's own directory. This server sits in front of that hub access and
adds a deterministic, auditable policy gate.

This is itself an MCP server (stdio) exposing a subset of server.py's tools
to its caller, while also acting as an MCP *client* of server.py, proxying
allowed calls through to it. Every gated tool call is checked against
policy.yaml BEFORE any upstream call or LLM call happens — a deny short-
circuits both. A small LLM (see MODEL below) is only ever invoked after
that gate passes, to summarize a read or draft content for a write; it has
no ability to influence the allow/deny decision itself, which is why the
policy rules live in policy.yaml (checked in code), not in the LLM's prompt.

create_project is intentionally NOT exposed here — cross-project creation
is out of scope for this prototype, not an oversight.

Run it directly for a quick manual check:
    python src/gatekeeper.py

Or use the MCP inspector:
    mcp dev src/gatekeeper.py

To point a client at it instead of the raw hub server (manual, one-time,
not auto-registered anywhere):
    claude mcp add project-vault-gatekeeper -- python /home/dev/workspace/project-vault-mcp/src/gatekeeper.py
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
POLICY_PATH = REPO_ROOT / "policy.yaml"
AUDIT_LOG_PATH = REPO_ROOT / "gatekeeper_audit.log"
SERVER_SCRIPT = REPO_ROOT / "src" / "server.py"
MODEL = "claude-haiku-4-5-20251001"

mcp = MCPServer("project-vault-gatekeeper")
anthropic_client = AsyncAnthropic()


# --- deterministic policy gate -------------------------------------------

def _load_policy() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def _check_policy(project: str, action: str) -> bool:
    """Pure allow/deny lookup. No I/O beyond reading policy.yaml, no LLM
    involved — this is the actual security boundary."""
    policy = _load_policy()
    default = policy["default"]
    rule = policy.get("projects", {}).get(project, default)
    return rule.get(action, default[action]) == "allow"


def _audit(tool: str, project: str, key: str | None, action: str,
           decision: str, reason: str) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "project": project,
        "key": key,
        "action": action,
        "decision": decision,
        "reason": reason,
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _enforce(tool: str, project: str, key: str | None, action: str,
             reason: str) -> None:
    """Called as the first statement of every gated tool. Raises before
    any upstream proxy call or LLM call is made, so a deny never reaches
    either of them."""
    allowed = _check_policy(project, action)
    _audit(tool, project, key, action, "allow" if allowed else "deny", reason)
    if not allowed:
        raise ToolError(
            f"policy denies {action} access to project {project!r} "
            f"(see policy.yaml) — reason given: {reason!r}"
        )


# --- upstream proxy (lazy-connected, cached) ------------------------------
#
# The upstream stdio_client/ClientSession connection has to live in its own
# long-running task, not be opened-and-left-open inside a per-request tool
# call: anyio's structured concurrency requires a cancel scope to be
# entered and exited within the same task, and MCPServer runs each tool
# call in its own request task. Opening the connection inside a request
# coroutine and caching it past that call's return broke that invariant
# (manifested as "Attempted to exit a cancel scope that isn't the current
# task's current cancel scope" once the first request task completed).
# Fix: a single dedicated background task owns the connection for the
# server's whole lifetime; tool calls just await its readiness and reuse
# the session it publishes.

_upstream: ClientSession | None = None
_upstream_ready = asyncio.Event()
_upstream_task: asyncio.Task | None = None


async def _upstream_manager() -> None:
    global _upstream
    params = StdioServerParameters(
        command="python", args=[str(SERVER_SCRIPT)], cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            _upstream = session
            _upstream_ready.set()
            await asyncio.Event().wait()  # keep the connection open forever


async def _get_upstream() -> ClientSession:
    global _upstream_task
    if _upstream_task is None:
        _upstream_task = asyncio.create_task(_upstream_manager())
    await _upstream_ready.wait()
    assert _upstream is not None
    return _upstream


async def _call_upstream(name: str, args: dict) -> str:
    """For tools that return a single string (get_memory, set_memory)."""
    session = await _get_upstream()
    result = await session.call_tool(name, args)
    text = "".join(block.text for block in result.content if block.type == "text")
    if result.is_error:
        raise ToolError(text)
    return text


async def _call_upstream_list(name: str, args: dict) -> list[str]:
    """For tools that return a list (list_projects, list_memory) — the SDK
    serializes each element as its own TextContent block, not a JSON blob."""
    session = await _get_upstream()
    result = await session.call_tool(name, args)
    if result.is_error:
        text = "".join(block.text for block in result.content if block.type == "text")
        raise ToolError(text)
    return [block.text for block in result.content if block.type == "text"]


# --- LLM helpers (invoked only after the policy gate passes) -------------

async def _llm_summarize(content: str, reason: str) -> str:
    resp = await anthropic_client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": (
                f"Summarize this project memory entry for the stated purpose "
                f"({reason or 'general review'}). Do not invent facts not "
                f"present in it.\n\n{content}"
            ),
        }],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


async def _llm_draft_content(project: str, key: str, instruction: str) -> str:
    resp = await anthropic_client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": (
                f"Draft a project-vault memory entry for project {project!r}, "
                f"key {key!r}, following this repo's format: YAML frontmatter "
                f"with 'key' and 'description' fields, then a Markdown body of "
                f"'- [stated] ...' bullet lines. Base it only on this "
                f"instruction, do not invent unstated facts:\n\n{instruction}"
            ),
        }],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


# --- tools -----------------------------------------------------------------

@mcp.tool()
async def list_projects() -> list[str]:
    """List projects readable under the current policy. Filters the hub's
    full project list down to those with read: allow in policy.yaml —
    denied projects are simply absent, not an error."""
    all_projects = await _call_upstream_list("list_projects", {})
    return [p for p in all_projects if _check_policy(p, "read")]


@mcp.tool()
async def list_memory(project: str, reason: str = "") -> list[str]:
    """List memory keys for a project, subject to policy.yaml's read rule."""
    _enforce("list_memory", project, None, "read", reason)
    return await _call_upstream_list("list_memory", {"project": project})


@mcp.tool()
async def get_memory(key: str, project: str, reason: str = "",
                      summarize: bool = False) -> str:
    """Read one memory file by key for a project, subject to policy.yaml's
    read rule. If summarize=True, the result is passed through a small LLM
    to condense it for the stated `reason` (informational only — never
    part of the allow/deny decision, which already happened)."""
    _enforce("get_memory", project, key, "read", reason)
    content = await _call_upstream("get_memory", {"key": key, "project": project})
    if summarize:
        content = await _llm_summarize(content, reason)
    return content


@mcp.tool()
async def set_memory(key: str, project: str, content: str = "",
                      instruction: str = "", reason: str = "") -> str:
    """Write (create or overwrite) one memory file by key for a project,
    subject to policy.yaml's write rule. Pass `content` verbatim, or leave
    it empty and pass a natural-language `instruction` instead — a small
    LLM drafts frontmatter-consistent content from it, which is then still
    written through the same policy-checked upstream call."""
    _enforce("set_memory", project, key, "write", reason)
    if not content and instruction:
        content = await _llm_draft_content(project, key, instruction)
    if not content:
        raise ToolError("must provide either content or instruction")
    return await _call_upstream(
        "set_memory", {"key": key, "project": project, "content": content}
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
