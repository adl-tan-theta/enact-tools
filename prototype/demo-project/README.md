# enact-bridge demo project

This directory is wired to **enact-bridge**, an MCP server that publishes
enact-agent's tool surface as one canonical registry for both Codex CLI and
Claude Code.

Try it:

    cd demo-project
    codex "list the canonical tools you have"
    claude "which tools can you use?"

## What lives here

Only this README is tracked. Everything else in this directory is **written by
the installer** and is git-ignored:

| path | written by |
|---|---|
| `.mcp.json` | `bridge.py install --host claude-code` |
| `.claude/settings.json` | `bridge.py install --host claude-code` |
| `.claude/skills/enact-bridge/SKILL.md` | `bridge.py install --host claude-code` |
| `.codex/config.toml` | `bridge.py install --host codex` |
| `.codex/skills/enact-bridge/SKILL.md` | `bridge.py install --host codex` |
| `AGENTS.md` | both installers (the shared instruction block) |
| `CLAUDE.md` | both installers (Claude Code does not read `AGENTS.md` on its own) |
| `memory/`, `state/` | the demo project's own runtime state |

They are ignored because the MCP configs embed **absolute paths** to this
machine's interpreter and to `serve.py` — meaningless in another checkout, and
noise in a diff.

## Recreating the wiring

```sh
cd ../..
python3 bridge.py install --host both --scope project --project demo-project
```

Every file the installer writes is marker-guarded (`<!-- enact-bridge:begin -->`),
so uninstalling removes exactly what was installed and nothing else:

```sh
python3 bridge.py uninstall --host both --scope project --project demo-project
```
