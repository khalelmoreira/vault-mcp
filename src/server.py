"""
project-vault MCP server — v0 (simplest possible version)

Exposes the local `vault/` folder of .md files as three MCP tools:
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

Run it directly for a quick manual check:
    python src/server.py

Or use the MCP inspector (installed via the `mcp[cli]` extra) to poke at the
tools with a UI instead of a chat client:
    mcp dev src/server.py
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

VAULT_DIR = Path(__file__).parent.parent / "vault"
VAULT_DIR.mkdir(exist_ok=True)

mcp = MCPServer("project-vault")


def _safe_path(key: str) -> Path:
    """Resolve a memory key to a path inside the vault, refusing anything
    that would escape it (no '..', no absolute paths, no subdirectories for
    this simple version)."""
    if not key or "/" in key or "\\" in key or key.startswith("."):
        raise ValueError(f"invalid key: {key!r}")
    return VAULT_DIR / f"{key}.md"


@mcp.tool()
def list_memory() -> list[str]:
    """List the keys of every memory file currently in the vault."""
    return sorted(p.stem for p in VAULT_DIR.glob("*.md"))


@mcp.tool()
def get_memory(key: str) -> str:
    """Read one memory file by key (filename without the .md extension).

    Returns its full contents, or an explanatory message if it doesn't
    exist yet — callers should treat a missing key as "nothing stored
    here", not as an error to surface to the user.
    """
    path = _safe_path(key)
    if not path.exists():
        return f"(no memory stored under key '{key}')"
    return path.read_text(encoding="utf-8")


@mcp.tool()
def set_memory(key: str, content: str) -> str:
    """Write (create or overwrite) one memory file by key.

    This is a full overwrite, not an append or patch — callers should send
    the complete content they want the file to contain.
    """
    path = _safe_path(key)
    path.write_text(content, encoding="utf-8")
    return f"saved '{key}' ({len(content)} chars)"


if __name__ == "__main__":
    mcp.run(transport="stdio")
