"""Host vocabularies mapped onto canonical registry names.

Each host spells the same capability differently:

    Claude Code   Bash / Read / Write / Edit / Grep / Glob / WebFetch ...
    Codex CLI     shell / apply_patch / update_plan / view_image / web_search

The bridge never renames a host's own tools. It resolves a *host* name to the
*canonical* registry name so that a policy rule written in either vocabulary
can be evaluated against one registry. This mirrors jcode's
`resolve_tool_name()` approach.

MCP tools are addressed as `mcp__<server>__<tool>` by Claude Code and as
`<server>__<tool>` by Codex; both are unwrapped back to the bare tool name.
"""
from __future__ import annotations

import re

CLAUDE_CODE = "claude-code"
CODEX = "codex"
HOSTS = (CLAUDE_CODE, CODEX)

# Claude Code built-in tools -> canonical registry names.
CLAUDE_CODE_ALIASES: dict[str, str] = {
    "Bash": "shell",
    "BashOutput": "shell",
    "KillShell": "shell",
    "Read": "file_read",
    "Write": "file_write",
    "Edit": "file_edit",
    "NotebookEdit": "file_edit",
    "MultiEdit": "file_edit",
    "Grep": "content_search",
    "Glob": "glob_search",
    "WebFetch": "web_fetch",
    "WebSearch": "web_search_tool",
    "Task": "spawn_subagent",
    "Skill": "read_skill",
    "TodoWrite": "TodoWrite",
    "AskUserQuestion": "ask_user",
}

# Codex CLI built-in tools -> canonical registry names.
CODEX_ALIASES: dict[str, str] = {
    "shell": "shell",
    "local_shell": "shell",
    "container.exec": "shell",
    "apply_patch": "file_edit",
    "update_plan": "TodoWrite",
    "view_image": "image_info",
    "web_search": "web_search_tool",
}

HOST_ALIASES: dict[str, dict[str, str]] = {
    CLAUDE_CODE: CLAUDE_CODE_ALIASES,
    CODEX: CODEX_ALIASES,
}

# The two tools the bridge itself publishes to the MCP surface.
BRIDGE_TOOLS = ("mcp_search", "mcp_call")

_MCP_NAME_RE = re.compile(r"^(?:mcp__)?(?P<server>[A-Za-z0-9_.-]+?)__(?P<tool>[A-Za-z0-9_.-]+)$")


def split_mcp_name(name: str) -> tuple[str | None, str]:
    """Split `mcp__enact__mcp_call` into ("enact", "mcp_call")."""
    m = _MCP_NAME_RE.match(name)
    if not m:
        return None, name
    server, tool = m.group("server"), m.group("tool")
    # `mcp__` prefix consumed the first `__`; a plain `server__tool` has no prefix.
    if name.startswith("mcp__"):
        m2 = re.match(r"^mcp__(?P<server>[A-Za-z0-9_.-]+?)__(?P<tool>[A-Za-z0-9_.-]+)$", name)
        if m2:
            return m2.group("server"), m2.group("tool")
    return server, tool


def resolve(host: str, name: str) -> str | None:
    """Resolve a host tool name to a canonical registry name.

    Returns None when the host name has no canonical counterpart.
    """
    if not name:
        return None
    server, tool = split_mcp_name(name)
    if tool in BRIDGE_TOOLS:
        return tool
    aliases = HOST_ALIASES.get(host, {})
    if tool in aliases:
        return aliases[tool]
    if tool == name and name in aliases:
        return aliases[name]
    return None


def resolve_any(name: str) -> str | None:
    """Resolve against every known host vocabulary."""
    for host in HOSTS:
        hit = resolve(host, name)
        if hit:
            return hit
    return None


def host_names_for(canonical: str) -> dict[str, str]:
    """The reverse map: canonical name -> the name each host uses for it."""
    out: dict[str, str] = {}
    for host, aliases in HOST_ALIASES.items():
        for host_name, canon in aliases.items():
            if canon == canonical:
                out[host] = host_name
                break
    return out


def is_bridge_tool(name: str) -> bool:
    return name in BRIDGE_TOOLS
