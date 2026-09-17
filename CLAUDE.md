# project-vault-mcp

## What this is

An experiment in separating "project memory" from a chat AI's own built-in
memory. Instead of a chat app storing project-specific facts inside its own
memory system, this repo is a **separate, self-contained vault** that any
MCP-capable client reaches only through an MCP server — never directly.

Motivation: mixing general "about me" memory with project-specific memory in
one store gets messy over time, and it's also not portable across chat
apps/models. A plain local vault + MCP server is portable by construction:
any client that speaks MCP (Claude Desktop, Claude Code, other assistants,
local models with MCP support) can reach it the same way, and nothing about
the vault format is Anthropic-specific.

## Architecture (v0 — current)

```
chat client (any MCP-capable AI) --MCP--> src/server.py --reads/writes--> vault/*.md
```

- `vault/` — the actual memory. Plain Markdown files, one per key, with a
  small YAML frontmatter block (see `vault/example.md`). This is the source
  of truth; everything else is just a way to reach it.
- `src/server.py` — a stdio MCP server exposing three tools: `list_memory`,
  `get_memory`, `set_memory`. It does no filtering or summarizing — it's a
  thin, honest pass-through. That's intentional for v0: prove the plumbing
  (a chat model calling out over MCP to storage it doesn't own) before
  adding any intelligence in front of it.
- No second LLM yet. A later version may put a small model (possibly local)
  in front of the vault to filter/summarize what gets returned, rather than
  handing back raw file contents. Don't add that until v0 is working
  end-to-end — see "Next steps" below.

## Repo layout

```
.devcontainer/devcontainer.json   dev environment: Python + Node + gh CLI, non-root "dev" user, single workspace path
Dockerfile                        Python base image, creates the "dev" user, server dependencies
requirements.txt                  mcp[cli], fastapi/uvicorn/anthropic for web/
.vscode/                          editor settings + recommended extensions
src/server.py                     the MCP server
vault/                            the actual memory files (gitignored by default — see .gitignore)
web/backend/app.py                second MCP client: browser chat UI backend (Anthropic API + MCP stdio client)
web/frontend/index.html           plain HTML/JS chat page, no build step
```

Inside the container, the repo lives at `/home/dev/workspace/project-vault-mcp`
— `workspaceMount`/`workspaceFolder` are set explicitly in devcontainer.json
so VS Code's own default (`/workspaces/<name>`) doesn't create a second,
confusing path alongside it.

Claude Code's internal sandbox (bubblewrap-based on Linux) is disabled via
`~/.claude/settings.json` — it can't create a nested mount namespace inside
this already-unprivileged container, so Bash commands would otherwise fail.
The devcontainer itself is the isolation boundary here.

## Running it

Inside the devcontainer (Claude Code is already installed and this server is
already registered with it via `postCreateCommand`):

```bash
# Sanity-check the server directly
python src/server.py

# Or poke at its tools with a UI instead of a full chat client
mcp dev src/server.py
```

To connect it to a chat client manually (if not using the devcontainer's
auto-registration, or connecting from outside the container):

```bash
claude mcp add project-vault -- python src/server.py
```

## Current status

- [x] Devcontainer + Dockerfile + Claude Code install
- [x] Persistent volume for Claude Code session data across rebuilds
      (`CLAUDE_CONFIG_DIR` set so `~/.claude.json` persists too, not just
      `~/.claude`)
- [x] `gh` CLI installed and its own auth persisted via a separate volume
- [x] Single, unambiguous workspace path — no `/workspace` vs `/workspaces`
      split
- [x] Claude Code's internal sandbox disabled (was causing Bash commands to
      fail — bubblewrap can't nest inside an unprivileged container)
- [x] Minimal MCP server: list/get/set over local .md files
- [x] Actually exercised end-to-end from a real chat session (2026-09-16,
      via Claude Code: list_memory/get_memory/set_memory all confirmed)
- [ ] Decide: does this need a second (filtering/summarizing) LLM in front
      of the vault, or is thin pass-through enough?
- [ ] Decide on write semantics if a second LLM is added (does the main
      chat model ever write directly, or only request writes in natural
      language that the project-side LLM interprets?)
- [ ] Vault format conventions — right now it's just YAML frontmatter +
      bullet lines; align with whatever tagging convention (e.g. `[stated]`)
      turns out to matter once there's real content to manage.
- [x] Second MCP client (browser chat UI in `web/`, calling the Anthropic
      API directly) proves the vault isn't Claude-Code-specific

## Notes for whoever (human or AI) picks this up next

This is explicitly a v0/throwaway-if-needed scaffold to learn MCP hands-on,
not a polished tool. Feel free to restructure once the basic loop (client →
MCP → vault) has actually been exercised and its rough edges are known.
