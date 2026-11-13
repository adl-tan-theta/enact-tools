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
        "The upstream sync is applied. 23 upstream commits are merged, the four "
        "moved anchors are re-pointed at the new protocol crate, the three "
        "exhaustiveness constraints upstream imposes are satisfied, and the fork's "
        "tracked core is byte-identical to upstream master again. The cargo sweep "
        "that followed the merge failed five tests in three targets; a control run "
        "against pristine upstream sorted them, and the three the fork owned are "
        "fixed. Widening the sweep to the channels crate found three more, all "
        "pre-existing. The tree now fails exactly what pristine upstream fails."
    ),
    "verdict": (
        "The sync is in, and the fork is back at parity with upstream. The tracked "
        "core matches byte for byte, the overlay follows upstream's structure in "
        "zeroclaw-rpc-proto, and release.json pins the base the core actually "
        "matches. The sweep that the merge triggered also surfaced four real "
        "defects — the overlay was promising a tool a default build cannot "
        "deliver, was offering the memory family to runs that had removed the "
        "memory tools, and left the Matrix channel's own expectations stale for "
        "the skill tools the fork registers. All are fixed and gated. What is "
        "left is the CI gap: upstream's Quality Gate still does not run in the "
        "fork, so nothing checks those anchors for us."
    ),

    # ---------------------------------------------------------------- repos
    "repos": [
        {
            "name": "adl-tan-theta/enact-agent",
            "role": "the product — a fork of zeroclaw-labs/zeroclaw",
            "url": "https://github.com/adl-tan-theta/enact-agent",
            "visibility": "public",
            "state": "Branch worktree/affectionate-ride-r8iuw6 @ d550d902d, in sync with origin.",
            "detail": (
                "Pull request #4 is OPEN, MERGEABLE and CLEAN against base "
                "enact/branding: 93 commits, 336 files. The fork's own checks run "
                "on the pull request — Validate PR title, Apply path labels, the "
                "Desktop App Check on three platforms, and the translations pin. "
                "Upstream zeroclaw master contains no Enact commit — the fork never "
                "pushes upstream."
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
        {"check": "Overlay gate", "result": "35 / 35 OK", "state": "good"},
        {"check": "prepare() against the merged tree", "result": "clean — all 44 anchors resolve once", "state": "good"},
        {"check": "Capability contract", "result": "2 / 2 OK", "state": "good"},
        {"check": "Family table", "result": "19 / 19 OK", "state": "good"},
        {"check": "zeroclaw-rpc-proto --lib (new crate)", "result": "25 / 0 — including the exclusive catalog test", "state": "good"},
        {"check": "zeroclaw-api --lib", "result": "322 / 0", "state": "good"},
        {"check": "Cargo sweep (debug, 7 crates)", "result": "3 failures in 2 targets — the same three pristine upstream fails on this host", "state": "good"},
        {"check": "Control run against pristine upstream/master", "result": "3 of the 5 sweep failures reproduce upstream — the other two were the fork's", "state": "good"},
        {"check": "zeroclaw-channels --lib", "result": "2061 / 0 after the Matrix policy fix", "state": "good"},
        {"check": "Native probe (local RPC)", "result": "24 checks OK — session/tools and the success field both work end to end", "state": "good"},
        {"check": "Release build", "result": "5m 30s, no warnings", "state": "good"},
        {"check": "Release-gate core check", "result": "git diff --exit-code 2c0a8c263 -- src crates Cargo.toml Cargo.lock: clean", "state": "good"},
        {"check": "Tool surface after the merge and the fixes", "result": "109 / 109 schemas extracted, 0 unresolved, 83 canonical, 52 advertised, 1 source-vs-binary difference (file_read, the overlay's own patch)", "state": "good"},
        {"check": "Web", "result": "branding + sidebar 8 / 8", "state": "good"},
        {"check": "Bridge suite + bridge.py verify", "result": "68 OK, 11 / 11", "state": "good"},
        {"check": "Desktop App Check (3 platforms)", "result": "ubuntu-22.04 failed once on upstream's own desktop test, then green on re-run; 920 iterations of a standalone reproducer did not reproduce it", "state": "warn"},
        {"check": "Native build CI (ubuntu, macos arm64, macos x64)", "result": "dispatched on the merged tree", "state": "warn"},
    ],
    "verification_note": (
        "The three remaining failures are the ones pristine upstream fails on the "
        "same machine. Two are relay::local_dial_tests — crates/zeroclaw-runtime/"
        "src/relay.rs is byte-identical to upstream master and prepare() does not "
        "rewrite it, so they are a macOS loopback environment issue. One is a "
        "model-routing test that fails only when it runs in the full sweep and "
        "passes alone; it fails the same way upstream."
    ),

    # ---------------------------------------------------------------- the triage
    "triage": {
        "headline": (
            "Five failures in three cargo targets, sorted by a control run against "
            "pristine upstream."
        ),
        "method": (
            "The sweep that followed the merge failed three targets. To tell a "
            "regression from an inherited failure, a second worktree was created at "
            "upstream/master — pristine, no overlay, its own target directory — and "
            "the same sweep was run against it on the same machine. A failure that "
            "reproduced there is upstream's; a failure that did not is the fork's. "
            "The sweep's crate list was then widened to the channels crate, which "
            "had not been covered; it held three more failures, all pre-existing."
        ),
        "before": "5 failures in 3 targets, then 3 more in a crate the sweep had not reached",
        "after": "3 failures in 2 targets — exactly the three pristine upstream fails",
        "rows": [
            {
                "test": "tools::tests::every_inventoried_tool_registers_under_a_maximal_config",
                "upstream": "passes",
                "fork": "failed",
                "state": "fixed",
                "cause": (
                    "The inventory row a family gets claimed Always while its members "
                    "sit behind tools-external. The email family collapses two "
                    "external adapters, so a default build promised a tool it cannot "
                    "deliver, and upstream's gate — every compiled row must register "
                    "under the maximal config — failed on the missing family."
                ),
                "fix": (
                    "The row now carries the compilation group of the family's "
                    "members, and a family that collects the external adapters joins "
                    "the canonical adapter list beside them, so upstream's \"the "
                    "external compilation rows match the canonical adapter names\" "
                    "check holds."
                ),
            },
            {
                "test": "uses_memory_false_cron_run_has_no_memory_backend_or_tools",
                "upstream": "passes",
                "fork": "failed",
                "state": "fixed",
                "cause": (
                    "The scope filter drops the persistent memory tools by name, and "
                    "a family's own name is not one of its members'. A memory-free "
                    "cron run was therefore still offered the memory family, whose "
                    "description names every member and whose actions call the very "
                    "tools uses_memory = false removes. This was a behavioural "
                    "defect, not only a test failure: the run was offered memory "
                    "access it had been told to drop."
                ),
                "fix": (
                    "A consolidated family is now offered only while at least one of "
                    "its members is, and the builtin-selection fixture follows the "
                    "same rule for the ACP turn."
                ),
            },
            {
                "test": "full_chat_and_acp_restore_the_matching_builtin_fixture",
                "upstream": "passes",
                "fork": "failed",
                "state": "fixed",
                "cause": (
                    "The fixture the overlay maintains expected the memory family to "
                    "survive the ACP turn even though every member was dropped — the "
                    "old behaviour, written down."
                ),
                "fix": (
                    "The fixture now drops a family whose every member is a memory "
                    "tool, so the expectation states the corrected rule."
                ),
            },
            {
                "test": "orchestrator::tests::matrix_safe_policy_names_only_inventoried_tools",
                "upstream": "passes",
                "fork": "failed",
                "state": "fixed",
                "cause": (
                    "Upstream deliberately leaves skills_list, skill_view and "
                    "skill_manage out of the built-in inventory and allows for "
                    "them in the Matrix policy's test. The fork registers and "
                    "inventories them, so the allowlist was stale. This one was "
                    "pre-existing: it fails the same way with the overlay from "
                    "before the sync."
                ),
                "fix": "The allowlist lets the three go, because the fork inventories them.",
            },
            {
                "test": "orchestrator::tests::matrix_safe_policy_fields_match_active_standard_tool_schemas",
                "upstream": "passes",
                "fork": "failed",
                "state": "fixed",
                "cause": (
                    "The policy named a \"name\" argument for skill_view, "
                    "skill_manage and skills_list. skill_view and skill_manage "
                    "take a \"slug\", and skills_list takes none. Upstream's entry "
                    "is dormant there, because those tools are never in its "
                    "default registry; the fork registers them, so the entry "
                    "became live and wrong."
                ),
                "fix": "The policy now names the arguments the tools really take.",
            },
            {
                "test": "orchestrator::tests::process_channel_message_refreshes_available_skills_after_new_session",
                "upstream": "passes",
                "fork": "failed",
                "state": "fixed",
                "cause": (
                    "The test asserts on the product literal the fork replaces. "
                    "The branding projection reached the runtime's skill files "
                    "but not the channels crate."
                ),
                "fix": "The branding projection now reaches the channels crate too.",
            },
            {
                "test": "relay::local_dial_tests::a_closed_route_releases_a_dial_parked_on_a_stalled_listener",
                "upstream": "fails",
                "fork": "fails",
                "state": "inherited",
                "cause": (
                    "\"the listener backlog never filled\" — the test cannot stall a "
                    "loopback connect on this macOS host."
                ),
                "fix": "Nothing to fix in the fork: the file is byte-identical to upstream.",
            },
            {
                "test": "relay::local_dial_tests::a_dial_that_never_connects_ends_on_its_own_budget",
                "upstream": "fails",
                "fork": "fails",
                "state": "inherited",
                "cause": "Same host limitation as the test above.",
                "fix": "Nothing to fix in the fork: the file is byte-identical to upstream.",
            },
            {
                "test": "model_routing_config::tests::set_default_probes_an_environment_only_model_override",
                "upstream": "fails",
                "fork": "fails",
                "state": "inherited",
                "cause": (
                    "Order-dependent: it fails in the full sweep and passes when run "
                    "alone, on upstream's tree as well as on the fork's."
                ),
                "fix": "Nothing to fix in the fork: the file is byte-identical to upstream.",
            },
        ],
        "note": (
            "The overlay gate grew from 27 to 35 tests. The new ones state the two "
            "rules the fixes rest on: a family row has to carry its members' "
            "compilation group, and no family may mix memory and other members, "
            "carry a tool the filter drops by itself, or be a member of another "
            "family — so the family lookup terminates."
        ),
    },

    # ---------------------------------------------------------------- the sync
    "sync": {
        "upstream_head": "2c0a8c263",
        "upstream_head_subject": "chore(deps): bump the web-minor-patch group across 1 directory with 21 updates (#11842)",
        "pending_commits": 0,
        "merge_base": "2c0a8c263 — upstream master is now an ancestor of the fork",
        "fork_core_matches": "2c0a8c263",
        "fork_core_subject": "the tracked core is byte-identical to upstream master: src, crates, Cargo.toml and Cargo.lock all diff clean",
        "files_changed": 146,
        "insertions": 36035,
        "deletions": 4212,
        "conflicts": 1,
        "conflict_resolution": "web/package.json, resolved as a union — upstream's test:auth and test:contexts (upstream added scoped-chat and scoped-agent cases) plus this fork's test:branding",
        "new_crates": ["zeroclaw-rpc-proto", "zeroclaw-rpc-client"],
        "version_change": "Cargo.toml 0.8.7 → 0.9.0",
        "cargo_lock": "identical to upstream after the merge — the fork adds no dependency churn",
        "inventory": "untouched — upstream changes neither inventory.rs nor builtin_tools.rs, so the canonical tool set and its gate are unaffected",
    },

    # ---------------------------------------------------------------- anchors
    "anchors": {
        "checked": 44,
        "broken": 0,
        "files": 0,
        "method": (
            "build.py's replace_required was instrumented to collect every failure "
            "in one pass instead of raising on the first, then the merged tree was "
            "prepared for real. All four moved anchors were re-pointed and "
            "prepare() now runs clean against the merged tree."
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
            "All 44 anchors now resolve exactly once — the four moved ones at "
            "their new homes in zeroclaw-rpc-proto, and the other 40 where they "
            "were: the authz and MethodAuthz arms in dispatch.rs, the "
            "handle_session_state insertion point, tool_names in agent.rs and the "
            "tool-result status field in zeroclaw-api/src/agent.rs."
        ),
        "resolved": (
            "Each moved anchor was re-pointed at upstream's own structure rather "
            "than reshaping it. The enum variant, the wire-name entry and a new "
            "Method::contract arm now live in zeroclaw-rpc-proto/src/method.rs; "
            "SessionToolsResult and the tool-result status field live in "
            "zeroclaw-rpc-proto/src/types.rs; and SessionToolsResult joins the "
            "proto schema catalog, because upstream's rule is that plain wire data "
            "lives in the protocol crate and the catalog is exclusive."
        ),
    },

    # ---------------------------------------------------------------- the real risk
    "hidden_risks": [
        {
            "title": "The consolidation promised a tool a build cannot deliver",
            "severity": "resolved",
            "detail": (
                "Every consolidated family got an inventory row claiming Always, "
                "while the email family's members sit behind tools-external. A "
                "default build therefore promised a tool it could not deliver, and "
                "upstream's own gate — every compiled row must register under the "
                "maximal config — failed on it. The row now carries the "
                "compilation group of the members, and a family that collects the "
                "external adapters joins the canonical adapter list with them."
            ),
        },
        {
            "title": "The consolidation offered memory to runs that had removed it",
            "severity": "resolved",
            "detail": (
                "The scope filter drops the persistent memory tools by name, and a "
                "family's own name is not one of its members'. A cron run with "
                "uses_memory = false was therefore still offered the memory family, "
                "whose description names every member and whose actions call the "
                "very tools the run was told to drop. This was behaviour, not only a "
                "test: the run was offered memory access it had been denied. A "
                "family is now offered only while at least one of its members is, "
                "and the overlay gate states that rule."
            ),
        },
        {
            "title": "The sweep's crate list was the gap, not the merge",
            "severity": "resolved",
            "detail": (
                "The first sweep covered six crates. Widening it to the channels "
                "crate found three more failures, all pre-existing: the fork makes "
                "the skill tools first-class, and upstream's Matrix channel "
                "expectations were written for a registry that never holds them. "
                "The allowlist, the policy's field list and the branding literal "
                "all follow now. The lesson for the fork is that the sweep's crate "
                "list is itself a decision, and a narrow one hides old failures."
            ),
        },
        {
            "title": "Upstream's CI never runs the desktop crate — the fork does",
            "severity": "medium",
            "detail": (
                "upstream's ci.yml excludes zeroclaw-desktop from every test job, "
                "so upstream never runs apps/tauri's own tests. The fork's Desktop "
                "App Check does, which is how a one-off ubuntu-22.04 failure in "
                "spawn_daemon_kills_group_when_supervisor_exits_before_cleanup "
                "surfaced. The code is byte-identical to upstream, and the same "
                "commit passed on re-run; a standalone reproducer built from "
                "upstream's own functions did not reproduce it in 620 Linux "
                "iterations — including under CPU starvation — or 300 macOS ones. "
                "The fork is the first place this test runs, so this is where it "
                "will be seen."
            ),
        },
        {
            "title": "Method::contract is arm-complete — satisfied",
            "severity": "resolved",
            "detail": (
                "upstream's contract() match covers the closed enum exhaustively — "
                "its own comment says a new method cannot be added without "
                "declaring what it accepts and returns. The overlay now adds the "
                "SessionTools arm in zeroclaw-rpc-proto/src/method.rs, alongside "
                "the variant. The crate compiles and the contract test passes."
            ),
        },
        {
            "title": "Method::ALL is the single wire table — satisfied",
            "severity": "resolved",
            "detail": (
                "wire_name() panics with \"every variant is in ALL\" if a variant is "
                "missing from the table, and from_wire() is a scan of that same "
                "table. The session/tools entry lands in the table in "
                "zeroclaw-rpc-proto/src/method.rs, not only in the enum."
            ),
        },
        {
            "title": "The schema catalog test is exclusive — satisfied",
            "severity": "resolved",
            "detail": (
                "every_typed_contract_resolves_to_a_schema_or_an_external_owner "
                "asserts a named contract type is EXACTLY ONE of catalog-defined or "
                "external. SessionToolsResult is added to the proto catalog — it is "
                "plain data, so upstream's own rule puts it in the protocol crate. "
                "The test passes."
            ),
        },
        {
            "title": "The overlay now patches a published crate",
            "severity": "medium",
            "detail": (
                "zeroclaw-rpc-proto is publish = true and its rpc_type! macro "
                "derives JsonSchema under schema-export, where the runtime's macro "
                "does not. The fork's added success field on the tool-result "
                "notification now participates in schema export. The tracked "
                "OpenRPC document stays upstream's, so upstream's own "
                "cargo generate openrpc --check still passes against the tracked "
                "crate — editing the generated document by hand would break that "
                "gate. The prepared tree's copy is stale by exactly the "
                "session/tools method, and the book is not part of the shipped "
                "release artifact."
            ),
        },
        {
            "title": "Upstream's Quality Gate still does not run in the fork",
            "severity": "high",
            "detail": (
                "upstream's ci.yml triggers only on pull_request to master while the "
                "fork's default branch is enact/branding — so upstream's Quality "
                "Gate does not run here at all, and the merge brought in a new gate "
                "inside it (cargo generate openrpc --check). Only Validate PR title, "
                "Apply path labels and the manually dispatched native build run on "
                "the fork's PRs. Retargeting the gate at enact/branding is a "
                "decision about CI minutes, so it is left to the owner."
            ),
        },
        {
            "title": "The release gate check — now clean",
            "severity": "resolved",
            "detail": (
                "AGENTS.md requires git diff --exit-code $upstream_base -- src "
                "crates Cargo.toml Cargo.lock with the base pinned in release.json. "
                "That check failed before the sync: release.json pinned 1c1cd118 "
                "while the branch's core actually matched 06765b1e6, 75 upstream "
                "commits further on. release.json now pins 2c0a8c263 and the check "
                "passes clean."
            ),
        },
        {
            "title": "The distribution version — moved",
            "severity": "resolved",
            "detail": (
                "The merge takes Cargo.toml to 0.9.0, so release.json's version "
                "moved from 0.8.7-enact.2 to 0.9.0-enact.1 and the upstreamCommit "
                "pin became the new upstream head. The published 0.8.7-enact.1 "
                "release and its withdrawn sibling stay untouched."
            ),
        },
    ],

    # ---------------------------------------------------------------- the plan
    "plan": [
        {
            "step": "1",
            "title": "Merge upstream/master into the PR branch — done",
            "detail": (
                "Merged into worktree/affectionate-ride-r8iuw6 as fb0314b99. One "
                "conflict, web/package.json, resolved as a union — upstream's "
                "test:auth and test:contexts plus the fork's test:branding. "
                "146 files, +36,035 / −4,212."
            ),
        },
        {
            "step": "2",
            "title": "Re-point the four moved anchors at the protocol crate — done",
            "detail": (
                "Followed upstream's structure rather than reshaping its RPC types: "
                "the enum variant and wire table now live in "
                "zeroclaw-rpc-proto/src/method.rs, the payload anchors in "
                "zeroclaw-rpc-proto/src/types.rs, and SessionToolsResult is defined "
                "in the protocol crate with a catalog entry, matching upstream's own "
                "rule that plain wire data lives in the protocol crate. The runtime "
                "re-exports the proto types, so the dispatcher resolves it unchanged."
            ),
        },
        {
            "step": "3",
            "title": "Add the contract arm and the catalog entry — done",
            "detail": (
                "The part no anchor count finds: a Method::contract arm for "
                "SessionTools (the match is arm-complete) and SessionToolsResult in "
                "the proto schema catalog (the catalog test is exclusive). Both are "
                "in, and the proto crate's 25 tests pass — including the exclusivity "
                "test that would otherwise fail."
            ),
        },
        {
            "step": "4",
            "title": "Re-pin release.json — done",
            "detail": (
                "upstreamCommit is now 2c0a8c263 and the version moved to "
                "0.9.0-enact.1, which makes the documented core-match check pass "
                "again instead of failing as it did before the sync."
            ),
        },
        {
            "step": "5",
            "title": "Re-run the whole gate — done",
            "detail": (
                "Overlay gate (35 tests), prepare(), a release build (5m 30s, no "
                "warnings), probe_native.py (24 checks), the web tests, and the "
                "cargo sweep over seven crates. The sweep failed three targets; a "
                "control run against a pristine upstream/master worktree sorted "
                "the five failures into three inherited and two the fork's own. "
                "Both fork failures were defects in the consolidated families. "
                "Widening the sweep to the channels crate found three more, also "
                "the fork's own and also pre-existing. All five are fixed and "
                "gated. The sweep now fails exactly what pristine upstream fails "
                "on this machine."
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
        "Upstream's Quality Gate still does not run in the fork: ci.yml triggers on pull_request to master, and the fork's default branch is enact/branding. The merge brought a new gate inside it (cargo generate openrpc --check). Retargeting it is a decision about CI minutes, so it is left to the owner.",
        "The native build workflow is still manual only (workflow_dispatch), so no PR is gated by a native build automatically.",
        "The prepared tree's OpenRPC document is stale by exactly the session/tools method. The tracked document stays upstream's so upstream's own --check stays green, and the book is not part of the shipped release artifact.",
        "The 0.9.0-enact.1 distribution has not been cut or published. The published 0.8.7-enact.1 release is untouched.",
        "Three cargo tests still fail on this machine — two relay::local_dial_tests cases that cannot stall a macOS loopback connect, and one order-dependent model-routing case. All three fail the same way on a pristine upstream/master worktree, and the files involved are byte-identical to upstream.",
        "One upstream desktop test failed once on ubuntu-22.04 in the fork's Desktop App Check and passed on re-run. Upstream's own CI never runs that crate, so the fork is where this test is seen at all.",
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
        "core_matches": git_diff_is_clean("upstream/master", cwd=AGENT),
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
