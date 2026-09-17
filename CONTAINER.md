# Devcontainer setup

Notes on how the dev container is built, for anyone changing it.

## Image

`Dockerfile` — Python 3.12 slim base, non-root `dev` user with passwordless
sudo. `devcontainer.json` adds Node 20 and the GitHub CLI as features (for
Claude Code and `gh`), then `postCreateCommand` installs Claude Code itself
and registers `project-vault` with it (`claude mcp add project-vault --
python src/server.py`).

## Workspace path

`workspaceMount`/`workspaceFolder` pin the repo to
`/home/dev/workspace/project-vault-mcp`.

## Persistence

Two named volumes survive rebuilds:

- `project-vault-mcp-claude-config` → `/home/dev/.claude` (Claude Code
  login/session state; `CLAUDE_CONFIG_DIR` points here so `~/.claude.json`
  persists too)
- `project-vault-mcp-gh-config` → `/home/dev/.config/gh` (`gh` auth)

## Sandbox

Claude Code's own per-command sandbox (`bubblewrap`) can't nest inside an
already-unprivileged devcontainer, so `postCreateCommand` disables it via
`~/.claude/settings.json`. The devcontainer itself is the isolation
boundary.

## Ports

`forwardPorts: [8000]` — the web chat UI (`web/`), forwarded automatically
when running `uvicorn`.
