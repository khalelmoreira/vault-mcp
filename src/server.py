"""
project-vault MCP server — v0 (simplest possible version)

One long-running server, run from this repo, exposing every project's
memory under `vaults/<project>/*.md` through five MCP tools:
  - list_projects
  - create_project
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

Projects are just subfolders of `vaults/` — nothing to register. From the
hub, call `create_project("project1")` (names must start with 'project')
and it immediately shows up in `list_projects()`; `list_memory`/
`get_memory`/`set_memory` all take an optional `project` argument to
operate on it.

The project is inferred from the server's cwd at launch, not hardcoded
(see `_infer_default_project()`), and it's a hard wall, not just a
default: launch it from inside `~/workspace/project1/` and the session is
SCOPED to `project1` — every tool refuses to touch any other project's
vault, and `list_projects()`/`create_project()` are locked down to just
that project (see `SCOPED` / `_enforce_scope()`). Launch it from anywhere
without a matching vault (including this repo itself) and it's the hub,
`project-vault-mcp`, with full cross-project access.

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

HUB_PROJECT = "project-vault-mcp"


def _infer_default_project() -> str:
    """Default project is inferred from the directory the server is
    launched from (its cwd), not hardcoded — this is what gives each
    project its own scope without asking the AI to name it every time.

    Launch the server from inside `~/workspace/project-foo/` and its
    memory calls default to `project-foo`'s vault. Launch it from
    anywhere without a matching vault (e.g. this repo itself) and it
    falls back to the hub project, `project-vault-mcp`, where
    cross-project reads via list_projects()/list_memory(project=...)
    make sense.
    """
    cwd_name = Path.cwd().name
    if (VAULTS_ROOT / cwd_name).is_dir():
        return cwd_name
    return HUB_PROJECT


DEFAULT_PROJECT = _infer_default_project()

# Hard isolation, not just a default: when the server is launched from
# inside a specific project's directory, it is SCOPED to that project and
# every tool is walled off from the rest of vaults/ — no listing, reading,
# or writing another project's memory, and no creating new projects. Only
# when launched from the hub (no matching project dir, e.g. this repo
# itself) does it see everything.
SCOPED = DEFAULT_PROJECT != HUB_PROJECT

mcp = MCPServer("project-vault")


def _enforce_scope(project: str) -> None:
    if SCOPED and project != DEFAULT_PROJECT:
        raise ToolError(
            f"this server instance is scoped to project {DEFAULT_PROJECT!r} "
            f"(launched from its directory) and cannot access {project!r} "
            f"or any other project — start a session from the hub "
            f"({HUB_PROJECT}) for cross-project access"
        )


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
    """List every project that has a vault (a subfolder under vaults/).

    If this server instance is scoped to a single project (launched from
    that project's own directory), returns only that one project — it
    cannot see or list any other vault.
    """
    if SCOPED:
        return [DEFAULT_PROJECT]
    return sorted(p.name for p in VAULTS_ROOT.iterdir() if p.is_dir())


@mcp.tool()
def create_project(project: str) -> str:
    """Create a new, empty vault folder under vaults/ for a project.

    Project names must start with 'project' (e.g. 'project-foo') and must
    not already exist. Only available from the hub (no other project's
    memory should be reachable, including by creating one, from a
    scoped session). Returns a confirmation message.
    """
    if SCOPED:
        raise ToolError(
            f"this server instance is scoped to project {DEFAULT_PROJECT!r} "
            f"and cannot create other projects — start a session from the "
            f"hub ({HUB_PROJECT}) to create new projects"
        )
    _safe_name(project, "project")
    if not project.startswith("project"):
        raise ToolError(
            f"invalid project name {project!r}: project names must start "
            f"with 'project'"
        )
    project_dir = VAULTS_ROOT / project
    if project_dir.exists():
        raise ToolError(f"project {project!r} already exists")
    project_dir.mkdir(parents=True)
    return f"created project '{project}' (vaults/{project}/)"


@mcp.tool()
def list_memory(project: str = DEFAULT_PROJECT) -> list[str]:
    """List the memory keys for a project (defaults to the project inferred
    from where this server was launched — see DEFAULT_PROJECT). Call
    list_projects() first if unsure what projects exist.
    """
    _enforce_scope(project)
    return sorted(p.stem for p in _project_dir(project).glob("*.md"))


@mcp.tool()
def get_memory(key: str, project: str = DEFAULT_PROJECT) -> str:
    """Read one memory file by key for a project (filename without the .md
    extension; project defaults to the one inferred from where this server
    was launched — see DEFAULT_PROJECT).

    Returns its full contents, or an explanatory message if it doesn't
    exist yet — callers should treat a missing key as "nothing stored
    here", not as an error to surface to the user.
    """
    _enforce_scope(project)
    path = _safe_path(project, key)
    if not path.exists():
        return f"(no memory stored under key '{key}' in project '{project}')"
    return path.read_text(encoding="utf-8")


@mcp.tool()
def set_memory(key: str, content: str, project: str = DEFAULT_PROJECT) -> str:
    """Write (create or overwrite) one memory file by key for a project
    (defaults to the project inferred from where this server was launched
    — see DEFAULT_PROJECT). The project's vault folder must already
    exist — this does not create new projects (use create_project()).

    This is a full overwrite, not an append or patch — callers should send
    the complete content they want the file to contain.
    """
    _enforce_scope(project)
    path = _safe_path(project, key)
    path.write_text(content, encoding="utf-8")
    return f"saved '{key}' in project '{project}' ({len(content)} chars)"


if __name__ == "__main__":
    mcp.run(transport="stdio")
