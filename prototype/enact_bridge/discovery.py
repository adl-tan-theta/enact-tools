"""Search over the canonical registry.

Advertising 83 tool schemas to a host costs context. The bridge therefore
publishes a tiny surface by default — `mcp_search` and `mcp_call` — and lets
the model pull a schema only when it needs one. The budget mirrors what
jcode ships: at most 32 tool references per search and roughly a 6000-token
result ceiling.
"""
from __future__ import annotations

import re
from typing import Any

from . import aliases
from .model import Registry, Tool

MAX_SEARCH_TOOL_REFERENCES = 32
SEARCH_TOKEN_BUDGET = 6000
CHARS_PER_TOKEN = 4


STOP_WORDS = {
    "a", "an", "the", "to", "of", "in", "on", "for", "with", "and", "or", "is",
    "it", "its", "my", "me", "do", "can", "how", "what", "when", "where",
    "which", "that", "this", "by", "be", "as", "at", "from", "any", "some",
}


def _tokens(query: str) -> list[str]:
    tokens = [t for t in re.split(r"[^A-Za-z0-9_]+", query.lower()) if t]
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def _score(tool: Tool, query: str, words: list[str]) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    name = tool.name.lower()

    if name == query:
        score += 100
        matched.append("name==")
    elif name.startswith(query):
        score += 60
        matched.append("name^")
    elif query in name:
        score += 40
        matched.append("name~")

    name_hits = 0
    for word in words:
        if word and word in name:
            score += 20
            name_hits += 1
            matched.append(f"name:{word}")
        if word and word in tool.description.lower():
            score += 5
            matched.append(f"desc:{word}")
        if word and any(word in a.lower() for a in tool.operations):
            score += 6
            matched.append(f"action:{word}")
        if word and any(word in m.lower() for m in tool.merged_from):
            score += 4
            matched.append(f"alias:{word}")

    # Every word landing in the name is a much stronger signal than a scatter.
    if words and name_hits == len(words):
        score += 25
        matched.append("name:all")

    # A host vocabulary hit is a strong signal ("bash" -> shell).
    for host in aliases.HOSTS:
        for host_name, canon in aliases.HOST_ALIASES[host].items():
            if canon == tool.name and word_hit(host_name, words):
                score += 30
                matched.append(f"host:{host_name}")

    return score, matched


def word_hit(text: str, words: list[str]) -> bool:
    low = text.lower()
    return any(w and (w in low) for w in words)


def search(
    registry: Registry,
    query: str,
    limit: int = 8,
    include_disabled: bool = False,
    token_budget: int = SEARCH_TOKEN_BUDGET,
) -> dict[str, Any]:
    """Search the registry and return a budgeted list of tool references."""
    query = (query or "").strip()
    words = _tokens(query)
    pool = registry.tools if include_disabled else registry.enabled_tools()

    if not words:
        # No query: return the most privileged tools first.
        scored = []
        for tool in pool:
            bonus = {"Core": 30, "Host": 20, "Optional": 10}.get(tool.tier, 0)
            scored.append((bonus, [f"tier:{tool.tier}"], tool))
    else:
        scored = []
        for tool in pool:
            s, m = _score(tool, query.lower(), words)
            if s > 0:
                scored.append((s, m, tool))
        scored.sort(key=lambda x: (-x[0], x[2].name))

    results: list[dict[str, Any]] = []
    used = 0
    for score, matched, tool in scored:
        if len(results) >= min(limit, MAX_SEARCH_TOOL_REFERENCES):
            break
        entry = tool.summary()
        entry["score"] = score
        entry["matched_on"] = sorted(set(matched))
        cost = len(entry["description"]) // CHARS_PER_TOKEN + len(entry["actions"]) * 2 + 12
        if used + cost > token_budget and results:
            break
        used += cost
        results.append(entry)

    return {
        "query": query,
        "results": results,
        "matched": len(scored),
        "truncated": len(scored) > len(results),
        "token_estimate": used,
        "registry_tools": len(pool),
    }


def detail(registry: Registry, name: str) -> dict[str, Any] | None:
    """Full detail for one canonical tool, including its source trace."""
    tool = registry.get(name)
    if not tool:
        return None
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
        "actions": tool.actions,
        "operations": [
            {
                "action": op.action,
                "source_tool": op.tool,
                "source_operation": op.operation,
                "disabled": op.disabled,
            }
            for op in tool.op_list
        ],
        "tier": tool.tier,
        "compilation": tool.compilation,
        "destructive": tool.destructive,
        "merged_from": tool.merged_from,
        "source_files": tool.source_files,
        "host_names": aliases.host_names_for(tool.name),
    }
