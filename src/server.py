"""
project-vault MCP server — v0 (simplest possible version)

One long-running server, run from this repo, exposing every project's
memory under `vaults/<project>/*.md` through four MCP tools:
  - list_projects
  - list_memory
  - get_memory
  - set_memory

Written against mcp>=2.0 (MCPServer, not the older FastMCP name/import path
used in pre-2.0 tutorials — the API is otherwise nearly identical).

No filtering/summarizing LLM in front of it yet (see CLAUDE.md for why that's
a deliberate v0 choice, not an oversight). This just proves the plumbing:
a real chat client (Claude Desktop, Claude Code, claude.ai via a remote
variant, etc.) calling out over MCP to read/write files that live entirely
outside its own memory store.

Projects are just subfolders of `vaults/` — nothing to register. Create
`vaults/project1/` yourself (a future tool will do this on request instead)
and it immediately shows up in `list_projects()`; `list_memory`/`get_memory`/
`set_memory` all take an optional `project` argument (defaulting to this
repo's own `project-vault-mcp`) to operate on it.

Run it directly for a quick manual check:
    python src/server.py

Or use the MCP inspector (installed via the `mcp[cli]` extra) to poke at the
tools with a UI instead of a chat client:
    mcp dev src/server.py
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

VAULTS_ROOT = Path(__file__).parent.parent / "vaults"
VAULTS_ROOT.mkdir(exist_ok=True)

DEFAULT_PROJECT = "project-vault-mcp"

mcp = MCPServer("project-vault")


def _safe_name(name: str, what: str) -> str:
    """Refuse anything that would escape vaults/<project>/ (no '..', no
    absolute paths, no subdirectories for this simple version)."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ToolError(f"invalid {what}: {name!r}")
    return name


def _project_dir(project: str) -> Path:
    _safe_name(project, "project")
    project_dir = VAULTS_ROOT / project
    if not project_dir.is_dir():
        raise ToolError(
            f"unknown project {project!r} — call list_projects() to see what "
            f"exists, or create vaults/{project}/ yourself for now"
        )
    return project_dir


def _safe_path(project: str, key: str) -> Path:
    _safe_name(key, "key")
    return _project_dir(project) / f"{key}.md"


@mcp.tool()
def list_projects() -> list[str]:
    """List every project that has a vault (a subfolder under vaults/)."""
    return sorted(p.name for p in VAULTS_ROOT.iterdir() if p.is_dir())


@mcp.tool()
def list_memory(project: str = DEFAULT_PROJECT) -> list[str]:
    """List the memory keys for a project (defaults to project-vault-mcp's
    own memory). Call list_projects() first if unsure what projects exist.
    """
    return sorted(p.stem for p in _project_dir(project).glob("*.md"))


@mcp.tool()
def get_memory(key: str, project: str = DEFAULT_PROJECT) -> str:
    """Read one memory file by key for a project (filename without the .md
    extension; project defaults to project-vault-mcp's own memory).

    Returns its full contents, or an explanatory message if it doesn't
    exist yet — callers should treat a missing key as "nothing stored
    here", not as an error to surface to the user.
    """
    path = _safe_path(project, key)
    if not path.exists():
        return f"(no memory stored under key '{key}' in project '{project}')"
    return path.read_text(encoding="utf-8")


@mcp.tool()
def set_memory(key: str, content: str, project: str = DEFAULT_PROJECT) -> str:
    """Write (create or overwrite) one memory file by key for a project
    (defaults to project-vault-mcp's own memory). The project's vault
    folder must already exist — this does not create new projects.

    This is a full overwrite, not an append or patch — callers should send
    the complete content they want the file to contain.
    """
    path = _safe_path(project, key)
    path.write_text(content, encoding="utf-8")
    return f"saved '{key}' in project '{project}' ({len(content)} chars)"


if __name__ == "__main__":
    mcp.run(transport="stdio")
