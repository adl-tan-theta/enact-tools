# enact-tools

The research, the review and the working prototype behind **Enact's tool and hook
surface** — how `enact-agent`'s tool inventory was reviewed against three comparable
agents, what was consolidated, and the bridge that hands one canonical registry to
every coding host.

This repository is the **workspace** side of the work. The product side lives in
[`adl-tan-theta/enact-agent`](https://github.com/adl-tan-theta/enact-agent).

---

## What is in here

| path | what it is |
|---|---|
| [`enact-tools-schema-report.html`](enact-tools-schema-report.html) | **the schema-level report** — every tool, before and after, with its real JSON schema and the config surface |
| [`enact-tools-surface-review.html`](enact-tools-surface-review.html) | the review — how the surface was consolidated and why |
| [`enact-sync-status.html`](enact-sync-status.html) | where the upstream sync stands, and what it will touch |
| `zeroclaw-tools-operations.csv` | the baseline inventory the review is built on (109 tools / 244 operations) |
| `build_tools_surface.py` + `rust_expr.py` | the Rust source → real tool schemas |
| `build_config_surface.py` | the binary → the real configuration surface |
| `render_tools_surface.py` | `tools-surface.json` + `config-surface.json` → the schema-level HTML |
| `build_report.py` / `render_report.py` | the review, and its HTML |
| `prototype/` | **enact-bridge** — a working MCP server that publishes enact-agent's tool surface to Codex CLI and Claude Code |
| `research/` | notes and the (local-only) third-party clones the review draws on |

The full narrative of the prototype lives in [`prototype/README.md`](prototype/README.md).

---

## The review in one page

`enact-agent` shipped **109 tools / 244 operations**. The review compared that surface
against three agents that solved the same problem differently, and proposed one answer:

| project | what it showed |
|---|---|
| [oh-my-pi](https://github.com/can1357/oh-my-pi) | a two-tool surface (`mcp_search` + `mcp_call`) over a much larger internal set, with `xd://` resources |
| [lean-ctx](https://github.com/yvgude/lean-ctx) | 82 → 35 tools by consolidation, and per-host hook dialects (17 actions × 11 hosts) |
| [jcode](https://github.com/1jehuang/jcode) | external tool injection over a Unix socket, and a token-budgeted tool reference list |

The conclusions, in short:

1. **Consolidate at the operation level.** Ten sibling families (`cron_*` + `schedule`,
   `memory_*`, `sessions_*`, …) collapse into one canonical tool each with a typed
   `action` enum. **109 → 83 tools, zero operations lost** — every `(tool, operation)`
   pair stays reachable exactly once.
2. **Do not advertise N schemas.** Two tools — `mcp_search` and `mcp_call` — keep the
   host's context budget intact.
3. **Degrade to each host's own policy.** The bridge reads Codex's `.rules` and Claude
   Code's `permissions` and mirrors their decisions instead of inventing a policy
   language.
4. **One wire format.** MCP, because Codex cannot serve tools and Claude Code can.

All of these landed in `enact-agent` — see the *native server* section of
[`prototype/README.md`](prototype/README.md) for what shipped where.

---

## Quick start

```sh
# regenerate the review (needs a checkout of enact-agent next to this repo)
python3 build_report.py     # inventory + verdicts → data.json
python3 render_report.py    # data.json → enact-tools-surface-review.html

# regenerate the schema-level report
python3 build_tools_surface.py   # the Rust source → every tool's real schema
python3 build_config_surface.py   # the binary → the real configuration surface
python3 render_tools_surface.py   # both → enact-tools-schema-report.html

# the bridge
cd prototype
python3 -m unittest discover -s tests -t .   # 68 tests
python3 bridge.py verify                     # 11 checks
python3 bridge.py show                       # 83 canonical tools, 244 operations
```

Pure Python 3.11+ standard library. **Zero dependencies.**

### The schema-level report

[`enact-tools-schema-report.html`](enact-tools-schema-report.html) shows the surface at
schema level: all **109** source tools and all **83** canonical tools, each with the JSON
schema it actually ships.

Nothing in it is written by hand.

* `build_tools_surface.py` reads every tool's `parameters_schema()` out of the Rust
  source and resolves the constants, associated constants, message catalogue and table
  folds that the schema refers to. `rust_expr.py` is the resolver.
* The same script drives the built binary over MCP (`mcp serve --expose-full`) and
  captures the `inputSchema` it really advertises, then compares the two. The only
  difference is `file_read`, whose schema the overlay rewrites in the prepared tree.
* `build_config_surface.py` reads the JSON Schema the binary prints for
  `zeroclaw config schema` — the same document the gateway serves at
  `GET /api/config` — and keeps the 19 sections that govern the tool surface.

The binary must be built with the `schema-export` feature for the config half:

```sh
cd ../enact-agent/target/enact/source
ENACT_AGENT_BUILD=1 CARGO_TARGET_DIR="$PWD/../../.." cargo build --locked --release \
  --no-default-features --features agent-runtime,tools-external,schema-export --bin zeroclaw
```

### Finding the enact-agent checkout

The scripts need a checkout of `enact-agent` because the **real** `compiled_in_enact`
flags live only in its overlay CSV — the copy in this repo claims every tool is
compiled in. Resolution order:

1. `ENACT_AGENT_DIR=/path/to/enact-agent`
2. `enact-agent` as a sibling of this repository
3. `enact-agent` inside this repository
4. `enact-agent` in the current directory or its parent

Set `ENACT_AGENT_DIR` when your layout differs. Nothing here hardcodes a machine path.

---

## The research clones are local-only

`research/` holds three third-party checkouts. They are **git-ignored on purpose** —
they are other people's code, and vendoring them would put 800 MB of someone else's
repository into this one.

```sh
git clone --depth 1 https://github.com/can1357/oh-my-pi.git research/oh-my-pi
git clone --depth 1 https://github.com/yvgude/lean-ctx.git research/lean-ctx
git clone --depth 1 https://github.com/1jehuang/jcode.git research/jcode
```

The commits the review was written against are recorded in
[`research/README.md`](research/README.md).

---

## Working rule: where changes land

> **All pull requests for this work target `enact/branding` in
> `adl-tan-theta/enact-agent` — never the `zeroclaw-labs/zeroclaw` upstream.**

`enact/branding` is the fork's integration branch. Upstream is a *source*, not a
destination: changes are authored in the fork's overlay and proposed against the
fork's own branch. Nothing in this project opens a PR against upstream zeroclaw.

The product-side rule lives with the product, in
[`enact-agent/overlays/enact/AGENTS.md`](https://github.com/adl-tan-theta/enact-agent/blob/enact/branding/overlays/enact/AGENTS.md).

---

## Relationship to `enact-agent`

```
enact-agent (the product, Rust)
  overlays/enact/            ← fork-only overlay: native MCP server, families, hooks
  overlays/enact/build.py    ← projects the overlay into the prepared tree
          ▲
          │  this repository supplies the inventory, the review and the host bridge
          │
enact-tools (this repo, Python)
  prototype/                 ← host-facing bridge (installs into Codex & Claude Code)
  build_report.py            ← the review
  build_tools_surface.py     ← the schema-level report
```

The division of labour: **the MCP server and the tool registry belong to
`enact-agent`** (it owns the real implementations and the real policy gate); **host
installation, policy mirroring and registry generation belong here** (they are
host-facing, and must work against a stock upstream build too).

---

## Licensing

This repository holds the fork's own review, generators and host adapter. It
carries no license file of its own yet — the code here is **ZeroClaw Labs'**
(the fork's upstream copyright holder), and the sibling `enact-agent` fork is
distributed under the upstream dual MIT / Apache-2.0 terms with its `LICENSE-MIT`,
`LICENSE-APACHE` and `NOTICE` files.

The three research projects this review compares against are **not**
redistributed here — they are git-ignored and cloned on demand:

| project | license |
|---|---|
| [oh-my-pi](https://github.com/can1357/oh-my-pi) | MIT (© 2025 Mario Zechner) |
| [lean-ctx](https://github.com/yvgude/lean-ctx) | Apache-2.0, with a path-level `LICENSE_MATRIX.toml` |
| [jcode](https://github.com/1jehuang/jcode) | MIT (© 2025 Jeremy Huang) |

`zeroclaw-tools-operations.csv` is derived from `enact-agent`'s own inventory and
inherits the upstream dual MIT / Apache-2.0 terms.

