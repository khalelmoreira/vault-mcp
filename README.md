# project-vault-mcp

A minimal MCP server that fronts a local folder of Markdown files (`vault/`)
as project-specific AI memory, kept separate from any chat app's own
built-in memory. See `CLAUDE.md` for the full rationale and architecture.

## Quickstart

1. Reopen this folder in a Dev Container.
2. Run `claude` — the `project-vault` MCP server is already registered,
   exposing `list_memory`, `get_memory`, `set_memory`.
3. `vault/` is the actual memory. Edit it directly, or let the tools do it.

Claude Code and `gh` auth persist across rebuilds via named volumes.

## Web chat UI

A second, independent MCP client in `web/` — talks to the Anthropic API
directly and reaches `src/server.py` over MCP, same as Claude Code.

1. Set `ANTHROPIC_API_KEY` (env var or `web/backend/.env`, gitignored).
2. `uvicorn web.backend.app:app --reload --port 8000`
3. Open `localhost:8000` and chat.

## Status

Early experiment — see the checklist in `CLAUDE.md`.
