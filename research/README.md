# enact-tools research

Analysis inputs for the tool & hook surface review, and the notes behind them.

## Layout

```
enact-tools/
├── enact-tools-surface-review.html   ← the deliverable (open in a browser)
├── build_report.py                   ← parses the CSV, joins verdicts → data.json
├── render_report.py                  ← renders data.json → the HTML
├── data.json                         ← generated intermediate (109 tools, 44 proposals, 25 hook rows,
│                                       9 host layers, 6 portability layers, 35 jcode tools, 8 jcode hooks)
├── zeroclaw-tools-operations.csv     ← the baseline inventory (244 operations)
└── research/
    ├── oh-my-pi/                     ← local clone of github.com/can1357/oh-my-pi
    ├── lean-ctx/                     ← local clone of github.com/yvgude/lean-ctx
    └── jcode/                        ← local clone of github.com/1jehuang/jcode
```

## The clones are local-only

Those three directories are **git-ignored**. They are other people's repositories —
vendoring them would put ~800 MB of third-party code into this repo and make the
review impossible to re-pin. Fetch them yourself:

```sh
git clone https://github.com/can1357/oh-my-pi.git research/oh-my-pi
git clone https://github.com/yvgude/lean-ctx.git research/lean-ctx
git clone https://github.com/1jehuang/jcode.git research/jcode
```

The commits the review was written against:

| clone | commit | date |
|---|---|---|
| `oh-my-pi` | `bcd5b0b996e0f4a107f51cb398a6492ffb7d44b9` | 2026-11-12 |
| `lean-ctx` | `013ddb1cce8948773c183e47c4a0d258a82c8599` | 2026-11-11 |
| `jcode` | `450117cb46eb38e700905d3c8c83bac985f78ad5` | 2026-11-12 |

`build_report.py` reads their contents only when they are present; the review itself
is generated from the CSV, so it regenerates without them.

## Regenerating

```sh
python3 build_report.py     # CSV + verdicts  → data.json
python3 render_report.py    # data.json       → enact-tools-surface-review.html
```

`build_report.py` reads the disabled-tool flags from the enact-agent overlay's
`zeroclaw-tools-operations.csv`, which carries the real `compiled_in_enact` column.
The workspace copy of the CSV has that column rewritten to `TRUE` on every row, so the
disabled set (13 tools / 48 operations) is only visible in the overlay copy.

That overlay lives in the sibling `enact-agent` checkout. The script finds it via
`ENACT_AGENT_DIR`, or by looking for `enact-agent` next to this repository:

```sh
ENACT_AGENT_DIR=/path/to/enact-agent python3 build_report.py
```


## Key source paths

| Project | What to read |
|---|---|
| enact-agent | `crates/zeroclaw-api/src/hook.rs` · `crates/zeroclaw-runtime/src/hooks/` · `crates/zeroclaw-config/src/builtin_tools.rs` · `crates/zeroclaw-config/src/schema.rs` (`HooksConfig`) · `crates/zeroclaw-tools/src/inventory.rs` · `crates/zeroclaw-tools/src/mcp_*.rs` (client only — no server) · `docs/book/src/developing/tool-inventory.md` |
| oh-my-pi | `packages/coding-agent/src/tools/builtin-names.ts` · `packages/coding-agent/src/tools/index.ts` · `packages/coding-agent/src/tools/essential-tools.ts` · `packages/coding-agent/src/extensibility/extensions/types.ts` · `docs/hooks.md` · `README.md` |
| lean-ctx | `rust/crates/lean-ctx-server/src/tools/registered/` · `rust/src/tool_defs/mod.rs` · `rust/crates/lean-ctx-hooks/src/hook_handlers/` · `docs/tool-consolidation-plan.md` · `docs/PROTECTED-HOOKS.md` · `CONTRACTS.md` |
| jcode | `crates/jcode-harness-api/src/requests.rs` (`ConfigureTools` — external tool injection) · `crates/jcode-harness-api-server/src/` · `crates/jcode-app-core/src/tool/sdk.rs` (custom-tool execution adapter) · `crates/jcode-app-core/src/tool/mod.rs` (registry) · `crates/jcode-base/src/mcp/protocol.rs` (config interop) · `crates/jcode-app-core/src/agent/turn_execution.rs` (tool-lock + one-shot rebuild) · `docs/HOOKS.md` · `docs/SWARM_ARCHITECTURE.md` · `docs/MEMORY_ARCHITECTURE.md` |

## Headline numbers

- enact-agent: 109 built-in tools / 244 operations — Tier 1 Core 11, Tier 2 Host 67, Tier 3 Optional 31
- Disabled in the Enact build: 13 tools / 48 operations (all `OptIn` adapters)
- oh-my-pi: 30 built-ins + 3 hidden; 13 `essential` in the schema, the rest behind `xd://`
- lean-ctx: 51 public MCP tools, 12-tool lazy core; consolidated 82 → 35 in 3.11.5
- jcode: 34 registered built-ins; 8 external-program hooks; Harness API v1.11 (NDJSON over Unix socket)
- Proposed: 109 → 83 tools by sibling-family merge, zero operations lost

## The portability answer (one tool system across Codex + Claude Code)

1. **Tools → MCP server.** MCP is the only substrate every host speaks. Claude Code can also
   *serve* its own tools (`claude mcp serve`); **Codex cannot** — so being an MCP server is the
   only way to give Codex a tool set you control. enact-agent was an MCP **client only**
   (no `ServerHandler`, no `rmcp` dep) — that was the single highest-leverage gap, and it is
   now closed: the Enact overlay ships `enact-agent mcp serve` (stdio + HTTP).
2. **Tools, take two → tool-injection API.** jcode's Harness API exposes
   `ConfigureTools { enabled, disabled, custom }`: an external client registers tool
   implementations, the runtime routes the call back down that client's connection, and the
   custom tool stays an "execution adapter only" so hooks/telemetry/permissions are unchanged.
3. **Schema budget → search + call, not N schemas** (jcode 32 refs / 6 000-token budget;
   Claude Code MCP Tool Search; oh-my-pi `xd://`).
4. **Behaviour → per-host hook dialects** (lean-ctx: 17 actions × 11 hosts).
5. **Instructions → AGENTS.md + SKILL.md** (Codex native; Claude Code v2.1.277+ or `@path` import).
6. **Policy → degrade to each host's own rules** (Codex `.rules`; Claude Code permissions).
