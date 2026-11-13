# enact-bridge — one canonical tool registry for Codex CLI and Claude Code

A working prototype that exposes **enact-agent's tool surface as a single canonical
registry** and hands that same registry to both Codex CLI and Claude Code.

```
enact-agent inventory (109 tools / 244 operations)
            │
            │  tools/generate_registry.py  +  tools/merge_map.py
            ▼
  canonical registry (83 tools / 244 operations, zero lost)
            │
            │  MCP server over stdio (JSON-RPC 2.0, protocol 2024-11-05)
            ▼
     ┌──────────────┴──────────────┐
     ▼                             ▼
  Codex CLI                   Claude Code
  ~/.codex/config.toml        ~/.claude.json / .mcp.json
  ~/.codex/rules/*.rules       .claude/settings.json
  AGENTS.md                   AGENTS.md + CLAUDE.md
```

Both hosts call the **same** registry and get **the same** answers. Verified end to end
against the real CLIs on this machine — see [Verification](#verification).

---

## Why this shape

The portable substrate between coding agents is not "a tool API". It is:

1. **MCP** — the only wire format both hosts speak. (Codex CLI has no server mode,
   so being an MCP *server* is the only way to hand Codex a tool set at all.)
2. **`AGENTS.md` / `SKILL.md`** — one instruction file both hosts can read.
3. **Per-host hook dialects** — Codex `~/.codex/rules/*.rules` (Starlark execpolicy),
   Claude Code `permissions.*` in `settings.json`.
4. **Per-host policy** — each host keeps its own approval model; the bridge mirrors it
   instead of inventing a new one.

That is the conclusion the earlier research (oh-my-pi, lean-ctx, jcode) pointed to, and
this prototype is that conclusion, running.

---

## Layout

```
prototype/
├── serve.py                     MCP stdio entry point (what hosts spawn)
├── bridge.py                    CLI: show / search / call / install / policy / verify
├── tools/
│   ├── merge_map.py             the 10 sibling families (109 → 83)
│   └── generate_registry.py     inventory + merge map → canonical registry
├── data/
│   └── registry.generated.json  the canonical registry (generated, never hand-edited)
├── enact_bridge/
│   ├── model.py                 Registry / Tool / Operation
│   ├── aliases.py               host vocabularies → canonical names
│   ├── policy.py                reads each host's own policy, mirrors its decisions
│   ├── discovery.py             search over the registry (the lazy tool surface)
│   ├── executor.py              real execution, sandboxed to a workspace
│   ├── server.py                MCP stdio server
│   ├── adapters.py              installers for Claude Code and Codex
│   └── cli.py                   command line
├── tests/                       68 tests
└── demo-project/                a project already wired to the bridge
```

Pure Python 3.11+ standard library. **Zero dependencies.** `tomllib` is stdlib.

---

## Quick start

```sh
cd prototype

python3 tools/generate_registry.py     # rebuild the registry from enact-agent's inventory
python3 bridge.py show                 # 83 canonical tools, 244 operations
python3 bridge.py search "read a file" # find a tool by intent
python3 bridge.py call file_read --args '{"path": "README.md"}'
python3 bridge.py verify               # full self-check
```

Install into a host:

```sh
python3 bridge.py install --host claude-code --scope project --project .
python3 bridge.py install --host codex        --scope user    --project .
python3 bridge.py uninstall --host both --scope project --project .
```

`--scope user` for Claude Code shells out to `claude mcp add`; for Codex it shells out
to `codex mcp add`. Both preserve the rest of your config. `--dry-run` shows exactly
what would be written without writing it.

---

## The canonical registry

### It is generated, not hand-written

`tools/generate_registry.py` reads two real files and writes the registry:

| source | what it gives |
|---|---|
| `enact-tools/zeroclaw-tools-operations.csv` | 109 tools, 244 operations, tiers, compilation mode |
| `enact-agent/overlays/enact/zeroclaw-tools-operations.csv` | the real `compiled_in_enact` flags |

Two traps in that data, both handled:

**Trap 1 — the workspace CSV lies about what is compiled in.** Its last column
`compiled_in_enact_all_tools` is `TRUE` on *every one of the 244 rows*. The real flag
only exists in the Enact overlay CSV, where a compiled-out tool is written with a
leading `#` (`#notion`, `#jira`, `#codex_cli`, …). Reading the workspace column gives
you 0 disabled tools; reading the overlay gives the correct **13 tools / 48 operations**.

**Trap 2 — sibling families share operation names.** `cron_add.add` and `schedule.add`
are both `add`. Collapsing on the bare operation name silently drops operations — the
first version of this generator lost exactly 6 of them. The fix derives a unique action
name per operation and keeps the source pair verbatim in `op_map`:

```
cron_add.add            → action "cron_add"
schedule.add            → action "schedule_add"
sop_workshop.list       → action "sop_workshop_list"
model_routing_config.get→ action "model_routing_config_get"
```

A name that is unique inside its family stays bare (`cron.run`, `sop.approve`), so the
public surface stays readable.

**Result:** 109 → 83 canonical tools, **244 operations preserved exactly** — every
`(tool, operation)` pair in the source inventory is reachable exactly once. There is a
test that asserts the bijection against the CSV, not a count.

### Consolidation map

10 sibling families collapse into one canonical tool with a typed `action` enum:

| canonical | members | ops |
|---|---|---|
| `cron` | `cron_add` `cron_list` `cron_remove` `cron_update` `cron_run` `cron_runs` `schedule` | 15 |
| `sop` | `sop_list` `sop_execute` `sop_advance` `sop_approve` `sop_status` `sop_workshop` | 13 |
| `model` | `model_switch` `model_routing_config` | 11 |
| `cloud` | `cloud_ops` `cloud_patterns` | 6 |
| `memory` | `memory_store` `memory_recall` `memory_forget` `memory_export` `memory_purge` | 5 |
| `a2a` | `a2a_discover` `a2a_send` `a2a_get_task` `a2a_cancel` | 4 |
| `sessions` | `sessions_current` `sessions_list` `sessions_history` `sessions_send` | 4 |
| `mcp` | `mcp_resources` `mcp_prompts` | 4 |
| `file_uploads` | `file_upload` `file_upload_bundle` | 2 |
| `email` | `email_search` `email_read` | 2 |

A merged family takes its **most restrictive** member's tier and compilation mode, so
folding never widens a tool's exposure. Every merged tool records `merged_from`, and
every action records the enact-agent operation it came from.

---

## The tool surface: search + call

Advertising 70 schemas eagerly would blow up the host's context. The default surface is
two tools:

| tool | purpose |
|---|---|
| `mcp_search` | find canonical tools by intent (`{"query": "read a file", "limit": 8}`) |
| `mcp_call` | run one (`{"tool": "file_read", "action": "...", "arguments": {...}}`) |

This follows jcode (32 tool references / 6000-token search budget), Claude Code's MCP
Tool Search, and oh-my-pi's `xd://` pattern. The budget constants live in
`discovery.py`.

`--expose full` advertises all 70 enabled canonical tools with their real schemas
instead, for hosts that prefer a flat surface.

Search is token-aware: stop words and one-character words are dropped, a name hit beats
a description hit, a host-vocabulary hit beats both, and the result is capped by an
estimated token budget.

---

## Host wiring

### Claude Code

| file | what the installer writes |
|---|---|
| `.mcp.json` | `mcpServers.enact` → `{command, args, env}` (project scope; other servers preserved) |
| `~/.claude.json` | the same server at user scope, via `claude mcp add --scope user` |
| `AGENTS.md` | the shared instruction block, marker-guarded |
| `CLAUDE.md` | `@AGENTS.md` — Claude Code does not read `AGENTS.md` on its own |
| `.claude/settings.json` | `permissions.allow: ["mcp__enact__mcp_search", "mcp__enact__mcp_call"]` |

### Codex CLI

| file | what the installer writes |
|---|---|
| `~/.codex/config.toml` | `[mcp_servers.enact]` via `codex mcp add` (user scope) |
| `.codex/config.toml` | the same table, project scope |
| `~/.codex/rules/enact.rules` | execpolicy `prefix_rule(pattern=[...], decision="allow"/"forbidden")` |
| `AGENTS.md` | the same shared instruction block |

**Two format details that are easy to get wrong, and were:**

- Codex execpolicy rule files are parsed as **Starlark**, not as text. `<!-- comment -->`
  is a parse error that breaks the whole Codex session with
  `Error loading rules: starlark error: unexpected symbol '<'`. The generated rules file
  uses `#` comments and valid `prefix_rule(...)` expressions only. There is a test that
  asserts every non-comment line is a Starlark expression.
- A TOML file cannot declare the same table twice, so the installer removes an existing
  `[mcp_servers.enact]` table before writing its own. Installing three times leaves one
  table. There is a test for that too.

**Known limitation:** on this machine `codex mcp list` does not surface a project-scoped
`.codex/config.toml` MCP server, so Codex should be installed at `--scope user`. The
project file is still written (and validated as TOML) for builds that do read it.

---

## The policy layer

The bridge does **not** invent a policy language. It reads what each host already
declared and answers the same question the host would answer.

**Claude Code** — `~/.claude/settings.json`:

```json
{ "permissions": { "allow": [], "deny": ["Grep", "Glob"], "defaultMode": "auto" } }
```

Rules are `Tool(specifier)`, and MCP tools are `mcp__<server>__<tool>`. The bridge
resolves a rule's host tool name onto the canonical registry name, so a rule written in
the host's vocabulary governs the canonical tool. With the deny list above, on this
machine:

```
content_search   blocked by claude-code:permissions.deny: denied by rule 'Grep'
glob_search      blocked by claude-code:permissions.deny: denied by rule 'Glob'
file_read        allowed
```

A Claude Code rule about `Grep` genuinely stops the bridge's `content_search`. That is
the point of one canonical registry: the host's policy cannot be side-stepped by
reaching the same capability under another name.

**Codex CLI** — `~/.codex/rules/*.rules`:

```
prefix_rule(pattern = ["git", "status"], decision = "allow")
prefix_rule(pattern = ["rm", "-rf"], decision = "forbidden")
```

The bridge matches the longest matching prefix against the `shell` tool's argv and
mirrors the decision. Codex execpolicy governs shell commands, not MCP tool calls, so
non-shell canonical tools are reported as `allow` — with the reason stated rather than
implied.

Only `forbidden` is enforced by the bridge. `prompt` is left to the host, because
Claude Code and Codex already run their own approval dialogs and double-prompting
would be worse than useless.

---

## Execution

Real execution is implemented for the tools that are useful without an agent runtime:

| tool | notes |
|---|---|
| `shell` | runs in the workspace, scrubbed environment, configurable timeout |
| `file_read` | line numbers, offset and limit |
| `file_write` | creates parent directories |
| `file_edit` | exact-string replace, reports the occurrence count |
| `glob_search` | glob over the workspace, skips `.git` / `node_modules` |
| `content_search` | regex over file contents, bounded result count |
| `calculator` | whitelisted arithmetic only |
| `git_operations` | read-only slice: `status log diff list branch show` |

**Sandboxing:** every path is resolved against the workspace root and rejected if it
escapes — including `../../etc/passwd` and absolute paths outside the root.

Every other tool returns an explicit, structured result naming the exact enact-agent
operation it stands for, rather than silently doing nothing:

```
web_fetch.fetch is not implemented in the prototype. It maps to enact-agent's
web_fetch.fetch (crates/zeroclaw-runtime/src/tools/web_fetch.rs).
Run enact-agent for the full implementation.
```

This is the honest limit of the prototype: the **registry** is complete (all 244
operations are addressable), the **execution** is not.

---

## Verification

Everything below was run against the real CLIs on this machine.

**Registry integrity** (`python3 bridge.py verify`):

```
PASS  registry loads                   83 canonical tools
PASS  operation count preserved        244 operations (source inventory has 244)
PASS  consolidation ratio              109 source tools -> 83 canonical
PASS  compiled-out tools flagged       13 disabled
PASS  no operation lost or duplicated  244 reachable pairs
PASS  MCP initialize                   2024-11-05
PASS  MCP tools/list                   mcp_search, mcp_call
PASS  MCP mcp_search
PASS  MCP write then read              1	hello
PASS  claude-code CLI present          ~/.local/bin/claude
PASS  codex CLI present                /opt/homebrew/bin/codex
```

**Test suite:** `python3 -m unittest discover -s tests -t .` → **68 tests, OK**.

**Claude Code, real session:**

```
$ claude mcp get enact
  Scope: User config (available in all your projects)
  Status: ✔ Connected

$ claude -p "Call the MCP tool mcp__enact__mcp_search with query 'read a file' ..."
file_read
read_skill
deliver_file

$ claude -p "Call mcp__enact__mcp_call with tool='file_read' ..."
# enact-bridge demo project
```

**Codex CLI, real session:**

```
$ codex mcp get enact
  enabled: true
  transport: stdio

$ codex exec "Use the MCP server named 'enact'. Call its mcp_search tool ..."
mcp: enact/mcp_search started
mcp: enact/mcp_search (completed)
file_read
read_skill
deliver_file

$ codex exec "Call its mcp_call tool with tool='file_read' ..."
mcp: enact/mcp_call started
mcp: enact/mcp_call (completed)
# enact-bridge demo project
```

Both hosts returned **identical** results for identical queries — the point of the
exercise.

---

## The native server (Phase 0, landed in enact-agent)

The port path has been taken. `enact-agent` now ships the MCP server itself, as a
fork-only module the overlay owns:

```
enact-agent/overlays/enact/native/mcp-server/src/
├── mod.rs               module root
├── protocol.rs          JSON-RPC / MCP envelope (reuses zeroclaw_tools::mcp_protocol)
├── surface.rs           the search + call surface over the real tool registry
├── server.rs            dispatch and the stdio loop
├── bootstrap.rs         config → risk profile → security policy → tool registry
├── cli.rs               `enact-agent mcp serve` / `enact-agent mcp hosts`
└── config_discovery.rs  reads the hosts' own MCP config, jcode precedence
```

`overlays/enact/build.py` copies it into the prepared source as `src/mcp_server/`
and patches `src/main.rs` with two checked anchors (the module declaration and
the `Commands::Mcp` variant). **No tracked `src/` or `crates/` Rust changes, and no
`Cargo.toml` / `Cargo.lock` churn** — every dependency it uses is already a
dependency of the root package.

What it does:

- **Serves the real registry.** `bootstrap.rs` loads the config, resolves the
  agent's risk profile, builds the security policy, constructs the runtime and
  memory, and calls `all_tools_with_runtime` — the same factory a live agent turn
  uses. It then routes the result through `ScopedToolRegistry::assemble`, because
  `AllToolsResult`'s tool vectors are **unfiltered by contract**; exposing them
  directly would hand a host tools the agent may not use.
- **Falls back safely.** With no configured agent it uses the default risk
  profile (supervised, workspace-only, high-risk commands blocked) with the
  requested workspace as the jail root, and says so on stderr.
- **Reads the hosts' MCP config.** `config_discovery.rs` reads
  `~/.codex/config.toml`, `~/.claude.json` and `<project>/.mcp.json`, and applies
  the precedence the hosts apply — with the tie-break that matters: a *runnable*
  server wins over a lower-precedence broken one.
  `enact-agent mcp hosts` prints the result.

Commands:

```sh
enact-agent mcp serve [--agent A] [--workspace DIR] [--expose-full] [--connect-mcp]
enact-agent mcp hosts [--project DIR] [--json]
```

### The division of labour

| | owner | why |
|---|---|---|
| the MCP server and the tool registry | **enact-agent** (native) | it needs the real tool implementations and the real policy gate |
| host installation, policy mirroring, canonical registry generation | **this bridge** | host-facing, not product-facing, and it must work for a stock upstream build too |

The bridge can point a host at either server:

```sh
python3 bridge.py install --host codex --server native   # enact-agent mcp serve
python3 bridge.py install --host codex --server python   # this prototype
```

---

## Cleanup

The prototype left these on this machine (all reversible):

```sh
claude mcp remove enact -s user
codex  mcp remove enact
rm ~/.codex/rules/enact.rules
```

Project-scoped artifacts (`demo-project/.mcp.json`, `AGENTS.md`, `CLAUDE.md`,
`.claude/settings.json`, `.codex/config.toml`) are removed by:

```sh
python3 bridge.py uninstall --host both --scope project --project prototype/demo-project
```

Everything the installer writes is marker-guarded, so uninstalling removes exactly what
was installed and nothing else.
