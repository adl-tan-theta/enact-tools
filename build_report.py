#!/usr/bin/env python3
"""Generate the enact-tools comparison HTML report.

Sources (all local, cloned under ./research):
  - research/oh-my-pi        github.com/can1357/oh-my-pi
  - research/lean-ctx        github.com/yvgude/lean-ctx
  - ../enact-agent           enact-agent (zeroclaw fork) - read only
  - zeroclaw-tools-operations.csv  (enact build; overlays/enact/zeroclaw-tools-operations.csv
                                   is the variant carrying the real `compiled_in_enact` flags)
"""
import csv
import json
import os
import sys
from collections import defaultdict, OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from enact_paths import overlay_csv  # noqa: E402

CSV_MAIN = os.path.join(ROOT, "zeroclaw-tools-operations.csv")
CSV_OVERLAY = str(overlay_csv())

# ---------------------------------------------------------------- load baseline
rows = list(csv.DictReader(open(CSV_MAIN)))
overlay = {r["tool_name"]: r for r in csv.DictReader(open(CSV_OVERLAY))}

tools = OrderedDict()
for r in rows:
    t = tools.setdefault(
        r["tool_name"],
        {
            "name": r["tool_name"],
            "tier": r["tier"],
            "compilation": r["compilation"],
            "source": r["source_file"],
            "ops": [],
            "disabled": overlay.get(r["tool_name"], {}).get("compiled_in_enact", "").lower() != "true",
        },
    )
    t["ops"].append(r["operation"])

# ------------------------------------------------- curated verdict per tool
# verdict, omp, lcx, note
V = {
    # --- Tier 1 core -------------------------------------------------------
    "shell":        ("KEEP", "bash", "ctx_shell", "Local-first execution boundary; already under shell policy + sandbox + receipts."),
    "file_read":    ("ENHANCE", "read", "ctx_read", "Add read modes (signatures/outline/diff/anchored) so orientation does not cost whole files."),
    "file_write":   ("KEEP", "write", "ctx_write", "Fine as-is."),
    "file_edit":    ("ENHANCE", "edit", "ctx_patch", "Move to hash-anchored edits with stale-anchor conflict detection."),
    "glob_search":  ("KEEP", "glob", "ctx_files", "Fine as-is."),
    "content_search": ("ENHANCE", "grep", "ctx_search", "Add semantic + symbol search modes; keep regex default."),
    "git_operations": ("MERGE", "-", "ctx_git_read", "13 actions already enum-backed; keep as one tool with action enum."),
    "memory_store": ("MERGE", "retain", "ctx_knowledge", "Merge memory_* family into one action-enum tool."),
    "memory_recall": ("MERGE", "recall", "ctx_knowledge", "Merge into `memory` action=recall."),
    "memory_forget": ("MERGE", "memory_edit", "ctx_memory", "Merge into `memory` action=forget."),
    "memory_export": ("MERGE", "-", "ctx_knowledge", "Merge into `memory` action=export."),
    "memory_purge": ("MERGE", "-", "-", "Merge into `memory` action=purge."),
    "web_fetch":    ("ENHANCE", "-", "ctx_url_read", "Add compression + SSRF guard parity with ctx_url_read."),
    # --- Tier 2 host --------------------------------------------------------
    "cron_add":     ("MERGE", "-", "ctx_session", "Merge cron_* + schedule into one `cron` tool with action enum."),
    "cron_list":    ("MERGE", "-", "ctx_session", "Merge into `cron` action=list."),
    "cron_remove":  ("MERGE", "-", "-", "Merge into `cron` action=remove."),
    "cron_update":  ("MERGE", "-", "-", "Merge into `cron` action=update."),
    "cron_run":     ("MERGE", "-", "-", "Merge into `cron` action=run."),
    "cron_runs":    ("MERGE", "-", "-", "Merge into `cron` action=runs."),
    "schedule":     ("MERGE", "-", "ctx_session", "Merge into `cron` action=once/recurring."),
    "spawn_subagent": ("KEEP", "task", "ctx_agent", "Strongest delegation primitive in the set; keep."),
    "delegate":     ("MERGE", "task", "ctx_work_graph", "Merge delegate + a2a_* into one `agents` action-enum tool."),
    "send_message_to_peer": ("MERGE", "wait", "ctx_share", "Merge into `agents` action=message."),
    "model_switch": ("MERGE", "-", "-", "Merge model_switch + model_routing_config into one `model` tool."),
    "model_routing_config": ("MERGE", "-", "-", "Merge into `model` action=route_*."),
    "proxy_config": ("MERGE", "-", "-", "Merge into `model` action=proxy_* (or keep separate if proxy is a distinct operator concern)."),
    "ask_user":     ("KEEP", "ask", "-", "Channel-bridging primitive; keep."),
    "escalate_to_human": ("KEEP", "-", "-", "Unique to enact; keep."),
    "reaction":     ("MERGE", "-", "-", "Merge reaction + poll + channel_room into `channel` action enum."),
    "poll":         ("MERGE", "-", "-", "Merge into `channel` action=poll."),
    "channel_room": ("MERGE", "-", "-", "Merge into `channel` action=room_*."),
    "send_via":     ("KEEP", "-", "-", "Outbound channel send; keep."),
    "git_forge":    ("MERGE", "github", "ctx_git_read", "Merge git_forge + git_operations into `git` action enum; adopt OMP unified GitHub CLI surface."),
    "sessions_current": ("MERGE", "-", "ctx_session", "Merge sessions_* into one `sessions` action-enum tool."),
    "sessions_list": ("MERGE", "-", "ctx_session", "Merge into `sessions` action=list."),
    "sessions_history": ("MERGE", "-", "ctx_session", "Merge into `sessions` action=history."),
    "sessions_send": ("MERGE", "-", "-", "Deprecated legacy append; merge or drop in favour of agents action=message."),
    "sop_list":     ("MERGE", "-", "-", "Merge sop_* into one `sop` action-enum tool."),
    "sop_execute":  ("MERGE", "-", "-", "Merge into `sop` action=execute."),
    "sop_advance":  ("MERGE", "-", "-", "Merge into `sop` action=advance."),
    "sop_approve":  ("MERGE", "-", "-", "Merge into `sop` action=approve."),
    "sop_status":   ("MERGE", "-", "-", "Merge into `sop` action=status."),
    "sop_workshop": ("MERGE", "-", "-", "Merge into `sop` action=workshop_*."),
    "read_skill":   ("ENHANCE", "manage_skill", "ctx_skillify", "Add skill authoring (learn/manage_skill) alongside reading."),
    "TodoWrite":    ("KEEP", "todo", "-", "Task tracker; keep name and lifecycle stable."),
    "canvas":       ("MERGE", "-", "-", "Merge canvas ops into action enum; keep shared-with-gateway store."),
    "deliver_file": ("KEEP", "-", "-", "ACP delivery; keep."),
    "llm_task":     ("KEEP", "eval", "ctx_execute", "Tool-less LLM subtask; keep."),
    "claude_code":  ("DISABLE", "-", "-", "Opt-in CLI adapter; stays feature-gated off in the Enact build."),
    "codex_cli":    ("DISABLE", "-", "-", "Opt-in CLI adapter; stays feature-gated off in the Enact build."),
    "gemini_cli":   ("DISABLE", "-", "-", "Opt-in CLI adapter; stays feature-gated off in the Enact build."),
    "opencode_cli": ("DISABLE", "-", "-", "Opt-in CLI adapter; stays feature-gated off in the Enact build."),
    "a2a_discover": ("MERGE", "-", "ctx_agent", "Merge a2a_* into `agents` action enum."),
    "a2a_send":     ("MERGE", "-", "ctx_agent", "Merge into `agents` action=a2a_send."),
    "a2a_get_task": ("MERGE", "-", "ctx_agent", "Merge into `agents` action=a2a_task."),
    "a2a_cancel":   ("MERGE", "-", "ctx_agent", "Merge into `agents` action=a2a_cancel."),
    "file_download": ("MERGE", "-", "ctx_url_read", "Merge into `web` action=download."),
    "security_ops": ("MERGE", "-", "-", "Merge security_ops actions into one tool (already enum-backed)."),
    "execute_pipeline": ("KEEP", "-", "ctx_call", "Keep; pair with tool_call escape hatch."),
    "tool_search":  ("ENHANCE", "find", "ctx_tools", "Upgrade to BM25 discovery over ALL tools + deferred schema load (OMP/lean-ctx pattern)."),
    "mcp_resources": ("MERGE", "-", "-", "Merge mcp_resources + mcp_prompts into `mcp` action enum."),
    "mcp_prompts":  ("MERGE", "-", "-", "Merge into `mcp` action=prompts_*."),
    # --- Tier 3 optional ----------------------------------------------------
    "calculator":   ("KEEP", "-", "-", "Tiny and harmless; keep."),
    "weather":      ("EXT", "-", "ctx_provider", "Externalise to skill package or HTTP skill."),
    "pushover":     ("EXT", "-", "-", "Externalise behind system.notify common path."),
    "screenshot":   ("ENHANCE", "computer", "-", "Add desktop AX-tree access (OMP `computer`) if desktop use matters."),
    "image_info":   ("KEEP", "-", "-", "Keep."),
    "browser_open": ("MERGE", "browser", "-", "Merge browser_* family into one `browser` action-enum tool (22 ops today)."),
    "browser":      ("MERGE", "browser", "-", "22 operations -> one tool with action enum."),
    "browser_delegate": ("MERGE", "-", "-", "Merge into `browser` action=delegate."),
    "text_browser": ("MERGE", "-", "ctx_url_read", "Merge into `web` action=text."),
    "http_request": ("MERGE", "-", "-", "Merge http_request + web_fetch + web_search_tool into `web` action enum."),
    "web_search_tool": ("MERGE", "-", "-", "Merge into `web` action=search."),
    "notion":       ("DISABLE", "-", "ctx_provider", "Opt-in SaaS; stays off. lean-ctx routes this through ctx_provider instead of a bespoke tool."),
    "jira":         ("DISABLE", "-", "ctx_provider", "Opt-in SaaS; stays off. Route via ctx_provider-style gateway."),
    "linkedin":     ("DISABLE", "-", "ctx_provider", "Opt-in SaaS; stays off."),
    "composio":     ("DISABLE", "-", "ctx_tools", "Opt-in; stays off. lean-ctx's ctx_tools is the general escape hatch instead."),
    "google_workspace": ("DISABLE", "-", "ctx_provider", "Opt-in; stays off."),
    "microsoft365": ("DISABLE", "-", "ctx_provider", "Opt-in; stays off."),
    "project_intel": ("DISABLE", "-", "-", "Opt-in; stays off."),
    "report_template": ("DISABLE", "-", "-", "Opt-in; stays off."),
    "claude_code_runner": ("DISABLE", "-", "-", "Opt-in; stays off."),
    "backup":       ("MERGE", "-", "-", "Merge backup actions into one tool (already enum-backed)."),
    "data_management": ("MERGE", "-", "ctx_cost", "Merge into `admin` action enum with retention/purge."),
    "cloud_ops":    ("MERGE", "-", "-", "Merge cloud_ops + cloud_patterns into `cloud` action enum."),
    "cloud_patterns": ("MERGE", "-", "-", "Merge into `cloud` action=patterns_*."),
    "image_gen":    ("KEEP", "generate_image", "-", "Parity with OMP generate_image."),
    "file_upload":  ("MERGE", "-", "-", "Merge file_upload + file_upload_bundle into `transfer` action enum."),
    "file_upload_bundle": ("MERGE", "-", "-", "Merge into `transfer` action=upload_bundle."),
    "discord_search": ("EXT", "-", "-", "Channel companion; externalise."),
    "email_search": ("MERGE", "-", "-", "Merge email_* into `email` action enum."),
    "email_read":   ("MERGE", "-", "-", "Merge into `email` action=read."),
    "knowledge":    ("MERGE", "-", "ctx_knowledge", "Merge 10 knowledge actions into one tool (already enum-backed)."),
}

# ---------------------------------------------------------------- new tools
# name, one-liner, source, priority, category, why
NEW = [
    ("compose", "One-call context assembly: ranked files + inline source for a task",
     "lean-ctx ctx_compose", "P0", "Context",
     "Replaces search->read->read chains. Highest-leverage single addition: it is the anti-pattern fix lean-ctx documents explicitly."),
    ("expand", "Retrieve archived / withheld tool output by handle",
     "lean-ctx ctx_expand", "P0", "Context",
     "Makes compression lossless. Without it, any token-saving tool destroys information the agent may need again."),
    ("read_modes", "Read modes on file_read: signatures, outline, diff, anchored, task",
     "lean-ctx ctx_read", "P0", "Context",
     "Turns whole-file reads into structural reads. Orientation stops costing a full file."),
    ("outline", "Syntax-aware symbol table for a file or directory (tree-sitter)",
     "lean-ctx ctx_outline", "P0", "Code intel",
     "Lets the agent orient in a repo without reading source bodies."),
    ("delta", "Only the lines changed since the last read of a file",
     "lean-ctx ctx_delta", "P1", "Context",
     "Cheap re-read replacement. Pairs with the read cache."),
    ("patch", "Hash-anchored edits with stale-anchor conflict detection",
     "lean-ctx ctx_patch", "P1", "Files",
     "Upgrade path for file_edit. Prevents silent lost-update edits."),
    ("compress", "Compress the read cache to reclaim token budget",
     "lean-ctx ctx_compress", "P1", "Context",
     "Explicit budget control rather than implicit trimming."),
    ("transcript_compact", "Deterministic transcript compaction with recoverable summary",
     "lean-ctx ctx_transcript_compact", "P1", "Context",
     "Supersedes blunt history trimming: system + fresh tail stay verbatim, older turns are recoverable."),
    ("radar", "Context budget breakdown: system prompt / messages / tools / reads / shell",
     "lean-ctx ctx_radar", "P1", "Observability",
     "Makes context spend inspectable. enact-agent has cost tracking but no context attribution."),
    ("metrics", "Cache hit rates and per-tool context savings",
     "lean-ctx ctx_metrics", "P2", "Observability",
     "Measures whether the context tooling is actually earning its place."),
    ("context_control", "Reversible overlays on delivered context: exclude / include / pin / evict",
     "lean-ctx ctx_control", "P1", "Context",
     "Field-theory control surface over what the model sees, scoped per call/session/project."),
    ("preload", "Cache task-relevant files and return an L-curve-optimised summary",
     "lean-ctx ctx_preload", "P2", "Context",
     "Proactive context warming before the model spends turns searching."),
    ("prefetch", "Warm the cache for blast-radius files under a token budget",
     "lean-ctx ctx_prefetch", "P2", "Context",
     "Same idea, scoped to a change set."),
    ("dedup", "Cross-file dedup hints for read output",
     "lean-ctx ctx_dedup", "P2", "Context",
     "Removes repeated boilerplate from multi-file reads."),
    ("graph", "File dependency graph, impact chains, Mermaid diagrams",
     "lean-ctx ctx_graph", "P1", "Code intel",
     "Structural blast-radius analysis that content search cannot give."),
    ("callgraph", "Function call edges: callers, callees, trace, risk",
     "lean-ctx ctx_callgraph", "P1", "Code intel",
     "The single best code-intelligence primitive; lean-ctx ships it in the 12-tool lazy core."),
    ("impact", "Blast-radius analysis for a proposed change",
     "lean-ctx ctx_impact", "P2", "Code intel",
     "Composes graph + callgraph for a concrete change set."),
    ("semantic_search", "Hybrid BM25 + dense + SPLADE retrieval with RRF merge",
     "lean-ctx ctx_search", "P1", "Search",
     "Semantic recall where regex fails. Complement, not replace, content_search."),
    ("ast_grep", "Structural code queries over tree-sitter grammars",
     "OMP ast_grep", "P0", "Code intel",
     "Pattern search that survives renames and formatting. Nothing in enact-agent matches this."),
    ("ast_edit", "Structural rewrites, previewed before apply",
     "OMP ast_edit", "P1", "Code intel",
     "Mechanical refactors across many files, with a review step."),
    ("lsp", "Diagnostics, navigation, symbols, renames, code actions",
     "OMP lsp", "P1", "Code intel",
     "Compiler-grade facts instead of guessing from grep."),
    ("debug", "Drive a DAP session: breakpoints, stepping, threads, stack, variables",
     "OMP debug", "P2", "Code intel",
     "Runtime state inspection. High value for debugging agents."),
    ("find", "Semantic grep: describe behaviour, get ranked files and line ranges",
     "OMP find", "P1", "Search",
     "Behaviour-first retrieval. OMP gates it behind a judge model."),
    ("eval", "Persistent Python / JavaScript cells with shared prelude",
     "OMP eval", "P2", "Runtime",
     "Real computation and scripting without shelling out."),
    ("checkpoint", "Mark conversation state for a later collapse-and-report",
     "OMP checkpoint", "P1", "Context",
     "Cheap rollback point for a long exploratory turn."),
    ("rewind", "Prune exploratory context, keep a concise report",
     "OMP rewind", "P1", "Context",
     "Sister tool of checkpoint. OMP auto-includes the pair: a one-sided tool strands the agent."),
    ("new_context", "Request a fresh context window, preserving notebook and branch history",
     "OMP new_context", "P1", "Context",
     "Explicit context reset instead of relying on auto-compaction."),
    ("context_notes", "Persistent experimental context notebook for the branch",
     "OMP context_notes", "P2", "Context",
     "Scratch space that survives a context reset."),
    ("learn", "Capture a reusable lesson, optionally promote it into a managed skill",
     "OMP learn", "P1", "Memory",
     "Closes the loop from a correction to a durable capability. enact-agent has SOP workshop but no lesson capture."),
    ("manage_skill", "Create, update, or delete an isolated managed skill",
     "OMP manage_skill", "P1", "Skills",
     "enact-agent implements skill_manage but deliberately does not register it in the agent registry."),
    ("security_scan", "Plan and run native security reviews over the diff",
     "OMP security_scan", "P2", "Security",
     "Proactive review. Complements the reactive security_ops tool."),
    ("github", "Unified GitHub CLI surface: repo, PR, issue, code search, Actions watch",
     "OMP github", "P1", "Git",
     "One interface instead of separate gh_* tools. Maps onto the existing git_forge family."),
    ("wait", "Block until the next background result, peer message, or steering interrupt",
     "OMP wait", "P1", "Coordination",
     "Lets the agent await async work instead of polling. act/lean-ctx both forbid polling."),
    ("computer", "Drive the host desktop: windows, screenshots, native input, AX tree, clipboard",
     "OMP computer", "P2", "Desktop",
     "Native app control with no browser DOM involved."),
    ("goal", "Create, inspect, or drop a durable goal record with token/time budget",
     "OMP goal", "P2", "Coordination",
     "enact-agent has a /goal command but no model-callable goal tool."),
    ("think", "External thinking channel, separate from the visible assistant message",
     "OMP think", "P3", "Reasoning",
     "Lets reasoning stay out of the user-visible transcript."),
    ("context_proof", "Machine-readable proof of what context was produced and whether it reproduces",
     "lean-ctx ctx_proof", "P3", "Observability",
     "Auditability for regulated deployments."),
    ("work_graph", "Project-scoped coordination graph across agents: claim, receipt, fuse, attribute",
     "lean-ctx ctx_work_graph", "P2", "Coordination",
     "Multi-agent work accounting. Complements spawn_subagent / delegate."),
    ("tool_call", "Invoke any registered tool by name and arguments",
     "lean-ctx ctx_call", "P1", "Platform",
     "Universal escape hatch, so rarely-used tools need not sit in the schema at all."),
    ("context_package", "Portable session / summary / knowledge bundles for handoff",
     "lean-ctx ctx_package", "P2", "Session",
     "Cross-agent, cross-machine context transfer."),
    ("shadow_checkpoint", "Shadow git history of the agent's changes, isolated from project .git",
     "lean-ctx ctx_checkpoint", "P2", "Session",
     "Safe snapshot/restore that does not pollute the user's repository."),
    ("semantic_provider", "External context gateways: GitHub, GitLab, Jira, Postgres, MCP bridges",
     "lean-ctx ctx_provider", "P2", "Platform",
     "One gateway replacing N bespoke SaaS tools (the pattern for notion/jira/linkedin/etc)."),
    ("project_doc", "Documentation pages bound to code, with history",
     "lean-ctx ctx_doc", "P3", "Knowledge",
     "Docs and code versioned together."),
    ("semantic_project_tasks", "Project task board with claim / submit / verify / decide",
     "lean-ctx ctx_tasks", "P2", "Coordination",
     "External task system integration; Hive-gated in lean-ctx."),
]

# ------------------------------------------------------------ host-agnostic layers
# system, language, role, mcp_client, mcp_server, hooks, instructions, claude, codex, verdict, note
HOST_LAYERS = [
    ("enact-agent", "Rust", "agent runtime", "yes", "NO", "Rust trait only — no user script",
     "AGENTS.md", "via MCP", "via MCP", "GAP",
     "MCP client only. No server mode, so it cannot hand its tool set to another host yet."),
    ("jcode", "Rust", "agent harness", "yes", "no", "8 external-program hooks (docs/HOOKS.md)",
     "AGENTS.md + Harness API", "native (OAuth + MCP config interop)", "native (OAuth + config import)", "STRONG",
     "34 built-ins. Harness API = versioned NDJSON boundary for any UI — and it lets an EXTERNAL client inject a tool set via ConfigureTools { custom }."),
    ("goose (Block / AAIF)", "Rust", "agent", "yes", "no", "n/a",
     "YAML recipes", "reads ~/.claude/agents + ~/.claude/skills", "via MCP", "STRONG",
     "70+ MCP extensions. Imports Claude Desktop's MCP config on first run. Extensions are plain MCP servers — usable by any MCP client."),
    ("lean-ctx", "Rust", "context engine", "yes", "YES (51 tools)", "17 actions × 11 host dialects",
     "SKILL.md", "installs ~/.claude/settings.json hooks", "installs ~/.codex/hooks.json", "STRONG",
     "The reference implementation of a hook layer that spans Claude Code, Codex, Cursor, Windsurf, Gemini, Copilot, Kiro, Cline, Vibe."),
    ("oh-my-pi", "Rust + TS", "agent", "yes", "no", "TS modules in .omp/hooks/{pre,post}",
     "SKILL.md", "reads .claude/skills + .claude/tools", "reads ~/.codex/tools", "STRONG",
     "30 built-ins. 13 essential in the schema, the rest behind xd:// devices + BM25 search."),
    ("Serena", "Python", "MCP server", "n/a", "YES", "n/a",
     "n/a", "native (--context ide-assistant)", "native (--context codex)", "STRONG",
     "LSP-based semantic code retrieval + editing as one MCP server. Works in every MCP host; Codex needs a special context because it does not fully implement MCP."),
    ("OMX (oh-my-codex)", "Node/TS", "Codex orchestration", "yes (state plane)", "yes", "Codex-native hooks (.codex/hooks.json)",
     "AGENTS.md", "via AGENTS.md + MCP", "native", "STRONG",
     "Three-plane model: Codex executes, omx controls, MCP servers hold state. 25+ workflow skills, 32 agents."),
    ("Claude Code", "TS", "agent", "yes", "YES (claude mcp serve)", "settings.json hooks (documented)",
     "CLAUDE.md + AGENTS.md", "native", "via MCP", "REFERENCE",
     "The only host that can also serve its own tools as MCP. Has MCP Tool Search for deferred schemas."),
    ("Codex CLI", "Rust", "agent", "yes (partial)", "NO", ".codex/hooks.json + .rules policy files",
     "AGENTS.md", "via MCP", "native", "REFERENCE",
     "MCP client only, and does not fully implement the spec. No extension system beyond AGENTS.md + .rules."),
]

# The four-layer portability recipe
PORTABILITY = [
    ("1 · Tools", "Ship one MCP server",
     "MCP is the only substrate every host speaks. Claude Code can even serve its own tools (`claude mcp serve`); Codex cannot — so an MCP server is the only way to give Codex a tool set you control.",
     "enact-agent has no server mode today. This is the single highest-leverage change for the 'one system' goal."),
    ("2 · Tools, take two", "Or offer a tool-injection API",
     "jcode's Harness API exposes `ConfigureTools { enabled, disabled, custom }`: an external client registers its own tool implementations, the model calls them, and the runtime routes the call back down that client's connection. The custom tool is an execution adapter only — it never enters the shared registry, so hooks, telemetry, output limits and permission gates behave exactly as for built-ins.",
     "This is the richer alternative to MCP when you own the host: the tool implementations stay in your process, and the runtime keeps its safety model intact."),
    ("3 · Schema budget", "Expose search + call, not N schemas",
     "jcode collapses MCP servers into a fixed `mcp` / `mcp_search` / `mcp_call` surface with a 32-reference cap and a 6 000-token result budget; providers with native deferred loading get `defer_loading` instead. Claude Code has MCP Tool Search; oh-my-pi uses xd:// devices + BM25.",
     "enact-agent already has `tool_search` and `mcp_deferred` — extend the same idea to MCP servers."),
    ("4 · Behaviour", "Per-host hook dialects",
     "lean-ctx is the reference: 17 hook actions rendered into 11 host dialects, each installer writing that host's own config file. jcode keeps it simpler — eight external-program hooks, one command per event.",
     "Ship Claude Code `settings.json` and Codex `.codex/hooks.json` installers. Do not invent a new hook format."),
    ("5 · Instructions", "AGENTS.md + SKILL.md",
     "Codex reads AGENTS.md natively. Claude Code reads AGENTS.md only when no CLAUDE.md exists (v2.1.277+), or you put an `@path` import on line 1 of CLAUDE.md, or set project instructions to claude-md-and-agents-md.",
     "One AGENTS.md, one SKILL.md, imported by both. AGENTS.md is capped at 32 KiB by default. jcode, goose and oh-my-pi all already read these paths."),
    ("6 · Policy", "Degrade to each host's own rules",
     "Codex uses `.rules` files (allow / prompt / forbidden). Claude Code uses permissions in settings.json. They are not the same model and should not be unified.",
     "A shared tool must respect the host's policy rather than assume it. enact-agent's availability-vs-authorization split maps cleanly onto this."),
]

# jcode specifics
JCODE_TOOLS = [
    ("read", "Read a file with line numbers, offset/limit"),
    ("write", "Create or overwrite a file"),
    ("edit", "Exact string replacement; also absorbs the old `multiedit`"),
    ("apply_patch", "Unified-diff / Codex-envelope patch application; absorbs the old `patch`"),
    ("bash", "Shell execution"),
    ("agentgrep", "Search with modes: grep (default), find (file names), outline (one file's structure), trace (relationship DSL)"),
    ("bash / bg", "Move a long-running tool to the background, poll it"),
    ("batch", "Run several tool calls in one turn, optionally parallel"),
    ("codemode", "Opt-in: run model-written JS in a QuickJS sandbox that can call any session tool"),
    ("memory", "Semantic memory graph: remember, recall, search, list, forget, tag, link, related"),
    ("session_search", "Search past session transcripts"),
    ("conversation_search", "Search the current conversation history"),
    ("swarm", "Multi-agent coordination — impl `CommunicateTool`"),
    ("skill_manage", "Load, list, reload and read skills"),
    ("todo", "Todo list with phases, lanes and dependencies"),
    ("browser", "Browser automation"),
    ("macos_computer_use", "Native macOS desktop control (macOS only)"),
    ("open", "Open a file, URL or app"),
    ("webfetch", "HTTP fetch a URL"),
    ("websearch", "Web search (DDG / Bing / SearXNG / Kagi / custom)"),
    ("compile_remote", "Remote compile and verify"),
    ("schedule", "Ambient and background scheduling"),
    ("gmail", "Gmail access"),
    ("calendar", "Calendar access"),
    ("panel", "Render into the main panel"),
    ("side_panel", "Render into the side panel"),
    ("applet", "Mount declarative native UI into the session (desktop only)"),
    ("user_response", "Inline user-response UI (desktop only)"),
    ("selfdev", "Self-development mode"),
    ("desktop_selfdev", "Desktop self-development"),
    ("jcode_docs", "Query jcode's own bundled documentation"),
    ("integration_tools", "Opt-in: integration and app catalog"),
    ("maintainer_feedback", "Submit maintainer feedback"),
    ("mcp", "MCP management — connect, disconnect, reload, list servers, action=call"),
    ("mcp__<server>__<tool>", "Per-server proxy tools, registered dynamically"),
]

# jcode's external-program hooks (docs/HOOKS.md)
JCODE_HOOKS = [
    ("pre_tool", "Before a tool call", "Gate — may block the call"),
    ("pre_tool_transform", "Before a tool call", "Transformer — may rewrite the arguments"),
    ("post_tool", "After a tool call", "Observer — sees the result"),
    ("post_tool_feedback", "After a successful tool call", "Feeds stdout back into the tool result — the linter/checker loop"),
    ("turn_start", "Start of a turn", "Observer"),
    ("turn_end", "End of a turn", "Observer"),
    ("session_start", "Session opens", "Observer"),
    ("session_end", "Session closes", "Observer"),
]

JCODE_FACTS = [
    ("Language / licence", "Rust (91.6% of the repo) · MIT · ~21k stars · single native binary, no Node or Python runtime"),
    ("Registered tools", "34 built-ins (27 base + 4 per-session + the `mcp` family + 2 desktop-only), plus dynamically registered `mcp__<server>__<tool>` proxies"),
    ("Not registered", "`ls`, `glob`, `grep`, `subagent`, `goal`, `plan`, `rewind`, `checkpoint` are NOT model-callable tools. `ls` and `grep` survive only as alias names; the `acp` and `minimal` tool profiles still list `ls`, which is a dangling reference. Rewind is a Harness API request, not a tool."),
    ("Harness API", "Stable, versioned client API over a Unix socket, spoken as NDJSON. `API_VERSION_MAJOR` 1 / `API_VERSION_MINOR` 11. Every frame carries `v`; clients must ignore unknown fields and skip unknown event kinds. Explicitly the public boundary between the harness and any UI (TUI, desktop, web, scripts), and deliberately smaller than the internal `jcode-protocol`."),
    ("★ External tool injection", "`ApiRequest::ConfigureTools { session_id, tools: ToolConfiguration }` carries `enabled`, `disabled` and `custom: Vec<SessionToolDefinition>`. A custom tool may override a built-in of the same name. The model calls it, the server emits a `ToolCall` event down the client's own connection, the client replies with `ToolResult` (120 s deadline). This is a complete, versioned contract for handing a tool set to a runtime from outside it."),
    ("★ Injected tools keep builtin semantics", "A custom tool is an \"execution adapter only, never installed in the shared registry\" — so hooks, telemetry, output limits and permission gates behave exactly as they do for built-ins."),
    ("External-program hooks", "Eight hook keys in `docs/HOOKS.md` — `pre_tool`, `pre_tool_transform`, `post_tool`, `post_tool_feedback`, `turn_start`, `turn_end`, `session_start`, `session_end`. Each is a command string or array; observers run in order, gates run sequentially and the first block wins. `post_tool_feedback` appends its stdout to the tool result, which is how linters and checkers feed findings back to the model."),
    ("MCP config interop", "Project precedence: `.jcode/mcp.json` → `.mcp.json` (Claude Code) → `.claude/mcp.json`. Claude Code is a LIVE source (`~/.claude.json` and `~/.claude/mcp.json`) and is never copied. Codex is a one-time import from `~/.codex/config.toml` `[mcp_servers.*]`, and only while `~/.jcode/mcp.json` does not exist — the stated reason is that persisting a live source would resurrect deleted servers and duplicate inline secrets."),
    ("Server preference", "Runnable wins. A remote twin of a working local stdio server does not overwrite it, because a remote twin usually needs a separate login. A broken higher-precedence entry does not shadow a working one."),
    ("Schema bloat control", "Three layers: provider-native deferred loading (`defer_loading` + `cache_control`) where supported; a fixed `mcp` / `mcp_search` / `mcp_call` surface elsewhere; and transcript announcement for tools that arrive late. `mcp_search` caps at 32 tool references under a 6 000-token budget, drops description-only matches once a name matches, and trims descriptions before dropping schemas."),
    ("Prompt-cache safety", "The tool list is locked after the first request. Exactly ONE deliberate rebuild is permitted, latched by a one-shot guard that is deliberately NOT re-armed. Definitions are sorted by name because ordering is a cache requirement. An AGENTS.md snapshot keeps the cacheable prefix stable when a tool edits it mid-session."),
    ("Advertise-early", "Proxy tools are registered from the on-disk schema cache before connections settle, so the first locked snapshot already contains MCP tools and the intentional cache miss can be avoided entirely."),
    ("Tool profiles", "`full` (default) | `acp` | `minimal` | `none`, plus explicit allow/deny lists, `disable_base_tools` and `mcp_tools = auto|eager|deferred`. Deny beats allow; `disabled: [\"mcp\"]` disables every MCP tool at once."),
    ("Canonical alias table", "`resolve_tool_name()` maps every host's vocabulary onto one internal name — `Bash`, `file_grep`, `shell_exec`, `functions.bash`, `todoread`, `multiedit`, `patch`, `communicate` — with a matching provider-side reverse map."),
    ("Swarm", "One tool (`communicate`, exposed as `swarm`). The server coordinates agents in the same repo: a `FileTouch` bus event detects contention and emits a `FileConflict` notification plus a soft interrupt to BOTH parties. Detection and notification only — no automatic merge; cross-agent write serialization is a process-local mutex."),
    ("Memory graph", "A typed graph, not a key-value store: weighted edges, tag and cluster nodes, and `supersede` edges. Recall is link-traversal-capable (`related`, `link`, `tag`), so a memory can be found through its relationships and not only by similarity."),
    ("Providers", "Anthropic (OAuth), OpenAI / Codex OAuth, Gemini, Copilot, OpenRouter, Antigravity, Bedrock, Cursor, Grok Build, plus a large OpenAI-compatible catalog. Anthropic OAuth beta headers deliberately do NOT claim `claude-code`."),
    ("Skills & extensions", "Skills are Markdown + YAML frontmatter with `allowed-tools`, discovered from `.jcode/skills`, `.claude/skills` and `.agents/skills`, invoked as `/name`, overlaid per session at read time. Applets mount declarative native UI. Codemode is a QuickJS sandbox that can call any session tool."),
]


# ------------------------------------------------------------ hook comparison
HOOK_ROWS = [
    # capability, enact, omp, lcx, recommendation
    ("User-writable hook scripts",            "no (Rust trait only)", "yes (TS/JS modules)", "yes (JSON/TOML installers)", "BLOCKER"),
    ("Hook discovery location",               "-",                    ".omp/hooks/{pre,post}/*.ts", "~/.claude/settings.json + 10 other hosts", "BLOCKER"),
    ("Pre-tool-call block",                   "yes",                 "yes",                 "yes", "ok"),
    ("Pre-tool-call rewrite of args",         "yes",                 "yes",                 "yes", "ok"),
    ("Post-tool-call output rewrite",         "no",                  "yes",                 "yes (governor, read-dedup)", "ADD"),
    ("Cancel / deny a call",                  "yes (Cancel)",        "yes ({block:true})",   "yes (deny/rights/protected)", "ok"),
    ("Inject context before the model call",  "yes (before_llm_call)", "yes (additionalContext)", "yes (additionalContext)", "ok"),
    ("Trusted vs untrusted context split",    "no",                  "yes (documented)",     "partial", "ADD"),
    ("Session start / end events",            "yes",                 "yes",                 "yes", "ok"),
    ("Pre-compaction / post-compaction",      "no",                  "yes",                 "yes", "ADD"),
    ("Turn / agent start / end events",       "partial (llm_input/output)", "yes",          "partial", "ok"),
    ("Subagent spawn interception",           "no",                  "yes",                 "no", "ADD"),
    ("Provider request/response interception","no",                  "yes",                 "no", "ADD"),
    ("Prompt / message rewriting",            "partial (prompt_build)", "yes (context chain)", "partial", "ok"),
    ("Channel message interception",          "yes",                 "no",                  "no", "KEEP"),
    ("Heartbeat / tick event",                "yes",                 "no",                  "no", "KEEP"),
    ("Hook execution budget / timeout",       "no",                  "yes (30 s)",           "yes (2 s / 15 s)", "ADD"),
    ("Fail-open vs fail-closed semantics",    "n/a",                 "fail-closed on throw", "fail-open, fail-closed on policy", "ADD"),
    ("Hook ordering / conflict rules",        "priority ordering",   "documented per event", "profile-driven", "ok"),
    ("Panic isolation",                       "yes",                 "no",                  "no", "KEEP"),
    ("Correlation identity across phases",    "yes (ToolCallHookContext)", "no",          "n/a", "KEEP"),
    ("Abandonment / release signal",          "yes (on_tool_call_abandoned)", "no",    "no", "KEEP"),
    ("Multi-host dialect support",            "no",                  "no",                  "yes (11 hosts)", "P2"),
    ("Plugin hook capability",                "no (PluginCapability has no Hook)", "yes (extension API)", "n/a", "ADD"),
    ("Hook configuration docs page",          "no",                  "yes (docs/hooks.md)",  "yes (PROTECTED-HOOKS.md)", "ADD"),
]

# ----------------------------------------------------------- merge families
MERGE_FAMILIES = [
    ("cron",     ["cron_add","cron_list","cron_remove","cron_update","cron_run","cron_runs","schedule"], 7, 15),
    ("sop",      ["sop_list","sop_execute","sop_advance","sop_approve","sop_status","sop_workshop"], 6, 13),
    ("memory",   ["memory_store","memory_recall","memory_forget","memory_export","memory_purge"], 5, 5),
    ("a2a",      ["a2a_discover","a2a_send","a2a_get_task","a2a_cancel"], 4, 4),
    ("sessions", ["sessions_current","sessions_list","sessions_history","sessions_send"], 4, 4),
    ("model",    ["model_switch","model_routing_config"], 2, 11),
    ("mcp",      ["mcp_resources","mcp_prompts"], 2, 4),
    ("cloud",    ["cloud_ops","cloud_patterns"], 2, 6),
    ("file_uploads", ["file_upload","file_upload_bundle"], 2, 2),
    ("email",    ["email_search","email_read"], 2, 2),
]

VERDICT_ORDER = ["ADD", "KEEP", "ENHANCE", "MERGE", "EXT", "DISABLE"]

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

# ------------------------------------------------------------------- counts
disabled = [t for t in tools.values() if t["disabled"]]
enabled = [t for t in tools.values() if not t["disabled"]]
verdict_counts = defaultdict(int)
for t in tools.values():
    verdict_counts[V.get(t["name"], ("KEEP",))[0]] += 1
for n in NEW:
    verdict_counts["ADD"] += 1

merged_tool_count = sum(f[2] for f in MERGE_FAMILIES)
ops_absorbed = sum(f[3] for f in MERGE_FAMILIES)

data = {
    "tools": list(tools.values()),
    "verdicts": {t["name"]: V.get(t["name"], ("KEEP", "-", "-", "")) for t in tools.values()},
    "new": NEW,
    "hooks": HOOK_ROWS,
    "merges": MERGE_FAMILIES,
    "host_layers": HOST_LAYERS,
    "portability": PORTABILITY,
    "jcode_tools": JCODE_TOOLS,
    "jcode_facts": JCODE_FACTS,
    "jcode_hooks": JCODE_HOOKS,
    "stats": {
        "total_tools": len(tools),
        "total_ops": len(rows),
        "enabled_tools": len(enabled),
        "disabled_tools": len(disabled),
        "enabled_ops": len(rows) - sum(len(t["ops"]) for t in disabled),
        "disabled_ops": sum(len(t["ops"]) for t in disabled),
        "merged_tool_count": merged_tool_count,
        "ops_absorbed": ops_absorbed,
        "post_merge_tools": len(tools) - merged_tool_count + len(MERGE_FAMILIES),
        "verdict_counts": dict(verdict_counts),
        "omp_tools": 30,
        "omp_hidden": 3,
        "omp_essential": 13,
        "lcx_public": 51,
        "lcx_core": 12,
        "lcx_consolidated": 35,
        "lcx_registry": 82,
    },
}

with open(os.path.join(ROOT, "data.json"), "w") as f:
    json.dump(data, f, indent=1)

print("tools:", len(tools), "ops:", len(rows))
print("disabled tools:", len(disabled), "disabled ops:", sum(len(t['ops']) for t in disabled))
print("new tools proposed:", len(NEW))
print("merged families:", len(MERGE_FAMILIES), "tools merged:", merged_tool_count)
print("post-merge surface:", data["stats"]["post_merge_tools"])
print("verdicts:", dict(verdict_counts))
