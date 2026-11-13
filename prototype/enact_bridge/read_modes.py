"""Read modes for `file_read`.

The product's `file_read` can answer more than "give me the file": it can
list the declarations a file holds, outline its structure, show what changed
against a base, read the lines around a match, or pick out the lines that
are about a task. The bridge mirrors that contract so the canonical registry
advertises the same actions the native server implements.

The renderers here are the Python counterparts of the Rust ones in
`crates/zeroclaw-runtime/src/tools/file_read_modes.rs`.
"""

from __future__ import annotations

import re
from typing import Any

DECLARATION_KEYWORDS = (
    "fn ",
    "func ",
    "def ",
    "function ",
    "struct ",
    "enum ",
    "trait ",
    "impl ",
    "mod ",
    "class ",
    "interface ",
    "type ",
    "const ",
    "static ",
    "let ",
    "var ",
    "pub ",
    "async ",
    "unsafe ",
)

_NAME_KEYWORDS = (
    "fn ",
    "func ",
    "def ",
    "function ",
    "struct ",
    "enum ",
    "trait ",
    "impl ",
    "mod ",
    "class ",
    "interface ",
    "type ",
)

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WORD = re.compile(r"[A-Za-z0-9_]+")


def _is_declaration(line: str) -> bool:
    trimmed = line.lstrip()
    if not trimmed or trimmed.startswith("//") or trimmed.startswith("#"):
        return False
    return any(trimmed.startswith(keyword) for keyword in DECLARATION_KEYWORDS)


def _declared_name(line: str) -> str:
    trimmed = line.lstrip()
    for keyword in _NAME_KEYWORDS:
        if trimmed.startswith(keyword):
            rest = trimmed[len(keyword) :]
            match = _IDENTIFIER.match(rest)
            if match:
                return match.group(0)
    return ""


def render_signatures(text: str) -> str:
    """The declarations a file holds, with their line numbers."""
    lines = []
    for number, line in enumerate(text.splitlines(), start=1):
        if _is_declaration(line):
            lines.append(f"{number}: {line.strip()[:140]}")
    return "\n".join(lines) if lines else "No declarations found."


def render_outline(text: str) -> str:
    """The structure of a file, nested by brace depth."""
    out: list[str] = []
    depth = 0
    for number, line in enumerate(text.splitlines(), start=1):
        trimmed = line.strip()
        if not trimmed:
            continue
        if not _is_declaration(line):
            depth += trimmed.count("{") - trimmed.count("}")
            depth = max(depth, 0)
            continue
        indent = depth if "{" in trimmed else (len(line) - len(line.lstrip())) // 4
        out.append(f"{' ' * (indent * 2)}{number}: {trimmed[:140]}")
    return "\n".join(out) if out else "No declarations found."


def render_diff(before: str, after: str) -> str:
    """The lines that changed between two texts."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    out: list[str] = []
    changed = 0
    index = 0
    while index < len(before_lines) or index < len(after_lines):
        old = before_lines[index] if index < len(before_lines) else None
        new = after_lines[index] if index < len(after_lines) else None
        if old == new:
            index += 1
            continue
        changed += 1
        out.append(f"@@ line {index + 1}")
        if old is not None:
            out.append(f"-{old}")
        if new is not None:
            out.append(f"+{new}")
        index += 1
    if not changed:
        return "No differences."
    out.append(f"{changed} changed line(s).")
    return "\n".join(out)


def _regions(lines: list[str], hits: list[int], context: int) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    for index in hits:
        start = max(index - context, 0)
        end = min(index + context + 1, len(lines))
        if regions and start <= regions[-1][1]:
            regions[-1] = (regions[-1][0], max(regions[-1][1], end))
        else:
            regions.append((start, end))
    return regions


def render_anchored(text: str, anchor: str, context: int = 3) -> str:
    """The lines around a match."""
    lines = text.splitlines()
    needle = anchor.lower()
    hits = [index for index, line in enumerate(lines) if needle in line.lower()]
    if not hits:
        return f"No line matches {anchor!r}."
    out: list[str] = []
    previous_end = 0
    for start, end in _regions(lines, hits, context):
        if start > previous_end:
            out.append("...")
        for index in range(start, end):
            out.append(f"{index + 1}: {lines[index]}")
        previous_end = end
    return "\n".join(out)


def render_task(text: str, task: str, context: int = 3) -> str:
    """The lines that mention the task."""
    lines = text.splitlines()
    terms = {word.lower() for word in _WORD.findall(task) if len(word) > 2}
    if not terms:
        return "The task has no searchable words."
    hits = [index for index, line in enumerate(lines) if any(term in line.lower() for term in terms)]
    if not hits:
        return f"No line mentions anything from the task {task!r}."
    out: list[str] = []
    previous_end = 0
    for start, end in _regions(lines, hits, context):
        if start > previous_end:
            out.append("...")
        for index in range(start, end):
            out.append(f"{index + 1}: {lines[index]}")
        previous_end = end
    return "\n".join(out)


def render(mode: str, text: str, args: dict[str, Any]) -> str:
    """Render one read mode over a file's text."""
    context = int(args.get("context") or 3)
    if mode == "signatures":
        return render_signatures(text)
    if mode == "outline":
        return render_outline(text)
    if mode == "diff":
        base = args.get("base")
        if base is None:
            return "The diff action compares the file against a base; pass 'base' with the previous text."
        return render_diff(str(base), text)
    if mode == "anchored":
        anchor = args.get("anchor")
        if not anchor:
            return "The anchored action needs an 'anchor': the text to find."
        return render_anchored(text, str(anchor), context)
    if mode == "task":
        task = args.get("task")
        if not task:
            return "The task action needs a 'task' to look for."
        return render_task(text, str(task), context)
    return ""
