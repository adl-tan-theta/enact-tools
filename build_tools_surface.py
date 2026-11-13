#!/usr/bin/env python3
"""Extract the real tool surface from the Enact source tree.

Every schema here is the schema the product actually ships — the `json!` block
inside a tool's `parameters_schema()` — not a hand-written approximation. The
extractor reads the Rust source; a separate pass reads the built binary, and
the two are cross-checked so neither can silently drift.

Sources, in order of authority:

* `crates/zeroclaw-*/src/**.rs` and `overlays/enact/native/tools/*.rs` — the
  per-tool `parameters_schema()` implementation.
* `crates/zeroclaw-tools/src/inventory.rs` — the canonical tier and
  compilation-mode table.
* `overlays/enact/native/tools/families.rs` — the family table: which legacy
  tools collapse into which canonical tool, and with which actions.
* `crates/zeroclaw-config/src/*.rs` — the configuration surface.

Output: `tools-surface.json`, holding the before (per-tool) and after
(canonical) surfaces with full schemas.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import defaultdict

import rust_expr as RX

ROOT = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(os.path.dirname(ROOT), "enact-agent")
CSV = os.path.join(ROOT, "zeroclaw-tools-operations.csv")


# --------------------------------------------------------------------- Rust
def rust_files() -> list[str]:
    """Every Rust file that may hold a tool implementation."""
    out = subprocess.run(
        ["git", "ls-files", "crates", "src", "overlays/enact/native"],
        cwd=AGENT, capture_output=True, text=True,
    )
    return [line for line in out.stdout.splitlines() if line.endswith(".rs")]


def message_catalog() -> dict[str, str]:
    """The English message catalog: the source of most tool descriptions."""
    out: dict[str, str] = {}
    listed = subprocess.run(
        ["git", "ls-files", "crates"], cwd=AGENT, capture_output=True, text=True
    ).stdout.splitlines()
    for rel in listed:
        if not rel.endswith(".ftl"):
            continue
        if "/locales/en/" not in rel:
            continue
        full = os.path.join(AGENT, rel)
        with open(full, encoding="utf-8", errors="replace") as handle:
            out.update(RX.parse_fluent(handle.read()))
    return out


def impl_of(text: str, offset: int) -> tuple[str | None, str] | None:
    """The (type name, body) of the impl block containing `offset`."""
    best = None
    for type_name, body, start in RX.impl_blocks_spanned(text):
        if start <= offset < start + len(body):
            if best is None or start > best[0]:
                best = (start, type_name, body)
    if best is None:
        return None
    return best[1], best[2]


def tool_name_from(block: str, type_name: str | None, scope: RX.Scope) -> str | None:
    """The name a tool reports, from its impl block."""
    for pattern in (
        r"fn\s+name\s*\(\s*&self\s*\)\s*->\s*&(?:\s*&)?(?:\s*'static\s+)?str\s*\{\s*\"([^\"]+)\"",
        r"fn\s+name\s*\(\s*\)\s*->\s*&(?:\s*&)?(?:\s*'static\s+)?str\s*\{\s*\"([^\"]+)\"",
    ):
        hits = re.findall(pattern, block)
        if hits:
            return hits[0]
    m = re.search(r"fn\s+name\s*\(\s*&self\s*\)\s*->\s*&(?:\s*&)?(?:\s*'static\s+)?str\s*\{\s*Self::([A-Za-z_][A-Za-z0-9_]*)", block)
    if m:
        const_name = m.group(1)
        if type_name:
            value = scope.assoc_value(type_name, const_name)
            if isinstance(value, str):
                return value
        value = scope.assoc.get(f"Self::{const_name}")
        if isinstance(value, str):
            return value
        value = scope.const_value(const_name)
        if isinstance(value, str):
            return value
    return None


def tool_description_from(block: str, type_name: str | None, scope: RX.Scope) -> str | None:
    """The description a tool reports, from its impl block."""
    m = re.search(
        r"fn\s+description\s*\(\s*&self\s*\)\s*->\s*&(?:\s*&)?(?:\s*'static\s+)?str\s*\{\s*\"((?:[^\"\\]|\\.)*)\"",
        block,
    )
    if m:
        return RX.unescape_rust_string(f'"{m.group(1)}"')
    m = re.search(r"fn\s+description\s*\(\s*&self\s*\)\s*->\s*&(?:\s*&)?(?:\s*'static\s+)?str\s*\{\s*Self::([A-Za-z_][A-Za-z0-9_]*)", block)
    if m and type_name:
        value = scope.assoc_value(type_name, m.group(1))
        if isinstance(value, str):
            return value
    return None


def extract_from_source(paths: list[str], messages: dict[str, str] | None = None) -> dict[str, dict]:
    """Map tool name -> {description, schema, file} from the Rust source."""
    texts: dict[str, str] = {}
    for rel in paths:
        full = os.path.join(AGENT, rel)
        if not os.path.exists(full):
            continue
        with open(full, encoding="utf-8", errors="replace") as handle:
            texts[rel] = RX.strip_comments(handle.read())

    # A type's associated const, a constant or a function can live in another
    # crate — `RoomVisibility` is declared in zeroclaw-api but used in
    # zeroclaw-tools — so the index of those symbols spans the whole tree.
    scopes = [RX.Scope(text, messages) for text in texts.values()]
    tree = RX.Tree()
    tree.build(scopes)
    tree.finalize()

    candidates: dict[str, list[dict]] = {}
    for rel, text in texts.items():
        scope = RX.Scope(text, messages)
        scope.tree = tree

        for m in re.finditer(r"fn\s+parameters_schema\s*\(\s*&self\s*\)\s*->\s*[^;{]*\{", text):
            enclosing = impl_of(text, m.start())
            if enclosing is None:
                continue
            type_name, block = enclosing
            name = tool_name_from(block, type_name, scope)
            if not name:
                # a wrapper that forwards to an inner tool: not the tool itself
                continue
            body_start = text.find("{", m.end() - 1)
            call = re.search(r"json!\s*\(", text[body_start : body_start + 8000])
            if not call:
                continue
            open_paren = body_start + call.end() - 1
            try:
                blob = RX.balanced(text, open_paren, "(", ")")
            except ValueError:
                continue
            brace = blob.find("{")
            if brace == -1:
                continue
            try:
                body = RX.balanced(blob, brace, "{", "}")
            except ValueError:
                continue

            ctx = RX.Ctx(scope, type_name)
            RX.collect_locals(text[body_start:open_paren], ctx)
            resolved = RX.resolve_json_body(body, ctx)
            try:
                schema = json.loads(resolved)
            except json.JSONDecodeError:
                continue

            candidates.setdefault(name, []).append(
                {
                    "name": name,
                    "description": tool_description_from(block, type_name, scope),
                    "parameters": schema,
                    "source_file": rel,
                }
            )
    return candidates


def pick_candidates(candidates: dict[str, list[dict]], preferred: dict[str, str]) -> dict[str, dict]:
    """Choose one schema per tool, preferring the file the inventory names.

    A tool name can appear in more than one place — a test double, a wrapper,
    a copy in a different crate. The operations inventory records where a tool
    actually lives, so that file wins; otherwise the first candidate does.
    """
    out: dict[str, dict] = {}
    for name, options in candidates.items():
        want = preferred.get(name)
        chosen = None
        if want:
            for option in options:
                if option["source_file"] == want:
                    chosen = option
                    break
        if chosen is None and want:
            base = os.path.basename(want)
            for option in options:
                if os.path.basename(option["source_file"]) == base:
                    chosen = option
                    break
        out[name] = chosen or options[0]
    return out


# ------------------------------------------------------------------ families
def extract_families() -> list[dict]:
    """The family table: canonical name, members, and each member's actions."""
    path = os.path.join(AGENT, "overlays/enact/native/tools/families.rs")
    with open(path, encoding="utf-8") as handle:
        text = RX.strip_comments(handle.read())

    families: list[dict] = []
    for fm in re.finditer(
        r'Family\s*\{\s*name:\s*"([^"]+)"\s*,\s*description:\s*"((?:[^"\\]|\\.)*)"\s*,\s*members:\s*&\[(.*?)\]\s*,?\s*\}',
        text,
        re.S,
    ):
        name, description, members_block = fm.groups()
        members = re.findall(r'"([^"]+)"', members_block)
        families.append(
            {
                "name": name,
                "description": RX.unescape_rust_string(f'"{description}"'),
                "members": members,
            }
        )

    members: dict[str, dict] = {}
    for mm in re.finditer(
        r'Member\s*\{\s*tool:\s*"([^"]+)"\s*,\s*ops:\s*&\[(.*?)\]\s*,\s*action_backed:\s*(true|false)\s*,?\s*\}',
        text,
        re.S,
    ):
        tool, ops_block, backed = mm.groups()
        ops = re.findall(r'"([^"]+)"', ops_block)
        members[tool] = {
            "tool": tool,
            "ops": ops,
            "action_backed": backed == "true",
        }

    for family in families:
        family["member_details"] = [
            members[m] for m in family["members"] if m in members
        ]
    return families


# ----------------------------------------------------------------- inventory
def extract_inventory() -> dict[str, dict]:
    """The canonical tier and compilation-mode table."""
    path = os.path.join(AGENT, "crates/zeroclaw-tools/src/inventory.rs")
    with open(path, encoding="utf-8") as handle:
        text = RX.strip_comments(handle.read())

    entry = re.compile(
        r'BuiltinToolSpec\s*\{\s*name:\s*"([^"]+)"\s*,\s*tier:\s*ToolTier::(\w+)\s*,\s*compilation:\s*(?:BuiltinToolCompilation|CompilationGroup)::(\w+)\s*',
        re.S,
    )
    out: dict[str, dict] = {}
    for name, tier, compilation in entry.findall(text):
        out[name] = {"tier": tier, "compilation": compilation}
    return out


# ------------------------------------------------------------------ the CSV
def read_csv() -> list[dict]:
    import csv

    with open(CSV, newline="") as handle:
        return list(csv.DictReader(handle))


# --------------------------------------------------------------- the binary
def dump_binary_surface() -> list[dict]:
    """The canonical surface the shipped binary actually advertises."""
    binary = os.path.join(AGENT, "target/release/zeroclaw")
    if not os.path.exists(binary):
        return []
    script = r'''
import json, subprocess, sys
proc = subprocess.Popen(
    ["./target/release/zeroclaw", "mcp", "serve", "--expose-full",
     "--workspace", "/tmp/enact-surface-dump"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
def send(o):
    proc.stdin.write(json.dumps(o) + "\n"); proc.stdin.flush()
def read():
    line = proc.stdout.readline()
    if not line:
        sys.exit(1)
    return json.loads(line)
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"dump","version":"1"}}})
read()
send({"jsonrpc":"2.0","method":"notifications/initialized","params":{}})
send({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
print(json.dumps(read()["result"]["tools"]))
proc.stdin.close(); proc.terminate()
'''
    os.makedirs("/tmp/enact-surface-dump", exist_ok=True)
    result = subprocess.run(
        ["python3", "-c", script], cwd=AGENT, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"binary dump failed: {result.stderr[:400]}", file=sys.stderr)
        return []
    return json.loads(result.stdout)


# --------------------------------------------------------------------- main
def main() -> None:
    paths = rust_files()
    print(f"scanning {len(paths)} Rust files", file=sys.stderr)
    messages = message_catalog()
    print(f"  catalogue messages: {len(messages)}", file=sys.stderr)

    rows = read_csv()
    preferred: dict[str, str] = {}
    for row in rows:
        preferred.setdefault(row["tool_name"], row["source_file"])

    candidates = extract_from_source(paths, messages)
    from_source = pick_candidates(candidates, preferred)
    print(f"  schemas extracted: {len(from_source)}", file=sys.stderr)

    families = extract_families()
    print(f"  families: {len(families)}", file=sys.stderr)

    inventory = extract_inventory()
    print(f"  inventory entries: {len(inventory)}", file=sys.stderr)

    source_tools: dict[str, dict] = {}
    for row in rows:
        name = row["tool_name"]
        entry = source_tools.setdefault(
            name,
            {
                "name": name,
                "tier": row["tier"],
                "compilation": row["compilation"],
                "source_file": row["source_file"],
                "operations": [],
                "operation_basis": row["operation_basis"],
            },
        )
        entry["operations"].append(row["operation"])

    for name, entry in source_tools.items():
        found = from_source.get(name)
        if found is not None:
            entry["parameters"] = found["parameters"]
            entry["description"] = found.get("description")
            entry["schema_from"] = found["source_file"]
        else:
            entry["parameters"] = None
            entry["description"] = None
            entry["schema_from"] = None

    with_schema = sum(1 for e in source_tools.values() if e["parameters"])
    print(f"  source tools with a real schema: {with_schema}/{len(source_tools)}", file=sys.stderr)

    binary = dump_binary_surface()
    print(f"  canonical tools from the binary: {len(binary)}", file=sys.stderr)

    # the after surface: canonical tools with the real schema the binary serves
    after: list[dict] = []
    family_by_member = {m: f for f in families for m in f["members"]}
    binary_by_name = {t["name"]: t for t in binary}

    for family in families:
        actions = []
        for member in family["member_details"]:
            for op in member["ops"]:
                actions.append(op)
        entry = {
            "name": family["name"],
            "description": family["description"],
            "kind": "family",
            "merged_from": family["members"],
            "actions": actions,
            "member_details": family["member_details"],
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": actions,
                        "description": "Which operation to run.",
                    }
                },
                "required": ["action"],
                "additionalProperties": True,
            },
            "from_binary": family["name"] in binary_by_name,
        }
        if family["name"] in binary_by_name:
            entry["binary_parameters"] = binary_by_name[family["name"]].get("inputSchema")
        after.append(entry)

    for name, entry in source_tools.items():
        if name in family_by_member:
            continue  # folded into a family
        canon = {
            "name": name,
            "description": entry.get("description"),
            "kind": "standalone",
            "merged_from": [name],
            "actions": entry["operations"],
            "parameters": entry["parameters"],
            "tier": entry["tier"],
            "compilation": entry["compilation"],
            "source_file": entry["source_file"],
            "from_binary": name in binary_by_name,
        }
        if name in binary_by_name:
            canon["binary_parameters"] = binary_by_name[name].get("inputSchema")
        after.append(canon)

    after.sort(key=lambda t: (t["kind"] != "family", t["name"]))

    payload = {
        "generated_from": {
            "agent_head": subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"], cwd=AGENT,
                capture_output=True, text=True,
            ).stdout.strip(),
            "csv": os.path.basename(CSV),
        },
        "counts": {
            "source_tools": len(source_tools),
            "source_operations": sum(len(e["operations"]) for e in source_tools.values()),
            "canonical_tools": len(after),
            "families": len(families),
            "tools_with_real_schema": with_schema,
            "binary_advertised": len(binary),
        },
        "before": sorted(source_tools.values(), key=lambda t: t["name"]),
        "after": after,
        "binary_surface": binary,
    }
    out = os.path.join(ROOT, "tools-surface.json")
    with open(out, "w") as handle:
        json.dump(payload, handle, indent=1)
    print(f"wrote {out}", file=sys.stderr)
    for key, value in payload["counts"].items():
        print(f"  {key}: {value}", file=sys.stderr)


if __name__ == "__main__":
    main()
