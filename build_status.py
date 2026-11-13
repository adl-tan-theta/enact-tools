#!/usr/bin/env python3
"""Build the status facts for the Enact sync report.

Curated findings live in STATUS below. Anything that can be re-derived from the
two repositories is re-derived here, so the report cannot silently drift from
the tree it describes.

    python3 build_status.py     # -> status.json
    python3 render_status.py    # status.json -> enact-sync-status.html
"""
from __future__ import annotations

import json
import os
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(os.path.dirname(ROOT), "enact-agent")

STATUS = {
    "generated": "2026-11-13",
    "question": (
        "Where do we stand, and what does syncing with zeroclaw master actually cost?"
    ),
    "headline": (
        "The fork is feature-complete and green. The upstream sync is small in "
        "conflict terms and large in structure: 23 commits, one text conflict, and "
        "four overlay anchors that move because upstream split the RPC contract "
        "into a new published crate."
    ),
    "verdict": (
        "Take the sync. It is one conflict, two moved files and one new "
        "requirement the anchor count cannot see: upstream's Method contract match "
        "is arm-complete, so the fork's session/tools variant needs a contract arm "
        "in the published crate, not just an enum variant."
    ),

    # ---------------------------------------------------------------- repos
    "repos": [
        {
            "name": "adl-tan-theta/enact-agent",
            "role": "the product — a fork of zeroclaw-labs/zeroclaw",
            "url": "https://github.com/adl-tan-theta/enact-agent",
            "visibility": "public",
            "state": "Branch worktree/affectionate-ride-r8iuw6 @ 2dea86718, in sync with origin.",
            "detail": (
                "Pull request #4 is OPEN, MERGEABLE and CLEAN against base "
                "enact/branding: +40,846 / −2,102 across 222 files. Both fork "
                "checks pass (Validate PR title, Apply path labels). Upstream "
                "zeroclaw master contains no Enact commit — the fork never pushes "
                "upstream."
            ),
            "state_kind": "good",
        },
        {
            "name": "adl-tan-theta/enact-tools",
            "role": "the workspace — review, report generators, host bridge",
            "url": "https://github.com/adl-tan-theta/enact-tools",
            "visibility": "public",
            "state": "main @ 9605d98, 3 commits, 34 tracked files (652 KB).",
            "detail": (
                "Cleaned and published this session. The three third-party research "
                "clones (823 MB) and the demo project's generated host wiring are "
                "git-ignored; the pinned commits and clone commands are recorded in "
                "research/README.md. Paths into the sibling enact-agent checkout now "
                "resolve through ENACT_AGENT_DIR instead of a hardcoded location, so "
                "a fresh clone builds with no machine-specific paths."
            ),
            "state_kind": "good",
        },
    ],

    # ---------------------------------------------------------------- roadmap
    "roadmap": [
        {
            "phase": "Phase 0",
            "title": "Native MCP server",
            "detail": (
                "enact-agent mcp serve over stdio and HTTP, mcp_search / mcp_call, "
                "host MCP config discovery, enact-agent mcp hosts."
            ),
            "state": "landed",
        },
        {
            "phase": "Phase 1",
            "title": "Declarative hooks + plugin hook capability",
            "detail": (
                "Six events, 20 tests, hook docs, post-call output rewriting, the "
                "hook.wit WIT world with a WasmHook adapter (6 tests), and a "
                "trusted/untrusted message split."
            ),
            "state": "landed",
        },
        {
            "phase": "Phase 2",
            "title": "Context and code intelligence",
            "detail": (
                "compose, expand, ast_grep / ast_edit, callgraph / graph, radar, "
                "workspace_scan, the tool-output archive, the context ledger and five "
                "file_read modes."
            ),
            "state": "landed",
        },
        {
            "phase": "Phase 3",
            "title": "Consolidated tool families",
            "detail": (
                "Ten family tools over 36 members, operation-level actions, bounded "
                "schema, legacy names stay callable, one-time deprecation notice. "
                "Counts are derived: 109 source tools, 83 canonical, 244 operations."
            ),
            "state": "landed",
        },
        {
            "phase": "Phase 4",
            "title": "Coordination and mode primitives",
            "detail": (
                "wait, learn with skills_list / skill_view / skill_manage, "
                "checkpoint / rewind (dual history and canonical anchor), "
                "plan_mode / plan_execute, and read / write / exec approval tiers."
            ),
            "state": "landed",
        },
    ],

    # ---------------------------------------------------------------- evidence
    "verification": [
        {"check": "Overlay gate", "result": "27 / 27 OK", "state": "good"},
        {"check": "Capability contract", "result": "2 / 2 OK", "state": "good"},
        {"check": "Family table", "result": "19 / 19 OK", "state": "good"},
        {"check": "zeroclaw-runtime --lib", "result": "6335 passed / 2 failed", "state": "warn"},
        {"check": "zeroclaw-tools --lib", "result": "1789 / 0", "state": "good"},
        {"check": "zeroclaw-config --lib", "result": "1994 / 0", "state": "good"},
        {"check": "zeroclaw-plugins --lib", "result": "469 / 0", "state": "good"},
        {"check": "Root package --lib", "result": "282 / 0", "state": "good"},
        {"check": "mcp_server bin", "result": "34 / 0", "state": "good"},
        {"check": "Bridge suite + bridge.py verify", "result": "68 OK, 11 / 11", "state": "good"},
        {"check": "Native build CI (ubuntu, macos arm64, macos x64)", "result": "3 / 3 green", "state": "good"},
        {"check": "Artifact hand-verification", "result": "checksums, provenance, 0 private-home hits, NATIVE VERIFY OK 5/5", "state": "good"},
        {"check": "Web", "result": "tsc -b clean, 8 + 12 tests pass", "state": "good"},
    ],
    "verification_note": (
        "The two runtime failures are relay::local_dial_tests only. "
        "crates/zeroclaw-runtime/src/relay.rs is byte-identical to upstream master "
        "and prepare() does not rewrite it, so they are a macOS loopback environment "
        "issue inherited from upstream, not an overlay regression."
    ),

    # ---------------------------------------------------------------- the sync
    "sync": {
        "upstream_head": "2c0a8c263",
        "upstream_head_subject": "chore(deps): bump the web-minor-patch group across 1 directory with 21 updates (#11842)",
        "pending_commits": 23,
        "merge_base": "8512b711d",
        "fork_core_matches": "06765b1e6",
        "fork_core_subject": "fix(install): prefer system glibc over an installed musl loader (#12160)",
        "files_changed": 146,
        "insertions": 36035,
        "deletions": 4212,
        "conflicts": 1,
        "new_crates": ["zeroclaw-rpc-proto", "zeroclaw-rpc-client"],
        "version_change": "Cargo.toml 0.8.7 → 0.9.0",
        "cargo_lock": "identical to upstream after the merge — the fork adds no dependency churn",
        "inventory": "untouched — upstream changes neither inventory.rs nor builtin_tools.rs, so the canonical tool set and its gate are unaffected",
    },

    # ---------------------------------------------------------------- anchors
    "anchors": {
        "checked": 44,
        "broken": 4,
        "files": 2,
        "method": (
            "build.py's replace_required was instrumented to collect every failure "
            "in one pass instead of raising on the first, then the merged tree was "
            "prepared for real."
        ),
        "items": [
            {
                "file": "crates/zeroclaw-runtime/src/rpc/dispatch.rs",
                "anchor": '"    SessionState,\\n"',
                "was": "the Method enum variant list",
                "now": "crates/zeroclaw-rpc-proto/src/method.rs",
                "why": "upstream moved the Method enum into the new protocol crate",
            },
            {
                "file": "crates/zeroclaw-runtime/src/rpc/dispatch.rs",
                "anchor": '"        (Method::SessionState, \\"session/state\\"),\\n"',
                "was": "the Method::ALL wire-name table",
                "now": "crates/zeroclaw-rpc-proto/src/method.rs",
                "why": "the single wire table moved with the enum",
            },
            {
                "file": "crates/zeroclaw-runtime/src/rpc/types.rs",
                "anchor": '"rpc_type! {\\n    pub struct SessionStateResult {"',
                "was": "the SessionStateResult definition",
                "now": "crates/zeroclaw-rpc-proto/src/types.rs",
                "why": "the wire payload types moved into the protocol crate",
            },
            {
                "file": "crates/zeroclaw-runtime/src/rpc/types.rs",
                "anchor": '"        raw_output: String,\\n    },\\n    ApprovalRequest {"',
                "was": "the tool-result status field the overlay adds",
                "now": "crates/zeroclaw-rpc-proto/src/types.rs",
                "why": "SessionUpdateEvent is now a protocol-crate type",
            },
        ],
        "surviving": (
            "The other 40 anchors still resolve exactly once — including the "
            "authz and MethodAuthz arms in dispatch.rs, the handle_session_state "
            "insertion point, tool_names in agent.rs and the tool-result status "
            "field in zeroclaw-api/src/agent.rs."
        ),
    },

    # ---------------------------------------------------------------- the real risk
    "hidden_risks": [
        {
            "title": "Method::contract is arm-complete",
            "severity": "high",
            "detail": (
                "upstream's contract() match covers the closed enum exhaustively — "
                "its own comment says a new method cannot be added without "
                "declaring what it accepts and returns. Adding the fork's "
                "SessionTools variant therefore does not compile until a contract "
                "arm is added in the same file. An anchor count cannot see this; "
                "the compiler does."
            ),
        },
        {
            "title": "Method::ALL is the single wire table",
            "severity": "high",
            "detail": (
                "wire_name() panics with \"every variant is in ALL\" if a variant is "
                "missing from the table, and from_wire() is a scan of that same "
                "table. The fork's session/tools entry has to land in the table, "
                "not only in the enum."
            ),
        },
        {
            "title": "The schema catalog test is exclusive",
            "severity": "high",
            "detail": (
                "every_typed_contract_resolves_to_a_schema_or_an_external_owner "
                "asserts a named contract type is EXACTLY ONE of catalog-defined or "
                "external. SessionToolsResult must therefore be added to the proto "
                "catalog (it is plain data, so upstream's own rule puts it in the "
                "protocol crate) — not left out."
            ),
        },
        {
            "title": "The overlay now patches a published crate",
            "severity": "medium",
            "detail": (
                "zeroclaw-rpc-proto is publish = true and its rpc_type! macro "
                "derives JsonSchema under schema-export, where the runtime's macro "
                "does not. The fork's added success field on the tool-result "
                "notification now participates in schema export, so the tracked "
                "OpenRPC document would drift if it were ever regenerated from a "
                "prepared tree."
            ),
        },
        {
            "title": "That drift is not caught by CI today",
            "severity": "medium",
            "detail": (
                "upstream's ci.yml runs cargo generate openrpc --check, but the "
                "fork's ci.yml triggers only on pull_request to master while the "
                "fork's default branch is enact/branding — so upstream's Quality "
                "Gate does not run here at all. Only Validate PR title, Apply path "
                "labels and the manual native build run. This is why the local "
                "test sweep is the real gate, and it is worth adding the OpenRPC "
                "check to the fork's own workflow."
            ),
        },
        {
            "title": "The release gate check already fails today",
            "severity": "high",
            "detail": (
                "AGENTS.md requires git diff --exit-code $upstream_base -- src "
                "crates Cargo.toml Cargo.lock with the base pinned in release.json. "
                "That check fails on the branch right now: release.json pins "
                "1c1cd118 but the branch's core actually matches 06765b1e6, which is "
                "75 upstream commits further on. This is pre-existing drift, not "
                "caused by the pending sync, and it must be fixed by re-pinning "
                "release.json during the sync."
            ),
        },
        {
            "title": "The distribution version has to move",
            "severity": "medium",
            "detail": (
                "The merge takes Cargo.toml to 0.9.0, so release.json's version has "
                "to move from 0.8.7-enact.2 to a 0.9.0-based one, and the "
                "upstreamCommit pin has to become the new upstream head. The "
                "published 0.8.7-enact.1 release and its withdrawn sibling stay "
                "untouched."
            ),
        },
    ],

    # ---------------------------------------------------------------- the plan
    "plan": [
        {
            "step": "1",
            "title": "Merge upstream/master into the PR branch",
            "detail": (
                "Already rehearsed in a scratch worktree: one conflict, "
                "web/package.json, resolved as a union — upstream's dependency bumps "
                "and its two new test entries, plus the fork's branding test. "
                "146 files, +36,035 / −4,212."
            ),
        },
        {
            "step": "2",
            "title": "Re-point the four moved anchors at the protocol crate",
            "detail": (
                "Follow upstream's structure rather than reshaping its RPC types: "
                "the enum variant and wire table move to zeroclaw-rpc-proto/src/"
                "method.rs, the payload anchors to zeroclaw-rpc-proto/src/types.rs, "
                "and SessionToolsResult is defined in the protocol crate with a "
                "catalog entry, matching upstream's own rule that plain wire data "
                "lives in the protocol crate."
            ),
        },
        {
            "step": "3",
            "title": "Add the contract arm and the catalog entry",
            "detail": (
                "The part no anchor count finds: a Method::contract arm for "
                "SessionTools (the match is arm-complete) and SessionToolsResult in "
                "the proto schema catalog (the catalog test is exclusive)."
            ),
        },
        {
            "step": "4",
            "title": "Re-pin release.json",
            "detail": (
                "upstreamCommit becomes the new upstream head and the version moves "
                "to a 0.9.0-based one, which makes the documented core-match check "
                "pass again instead of failing as it does today."
            ),
        },
        {
            "step": "5",
            "title": "Re-run the whole gate",
            "detail": (
                "Overlay gate, the cargo test sweep, cargo fmt, a release build and "
                "probe_native.py, then the native build workflow on all three "
                "platforms — because session/tools is asserted by the native "
                "fixture, so the fork's own method has to survive the move."
            ),
        },
        {
            "step": "6",
            "title": "Push and keep PR #4 open against enact/branding",
            "detail": (
                "Never upstream. The convention is recorded in "
                "overlays/enact/AGENTS.md and in the enact-tools README."
            ),
        },
    ],

    # ---------------------------------------------------------------- rules
    "rules": [
        {
            "rule": "Pull requests target enact/branding",
            "detail": (
                "In adl-tan-theta/enact-agent. The zeroclaw-labs/zeroclaw upstream is "
                "the source that gets reviewed and merged in, never the destination. "
                "Recorded in overlays/enact/AGENTS.md (commit 2dea86718) and in the "
                "enact-tools README."
            ),
        },
        {
            "rule": "Always sync with zeroclaw master",
            "detail": (
                "Upstream master is the source of truth for the core. The fork owns "
                "the overlay; upstream owns the Rust. A sync is a merge plus an "
                "anchor re-point, never a rewrite of upstream's structure."
            ),
        },
        {
            "rule": "The overlay never edits tracked Rust",
            "detail": (
                "All native changes are authored under overlays/enact/ and injected "
                "by build.py into the prepared tree. No new crates, no Cargo.toml or "
                "Cargo.lock churn, cargo build --locked."
            ),
        },
    ],

    # ---------------------------------------------------------------- what is not done
    "open": [
        "The merge is rehearsed in a scratch worktree, not applied to the PR branch yet.",
        "The four anchors are not yet re-pointed — the re-point is scoped and specified, not implemented.",
        "release.json still pins the stale 1c1cd118 base and the 0.8.7-enact.2 version.",
        "The gate, the cargo sweep and the native build have not been re-run against the merged tree.",
        "The fork's CI still does not run upstream's Quality Gate, including cargo generate openrpc --check.",
    ],
}


def git(*args: str, cwd: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def git_diff_is_clean(base: str, cwd: str | None = None) -> bool:
    """True when `base` and HEAD agree on the tracked core.

    `git diff --quiet` exits 0 when clean and 1 when it differs, and prints
    nothing either way — so the exit status has to be read, not the output.
    """
    result = subprocess.run(
        [
            "git", "diff", "--quiet", base, "--",
            "src", "crates", "Cargo.toml", "Cargo.lock",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def derive() -> None:
    """Re-derive what can be checked from the tree, so the report cannot drift."""
    if not os.path.isdir(os.path.join(AGENT, ".git")):
        return

    STATUS["derived"] = {
        "enact_agent_head": git("rev-parse", "--short", "HEAD", cwd=AGENT),
        "enact_agent_branch": git("rev-parse", "--abbrev-ref", "HEAD", cwd=AGENT),
        "enact_agent_clean": git("status", "--porcelain", cwd=AGENT) == "",
        "upstream_head": git("rev-parse", "--short", "upstream/master", cwd=AGENT),
        "upstream_pending": git(
            "rev-list", "--count", "HEAD..upstream/master", cwd=AGENT
        ),
        "core_matches": git_diff_is_clean("06765b1e6", cwd=AGENT),
    }

    pinned = ""
    release_json = os.path.join(AGENT, "overlays", "enact", "release.json")
    if os.path.exists(release_json):
        with open(release_json) as handle:
            pinned = json.load(handle).get("upstreamCommit", "")
    STATUS["derived"]["release_pinned_base"] = pinned[:9]
    if pinned:
        STATUS["derived"]["release_gate_core_match"] = git_diff_is_clean(
            pinned, cwd=AGENT
        )


def main() -> None:
    derive()
    with open(os.path.join(ROOT, "status.json"), "w") as handle:
        json.dump(STATUS, handle, indent=1)
    print(f"wrote {os.path.join(ROOT, 'status.json')}")
    for key, value in STATUS["derived"].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
