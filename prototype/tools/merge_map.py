"""Sibling-family merge map: enact-agent's 109 tools → 83 canonical tools.

Each entry collapses a set of always-used-together sibling tools into one
canonical tool with a typed `action` enum. Every operation survives — only the
tool names change.

Mirrors the consolidation plan in the surface review (lean-ctx shipped the
same 82 → 35 move between 3.11.4 and 3.11.5, with legacy names kept as
forwarding aliases).
"""

# family -> (canonical tool name, [source tool names in CSV order])
MERGE_FAMILIES: dict[str, list[str]] = {
    "cron": [
        "cron_add", "cron_list", "cron_remove", "cron_update",
        "cron_run", "cron_runs", "schedule",
    ],
    "sop": [
        "sop_list", "sop_execute", "sop_advance", "sop_approve",
        "sop_status", "sop_workshop",
    ],
    "memory": [
        "memory_store", "memory_recall", "memory_forget",
        "memory_export", "memory_purge",
    ],
    "a2a": ["a2a_discover", "a2a_send", "a2a_get_task", "a2a_cancel"],
    "sessions": [
        "sessions_current", "sessions_list", "sessions_history", "sessions_send",
    ],
    "model": ["model_switch", "model_routing_config"],
    "mcp": ["mcp_resources", "mcp_prompts"],
    "cloud": ["cloud_ops", "cloud_patterns"],
    # NOT `file_upload`: the registry already has a tool by that name, and two
    # registry tools cannot share one name.
    "file_uploads": ["file_upload", "file_upload_bundle"],
    "email": ["email_search", "email_read"],
}

# Which tools are compiled out of the Enact build is NOT declared here: it is
# read from the overlay CSV (`#`-prefixed rows), which is the only place the
# real `compiled_in_enact` flag lives.

# Source tool -> canonical tool (the inverse of MERGE_FAMILIES).
TOOL_TO_CANONICAL: dict[str, str] = {}
for _fam, _members in MERGE_FAMILIES.items():
    for _member in _members:
        TOOL_TO_CANONICAL[_member] = _fam


def canonical_for(tool_name: str) -> str:
    """Map a source tool name to its canonical name (identity if standalone)."""
    return TOOL_TO_CANONICAL.get(tool_name, tool_name)


def family_of(tool_name: str) -> str | None:
    """Return the family a source tool was merged into, or None if standalone."""
    return TOOL_TO_CANONICAL.get(tool_name)
