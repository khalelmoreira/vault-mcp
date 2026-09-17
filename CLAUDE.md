# project-vault-mcp

## What this is

An experiment in separating "project memory" from a chat AI's own built-in
memory. Instead of a chat app storing project-specific facts in its own
memory system, this repo is a **separate, self-contained vault** reached
only through an MCP server — never directly.

Motivation: mixing general "about me" memory with project-specific memory
gets messy over time, and it's not portable across chat apps/models. A
plain local vault + MCP server is portable by construction — any
MCP-capable client can reach it the same way, and nothing about the vault
format is Anthropic-specific.

## Architecture (v0)

```
chat client (any MCP-capable AI) --MCP--> src/server.py --reads/writes--> vaults/<project>/*.md
```

- `vaults/<project>/` — the actual memory, centralized in this repo. One
  subfolder per project (this repo's own memory lives in
  `vaults/project-vault-mcp/`, no special-casing). Projects are just
  folders — create `vaults/project1/` and it's immediately usable, nothing
  to register. Plain Markdown files, one per key, with a small YAML
  frontmatter block (see `vaults/project-vault-mcp/example.md`).
- `src/server.py` — one long-running stdio MCP server exposing
  `list_projects`, `create_project`, `list_memory`, `get_memory`,
  `set_memory`. `list_memory`/`get_memory`/`set_memory` all take an
  optional `project` argument, defaulting to `project-vault-mcp` itself.
  `create_project` makes a new, empty `vaults/<project>/` folder on
  request; project names must start with `project` (e.g. `project-foo`).
  No filtering or summarizing — a thin, honest pass-through. That's
  intentional for v0: prove the plumbing before adding intelligence in
  front of it.
- No second LLM in front of the vault yet — see open questions below.

## Repo layout

```
.devcontainer/devcontainer.json   dev environment
Dockerfile                        Python base image, server dependencies
requirements.txt                  mcp[cli], fastapi/uvicorn/anthropic for web/
src/server.py                     the MCP server
vaults/<project>/                 memory per project (gitignored — see .gitignore)
web/backend/app.py                second MCP client: browser chat UI backend
web/frontend/index.html           plain HTML/JS chat page, no build step
```

## Open questions

- Does this need a second (filtering/summarizing) LLM in front of the
  vault, or is thin pass-through enough?
- If a second LLM is added, what are the write semantics — does the main
  chat model ever write directly, or only request writes in natural
  language that the project-side LLM interprets?
- Vault format conventions — right now it's just YAML frontmatter + bullet
  lines; align with a tagging convention (e.g. `[stated]`) once there's
  real content to manage.

## Notes for whoever (human or AI) picks this up next

This is a v0/throwaway-if-needed scaffold to learn MCP hands-on, not a
polished tool. Feel free to restructure once the basic loop (client → MCP
→ vault) has been exercised and its rough edges are known.
