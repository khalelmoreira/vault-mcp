# project-vault-mcp

A minimal MCP server that fronts local folders of Markdown files
(`vaults/<project>/`) as project-specific AI memory, kept separate from any
chat app's own built-in memory. See `CLAUDE.md` for the full rationale and
architecture.

## Quickstart

1. Reopen this folder in a Dev Container.
2. Run `claude` — the `project-vault` MCP server is already registered,
   exposing `list_projects`, `list_memory`, `get_memory`, `set_memory`.
3. `vaults/project-vault-mcp/` is this repo's own memory (the default
   project when none is specified). Edit it directly, or let the tools do
   it.

Claude Code and `gh` auth persist across rebuilds via named volumes, see `CONTAINER.md`.

## Web chat UI

A second, independent MCP client in `web/` — talks to the Anthropic API
directly and reaches `src/server.py` over MCP, same as Claude Code.

1. `cp web/backend/.env.example web/backend/.env` and fill in your key.
2. `uvicorn web.backend.app:app --reload --port 8000`
3. Open `localhost:8000` and chat.

## Adding a project

Vaults are just folders — `mkdir vaults/project1/` and it's immediately
usable: `list_projects()` picks it up, and `list_memory`/`get_memory`/
`set_memory` all take an optional `project` argument to target it. The
server itself only ever runs from this repo; there's no per-project
registration step.

## Status

Early experiment — see the checklist in `CLAUDE.md`.
