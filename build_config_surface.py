#!/usr/bin/env python3
"""Extract the configuration surface from the built binary.

The binary owns the configuration schema: `zeroclaw config schema` prints the
same JSON Schema the gateway serves at `GET /api/config`. This script reads
that document and keeps the sections that govern the tool surface, so the
report can show real options — their types, defaults, enums and descriptions —
without carrying a megabyte of unrelated schema around.

Output: `config-surface.json`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import enact_paths

ROOT = os.path.dirname(os.path.abspath(__file__))
AGENT = str(enact_paths.enact_agent_dir() or os.path.join(os.path.dirname(ROOT), "enact-agent"))
BINARY = os.path.join(AGENT, "target/release/zeroclaw")
OUT = os.path.join(ROOT, "config-surface.json")

# The sections that decide how the tools behave, and what the agent may do.
SECTIONS = [
    ("tools", "Builtin tools", "Which tools exist, and which are optional."),
    ("shell_tool", "Shell tool", "How the shell tool is constrained and supervised."),
    ("browser", "Browser", "Backends, and the domains the browser may reach."),
    ("cron", "Cron", "How scheduled jobs are delivered."),
    ("delegate", "Delegate", "How the delegate tool spawns and scopes subagents."),
    ("hooks", "Hooks", "Declarative hooks that run around the agent."),
    ("skills", "Skills", "User-defined capabilities and their creation policy."),
    ("skill_bundles", "Skill bundles", "Bundled skill sets."),
    ("plugins", "Plugins", "Plugin processes and the capabilities they hold."),
    ("mcp", "MCP servers", "Connected MCP servers and the tools they expose."),
    ("mcp_bundles", "MCP bundles", "Deferred MCP servers, loaded on demand."),
    ("memory", "Memory", "Long-term memory policy."),
    ("sop", "Standard operating procedures", "SOP execution and approval gates."),
    ("permission_profiles", "Permission profiles", "What each profile allows."),
    ("risk_profiles", "Risk profiles", "The risk tiers the permission profiles grant."),
    ("agents", "Agents", "Per-agent overrides, including the tools each may use."),
    ("security", "Security", "The security posture the runtime enforces."),
    ("reliability", "Reliability", "Retries, timeouts and circuit breaking."),
    ("trust", "Trust", "What the agent is allowed to trust from outside."),
]

MAX_DEPTH = 3


def dump_schema() -> dict | None:
    """The JSON Schema the binary prints."""
    if not os.path.exists(BINARY):
        print(f"no binary at {BINARY}", file=sys.stderr)
        return None
    result = subprocess.run(
        [BINARY, "config", "schema"], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"config schema unavailable: {result.stderr.strip()[:200]}", file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        print(f"config schema did not parse: {error}", file=sys.stderr)
        return None


def resolve_ref(node, root, depth=0):
    """Follow a `$ref` to its definition."""
    if depth > 12 or not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not ref or not ref.startswith("#/"):
        return node
    target = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, dict) or part not in target:
            return node
        target = target[part]
    return resolve_ref(target, root, depth + 1)


def describe_type(node) -> str:
    if not isinstance(node, dict):
        return ""
    if "type" in node:
        kind = node["type"]
        return " / ".join(kind) if isinstance(kind, list) else kind
    if "enum" in node:
        return "enum"
    if "const" in node:
        return "const"
    for key in ("oneOf", "anyOf", "allOf"):
        if key in node:
            return key
    resolved = resolve_ref(node, ROOT_SCHEMA)
    if resolved is not node:
        return describe_type(resolved)
    return ""


def walk(node, prefix="", depth=0, out=None):
    """The property tree of one section."""
    if out is None:
        out = []
    if depth > MAX_DEPTH or not isinstance(node, dict):
        return out
    node = resolve_ref(node, ROOT_SCHEMA)
    for name, child in (node.get("properties") or {}).items():
        child = resolve_ref(child, ROOT_SCHEMA)
        path = f"{prefix}{name}"
        entry = {
            "path": path,
            "type": describe_type(child),
            "description": (child.get("description") or "").strip(),
            "default": child.get("default"),
            "enum": child.get("enum"),
            "deprecated": bool(child.get("deprecated")),
            "read_only": bool(child.get("readOnly")),
            "secret": bool(child.get("writeOnly") or child.get("format") == "password"),
        }
        out.append(entry)
        nested = child.get("properties")
        if nested:
            walk(child, f"{path}.", depth + 1, out)
            continue
        items = child.get("items")
        if isinstance(items, dict):
            items = resolve_ref(items, ROOT_SCHEMA)
            if items.get("properties"):
                walk(items, f"{path}[]", depth + 1, out)
    return out


def section_entries(node, key):
    """The properties of a section, whether it is fixed or a map.

    A section like `[agents.<alias>]` is a map: it has no properties of its
    own, only the shape of one entry. Those entries are shown under the
    section with their own path prefix.
    """
    node = resolve_ref(node, ROOT_SCHEMA)
    entries = walk(node, f"{key}.")
    if entries:
        return entries, "properties"
    additional = node.get("additionalProperties")
    if isinstance(additional, dict):
        entry_node = resolve_ref(additional, ROOT_SCHEMA)
        entries = walk(entry_node, f"{key}.<name>.")
        if entries:
            return entries, "map"
    return entries, "properties"


ROOT_SCHEMA: dict = {}


def main() -> None:
    global ROOT_SCHEMA
    schema = dump_schema()
    if schema is None:
        print("config surface not written", file=sys.stderr)
        return
    ROOT_SCHEMA = {**(schema.get("$defs") or {}), **schema}
    properties = schema.get("properties") or {}

    sections = []
    total = 0
    for key, title, blurb in SECTIONS:
        node = properties.get(key)
        if node is None:
            continue
        entries, shape = section_entries(node, key)
        total += len(entries)
        sections.append(
            {
                "key": key,
                "title": title,
                "blurb": blurb,
                "shape": shape,
                "description": (node.get("description") or "").strip(),
                "properties": entries,
            }
        )

    payload = {
        "generated_from": {
            "binary": os.path.relpath(BINARY, AGENT),
            "command": "zeroclaw config schema",
            "schema_title": schema.get("title", ""),
        },
        "counts": {
            "config_sections_total": len(properties),
            "sections_shown": len(sections),
            "properties_shown": total,
        },
        "sections": sections,
    }
    with open(OUT, "w") as handle:
        json.dump(payload, handle, indent=1)
    print(f"wrote {OUT}", file=sys.stderr)
    for name, value in payload["counts"].items():
        print(f"  {name}: {value}", file=sys.stderr)


if __name__ == "__main__":
    main()
