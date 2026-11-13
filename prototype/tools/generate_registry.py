#!/usr/bin/env python3
"""Generate the canonical tool registry from enact-agent's real tool inventory.

Source of truth:
  - zeroclaw-tools-operations.csv            (109 tools / 244 operations)
  - enact-agent/overlays/enact/...csv        (the real `compiled_in_enact` flags)

Output:
  - data/registry.generated.json              (the canonical registry)

The canonical registry is the *consolidated* surface: sibling families collapse
into one tool with a typed `action` enum, so 109 tool names become 83 without
losing a single operation.

Two traps this generator is careful about:

1. `zeroclaw-tools-operations.csv` carries a `compiled_in_enact_all_tools`
   column that is `TRUE` on every single row. It is useless. The real flags
   live in the Enact overlay CSV's `compiled_in_enact` column, where a tool
   that is compiled out is prefixed with `#` (e.g. `#notion`).

2. Sibling families share operation names (`cron_add.add` and `schedule.add`
   are both `add`). Collapsing on the bare operation name silently drops
   operations. Every action name is therefore derived to be unique inside its
   family, and the source (tool, operation) pair is preserved verbatim in
   `op_map` so nothing is lost.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, ".."))
from enact_paths import overlay_csv  # noqa: E402
from merge_map import MERGE_FAMILIES, canonical_for, family_of  # noqa: E402

CSV_MAIN = os.path.join(ROOT, "..", "zeroclaw-tools-operations.csv")
CSV_OVERLAY = str(overlay_csv())

# ---------------------------------------------------------------- descriptions
FAMILY_DESCRIPTIONS = {
    "cron": "Schedule and manage autonomous jobs, recurring schedules and one-shot timers.",
    "sop": "Run Standard Operating Procedures: list, execute, advance, approve and inspect runs.",
    "memory": "Long-term memory: store, recall, forget, export and purge facts.",
    "a2a": "Agent-to-agent protocol: discover peers, send messages, inspect and cancel tasks.",
    "sessions": "Inspect and steer agent sessions: current, list, history and send.",
    "model": "Control plane for model selection, routing rules and provider listing.",
    "mcp": "List and read resources and prompts exposed by connected MCP servers.",
    "cloud": "Cloud architecture advisory: IaC review, migration assessment, cost and patterns.",
    "file_upload": "Upload local files to a configured remote endpoint, single or bundled.",
    "email": "Search and read mail in a configured IMAP mailbox. Read-only.",
}

STANDALONE_DESCRIPTIONS = {
    "shell": "Execute a shell command in the workspace directory.",
    "file_read": "Read a workspace file with line numbers, optional offset and limit, or one of the read modes: signatures, outline, diff, anchored, task.",
    "compose": "Assemble the context for a task in one call: rank the workspace files by relevance and inline the best ones.",
    "expand": "Retrieve a tool output that was archived because it was too large for the conversation.",
    "ast_grep": "Search code by structure with an ast-grep pattern or syntax kind.",
    "ast_edit": "Rewrite code by structure, with a preview before anything is written.",
    "callgraph": "Show what calls a function and what it calls.",
    "graph": "Show the file-level dependency graph of the workspace.",
    "radar": "Report where the context window went: the per-source breakdown of the last request.",
    "file_write": "Write a workspace file, creating or overwriting it.",
    "file_edit": "Replace an exact string in a workspace file.",
    "glob_search": "List workspace files matching a glob pattern.",
    "content_search": "Regex-search the contents of workspace files.",
    "git_operations": "Structured git operations over the workspace repository.",
    "web_fetch": "Fetch a URL and return clean plain text.",
    "http_request": "Make an HTTP request to an allowlisted domain.",
    "web_search_tool": "Search the web and return results with citations.",
    "browser": "Drive a headless browser: navigate, inspect, act and capture.",
    "text_browser": "Render a web page as plain text.",
    "browser_open": "Open a URL in the browser session.",
    "browser_delegate": "Delegate a browser task to a sub-agent.",
    "calculator": "Evaluate an arithmetic expression.",
    "weather": "Look up current weather for a location.",
    "image_info": "Read image metadata: format, dimensions, size.",
    "screenshot": "Capture the screen.",
    "image_gen": "Generate an image from a prompt.",
    "file_download": "Download a remote file into the workspace.",
    "knowledge": "Knowledge graph of decisions, patterns, lessons and experts.",
    "security_ops": "Managed security operations: triage, runbooks and vulnerability parsing.",
    "tool_search": "Discover deferred tools by keyword without loading every schema.",
    "execute_pipeline": "Chain several tool calls as a pipeline.",
    "canvas": "Shared canvas store for rendered artifacts.",
    "TodoWrite": "Render and update the live task tracker.",
    "read_skill": "Load a skill's full instructions on demand.",
    "escalate_to_human": "Escalate to a human with structured urgency routing.",
    "ask_user": "Ask the active channel a question and wait for the reply.",
    "spawn_subagent": "Spawn an ephemeral child run that inherits the caller's identity.",
    "delegate": "Hand off work to a different configured agent.",
    "send_message_to_peer": "Send an agent-to-agent message to a peer session.",
    "backup": "Create, list, verify and restore shared data-directory backups.",
    "data_management": "Retention preview and storage statistics for the shared data directory.",
    "llm_task": "Run a prompt through a model with no tool access.",
    "deliver_file": "Deliver a workspace file to the client as an embedded resource.",
    "proxy_config": "Manage proxy settings and the process-wide runtime proxy.",
    "git_forge": "Operate a git forge (GitHub, Gitea) through the git channel.",
    "discord_search": "Search Discord message history.",
    "screenshot_image": "Capture the screen.",
    "reaction": "Add or remove a reaction on a message.",
    "channel_room": "Create a channel room and invite a user.",
    "a2a_discover": "Discover agent-to-agent peers.",
    "model_switch": "Switch the model for the current session.",
    "notion": "Read and write Notion pages and databases.",
    "jira": "Read and write Jira tickets.",
    "linkedin": "Read and write LinkedIn posts and profiles.",
    "composio": "Run Composio-connected app actions.",
    "microsoft365": "Microsoft 365 mail, calendar, OneDrive, SharePoint and Teams.",
    "google_workspace": "Google Workspace mail, calendar, Drive and Docs.",
    "project_intel": "Project intelligence: status reports, risk scans and effort estimates.",
    "report_template": "Render a report from a template.",
    "claude_code": "Drive the Claude Code CLI as a tool.",
    "claude_code_runner": "Run Claude Code as a background runner.",
    "codex_cli": "Drive the Codex CLI as a tool.",
    "gemini_cli": "Drive the Gemini CLI as a tool.",
    "opencode_cli": "Drive the OpenCode CLI as a tool.",
}

# Tools whose calls change state on disk or the network. The policy layer uses
# this to decide whether a host's `prompt` rule should apply.
DESTRUCTIVE = {
    "file_write", "file_edit", "shell", "git_operations", "web_fetch",
    "http_request", "browser", "text_browser", "browser_open", "browser_delegate",
    "file_download", "file_upload", "image_gen", "screenshot", "backup",
    "data_management", "web_search_tool", "weather", "cron", "sop", "model",
    "proxy_config", "knowledge", "security_ops", "execute_pipeline", "canvas",
    "a2a", "sessions", "email", "cloud", "discord_search", "mcp",
    "notion", "jira", "linkedin", "composio", "microsoft365", "google_workspace",
    "project_intel", "report_template", "reaction", "channel_room",
    "claude_code", "claude_code_runner", "codex_cli", "gemini_cli", "opencode_cli",
    "git_forge", "delegate", "spawn_subagent", "send_message_to_peer",
}

# Extra per-tool JSON Schema properties for the tools the prototype executes.
CORE_SCHEMAS: dict[str, dict] = {
    "shell": {
        "command": {"type": "string", "description": "Shell command to run."},
        "cwd": {"type": "string", "description": "Working directory, relative to the workspace root."},
        "timeout_ms": {"type": "integer", "minimum": 1, "description": "Timeout in milliseconds."},
    },
    "file_read": {
        "path": {"type": "string", "description": "Path relative to the workspace root."},
        "offset": {"type": "integer", "minimum": 1, "description": "First line to read (1-indexed)."},
        "limit": {"type": "integer", "minimum": 1, "description": "Maximum number of lines."},
        "anchor": {"type": "string", "description": "The text to find, for the read_anchored action."},
        "task": {"type": "string", "description": "What to look for, for the read_task action."},
        "base": {"type": "string", "description": "The previous text, for the read_diff action."},
        "context": {"type": "integer", "minimum": 0, "description": "Lines of context around a match."},
    },
    "file_write": {
        "path": {"type": "string", "description": "Path relative to the workspace root."},
        "content": {"type": "string", "description": "Full file content to write."},
    },
    "file_edit": {
        "path": {"type": "string", "description": "Path relative to the workspace root."},
        "old_string": {"type": "string", "description": "Exact text to replace."},
        "new_string": {"type": "string", "description": "Replacement text."},
    },
    "glob_search": {
        "pattern": {"type": "string", "description": "Glob pattern, e.g. `**/*.rs`."},
        "path": {"type": "string", "description": "Subtree to search, relative to the workspace root."},
    },
    "content_search": {
        "pattern": {"type": "string", "description": "Regular expression to search for."},
        "path": {"type": "string", "description": "Subtree to search, relative to the workspace root."},
        "max_results": {"type": "integer", "minimum": 1, "description": "Cap on matches returned."},
    },
    "git_operations": {
        "action": {"type": "string", "description": "Git operation to perform."},
    },
}

# Tier / compilation ladders, least restrictive first. A merged family takes the
# most restrictive member's value, so folding never widens a tool's exposure.
TIER_ORDER = ["Core", "Host", "Optional"]
COMPILATION_ORDER = ["Always", "External"]


def action_schema(operations: list[str], required: bool = True) -> dict:
    """A typed `action` enum — the shape lean-ctx standardised on."""
    return {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": operations,
                "description": "Operation to perform.",
            }
        },
        "required": ["action"] if required else [],
        "additionalProperties": True,
    }


def load_rows() -> list[dict]:
    with open(CSV_MAIN, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"no rows in {CSV_MAIN}")
    return rows


def disabled_map() -> dict[str, bool]:
    """tool_name -> compiled out of the Enact build.

    In the overlay CSV a compiled-out tool is written with a leading `#`
    (e.g. `#notion`), which is the only place the real flag lives.
    """
    out: dict[str, bool] = {}
    if not os.path.exists(CSV_OVERLAY):
        raise SystemExit(f"overlay inventory missing: {CSV_OVERLAY}")
    with open(CSV_OVERLAY, newline="") as fh:
        for row in csv.DictReader(fh):
            name = row["tool_name"].strip()
            flag = row.get("compiled_in_enact", "").strip().lower()
            compiled_out = name.startswith("#") or flag != "true"
            name = name.lstrip("#")
            # A tool is compiled out when *any* of its operations is compiled out.
            out[name] = out.get(name, False) or compiled_out
    return out


def _discriminator(tool: str, op: str) -> str:
    """A short prefix that tells two colliding operations apart.

    `cron_add.add` and `schedule.add` both want to be `add`; the tool name
    minus the operation name is the natural discriminator (`cron` vs
    `schedule`). Where the tool name does not end with the operation, the whole
    tool name is used.
    """
    if tool.endswith("_" + op):
        return tool[: -(len(op) + 1)]
    return tool


def build_actions(members: list[str], ops_by_tool: dict[str, list[str]]) -> dict[tuple[str, str], str]:
    """Assign a unique action name to every (tool, operation) pair of a family.

    An operation name that is unique inside the family is kept verbatim; a name
    shared by several tools is prefixed with a discriminator derived from the
    source tool. The result is a bijection: no operation is dropped and no two
    operations share a name.
    """
    pairs = [(tool, op) for tool in members for op in ops_by_tool.get(tool, [])]
    by_op: dict[str, list[str]] = {}
    for tool, op in pairs:
        by_op.setdefault(op, []).append(tool)

    out: dict[tuple[str, str], str] = {}
    used: set[str] = set()
    for tool, op in pairs:
        if len(by_op[op]) == 1:
            out[(tool, op)] = op
    # shared names get a discriminator
    for tool, op in pairs:
        if len(by_op[op]) == 1:
            continue
        base = _discriminator(tool, op)
        candidate = f"{base}_{op}"
        if candidate in used:
            candidate = f"{tool}_{op}"
        out[(tool, op)] = candidate
    for tool, op in pairs:
        used.add(out[(tool, op)])
    dupes = [n for n in used if sum(1 for p in out.values() if p == n) > 1]
    if dupes:
        raise SystemExit(f"action name collision in family {members}: {dupes}")
    return out


def build() -> dict:
    rows = load_rows()
    dis = disabled_map()

    # group operations per source tool, preserving CSV order
    ops_by_tool: "OrderedDict[str, list[str]]" = OrderedDict()
    tier_by_tool: dict[str, str] = {}
    comp_by_tool: dict[str, str] = {}
    src_by_tool: dict[str, str] = {}
    for row in rows:
        name = row["tool_name"]
        ops_by_tool.setdefault(name, [])
        if row["operation"] not in ops_by_tool[name]:
            ops_by_tool[name].append(row["operation"])
        tier_by_tool.setdefault(name, row["tier"])
        comp_by_tool.setdefault(name, row["compilation"])
        src_by_tool.setdefault(name, row["source_file"])

    # action names per family (or per standalone tool)
    family_members = {fam: list(members) for fam, members in MERGE_FAMILIES.items()}
    actions: dict[tuple[str, str], str] = {}
    for fam, members in family_members.items():
        actions.update(build_actions(members, ops_by_tool))
    for tool, ops in ops_by_tool.items():
        if tool in family_members.get(family_of(tool) or "", []):
            continue
        for op in ops:
            actions[(tool, op)] = op

    # fold families together
    canon: "OrderedDict[str, dict]" = OrderedDict()
    for tool, ops in ops_by_tool.items():
        cname = canonical_for(tool)
        entry = canon.setdefault(
            cname,
            {
                "name": cname,
                "operations": [],
                "op_map": OrderedDict(),
                "sources": [],
                "tiers": [],
                "compilations": [],
                "source_files": [],
            },
        )
        for op in ops:
            action = actions[(tool, op)]
            if action not in entry["op_map"]:
                entry["operations"].append(action)
                entry["op_map"][action] = {
                    "tool": tool,
                    "operation": op,
                    "disabled": dis.get(tool, False),
                }
        if tool not in entry["sources"]:
            entry["sources"].append(tool)
        if src_by_tool[tool] not in entry["source_files"]:
            entry["source_files"].append(src_by_tool[tool])
        if tier_by_tool[tool] not in entry["tiers"]:
            entry["tiers"].append(tier_by_tool[tool])
        if comp_by_tool[tool] not in entry["compilations"]:
            entry["compilations"].append(comp_by_tool[tool])

    # names, descriptions, schemas
    tools = []
    for cname, entry in canon.items():
        fam = family_of(entry["sources"][0]) if len(entry["sources"]) > 1 else None
        ops = entry["operations"]
        if fam and fam in FAMILY_DESCRIPTIONS:
            desc = FAMILY_DESCRIPTIONS[fam]
        else:
            desc = STANDALONE_DESCRIPTIONS.get(cname, f"{cname.replace('_', ' ')}.")

        if cname in CORE_SCHEMAS:
            props = dict(CORE_SCHEMAS[cname])
            if len(ops) > 1:
                props["action"] = {
                    "type": "string",
                    "enum": ops,
                    "description": "Operation to perform.",
                }
            schema = {
                "type": "object",
                "properties": props,
                "required": [next(iter(CORE_SCHEMAS[cname]))],
                "additionalProperties": False,
            }
        elif len(ops) > 1:
            schema = action_schema(ops, required=True)
        else:
            schema = action_schema(ops, required=False)

        tier = max(entry["tiers"], key=lambda t: TIER_ORDER.index(t) if t in TIER_ORDER else 0)
        compilation = "External" if "External" in entry["compilations"] else "Always"
        if any(c.startswith("OptIn") for c in entry["compilations"]):
            compilation = next(c for c in entry["compilations"] if c.startswith("OptIn"))

        tools.append(
            {
                "name": cname,
                "description": desc,
                "parameters": schema,
                "operations": ops,
                "op_map": entry["op_map"],
                "merged_from": entry["sources"],
                "tier": tier,
                "compilation": compilation,
                "disabled": all(dis.get(t, False) for t in entry["sources"]),
                "destructive": cname in DESTRUCTIVE,
                "source_files": entry["source_files"],
            }
        )

    total_ops = sum(len(t["operations"]) for t in tools)
    return {
        "schema_version": 2,
        "generated_from": {
            "inventory_csv": "zeroclaw-tools-operations.csv",
            "overlay_csv": "overlays/enact/zeroclaw-tools-operations.csv",
        },
        "source_tool_count": len(ops_by_tool),
        "canonical_tool_count": len(tools),
        "operation_count": total_ops,
        "tools": tools,
    }


def main() -> None:
    data = build()
    out = os.path.join(ROOT, "data", "registry.generated.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"wrote {out}")
    print(f"  source tools   : {data['source_tool_count']}")
    print(f"  canonical tools: {data['canonical_tool_count']}")
    print(f"  operations     : {data['operation_count']}")
    disabled = [t["name"] for t in data["tools"] if t["disabled"]]
    print(f"  disabled tools : {len(disabled)} -> {', '.join(disabled)}")
    print(f"  disabled ops   : {sum(len(t['operations']) for t in data['tools'] if t['disabled'])}")


if __name__ == "__main__":
    main()
