# project-vault-mcp

A minimal MCP server that fronts a local folder of Markdown files (`vault/`)
as project-specific AI memory, kept separate from any chat app's own
built-in memory. See `CLAUDE.md` for the full rationale and architecture.

## Quickstart

1. Open this folder in VS Code with the **Dev Containers** extension
   installed, then "Reopen in Container" (or run
   `devcontainer up --workspace-folder .` from the CLI).
2. First boot will: build the image (Python base, a non-root `dev` user),
   add Node and the GitHub CLI via devcontainer features, install the
   Claude Code CLI, and register this server with it
   (`claude mcp add project-vault -- python src/server.py`).
3. The repo lives at a single path inside the container:
   `/home/dev/workspace/project-vault-mcp` — no separate `/workspace` or
   `/workspaces` split.
4. Run `claude` inside the container — the `project-vault` MCP server is
   already available to it, exposing `list_memory`, `get_memory`, and
   `set_memory`.
5. Everything under `vault/` is your actual memory. Edit it directly, or let
   the MCP tools do it.

Claude Code's login/session state persists across rebuilds via a named
volume (`project-vault-mcp-claude-config`), and `gh` auth persists the same
way via `project-vault-mcp-gh-config`. Claude Code's own internal sandbox is
disabled by default here (see `CLAUDE.md`) — the devcontainer is already the
isolation boundary, and its sandbox can't nest inside an unprivileged
container anyway.

## Status

Early experiment — see the checklist in `CLAUDE.md`.
