#!/usr/bin/env python3
"""Evaluate the Rust expressions that appear inside a `json!` schema block.

A tool's `parameters_schema()` is usually a `json!` macro, but the values in
it are not always literals. A real schema in this tree contains:

* `const` references — `"enum": KNOWLEDGE_ACTIONS` (a `&[&str]`),
* associated consts — `"enum": ChannelRoomAction::SCHEMA_VALUES`,
* `format!` with const placeholders — `"description": format!("... {MAX}")`,
* `let` bindings — `"description": action_desc`,
* table folds — `"description": format!("... ({})", Self::cell_vocab(...))`.

This module resolves those against the file they came from, so the extracted
schema is the schema the tool actually ships. Anything genuinely computed at
run time is marked `<computed at runtime>` rather than guessed.

The resolver is deliberately partial: it understands the expression shapes this
tree uses and refuses to invent values for shapes it does not.
"""
from __future__ import annotations

import re

MARKER = "<computed at runtime>"

# The helpers a schema uses to pull a description out of the message catalog.
MESSAGE_FUNCTIONS = {
    "tool_msg",
    "tool_msg_with_args",
    "get_required_tool_string",
    "get_required_tool_string_with_args",
    "msg",
    "msg_with_args",
}


# --------------------------------------------------------------------- lexing
def strip_comments(text: str) -> str:
    """Remove // and /* */ comments, leaving string literals intact.

    A `\\` at the end of a line inside a string literal is Rust's line
    continuation: it swallows the newline and the indentation after it. JSON
    has no such escape, so the continuation is collapsed here — otherwise the
    extracted schema would carry a raw newline inside a JSON string and fail
    to parse.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            out.append(ch)
            i += 1
            while i < n:
                if text[i] == "\\":
                    # a continuation swallows the newline and the indentation
                    j = i + 1
                    if j < n and text[j] == "\n":
                        j += 1
                        while j < n and text[j] in " \t":
                            j += 1
                        i = j
                        continue
                    out.append(text[i])
                    i += 1
                    if i < n:
                        out.append(text[i])
                        i += 1
                    continue
                out.append(text[i])
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text.startswith("/*", i):
            depth = 1
            i += 2
            while i < n and depth:
                if text.startswith("/*", i):
                    depth += 1
                    i += 2
                elif text.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def unescape_rust_string(literal: str) -> str:
    """The value of a Rust string literal, given the literal including quotes."""
    body = literal[1:-1]
    out = []
    i = 0
    n = len(body)
    simple = {
        "n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'",
        "0": "\0", "$": "$",
    }
    while i < n:
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        esc = body[i]
        if esc in simple:
            out.append(simple[esc])
            i += 1
        elif esc == "u" and i + 1 < n and body[i + 1] == "{":
            end = body.find("}", i)
            if end == -1:
                out.append(esc)
                i += 1
                continue
            out.append(chr(int(body[i + 2 : end], 16)))
            i = end + 1
        elif esc == "x" and i + 2 < n:
            out.append(chr(int(body[i + 1 : i + 3], 16)))
            i += 3
        elif esc == "\n":
            # a line continuation: skip the newline and the indentation
            i += 1
            while i < n and body[i] in " \t":
                i += 1
        else:
            out.append(esc)
            i += 1
    return "".join(out)


def split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split on `sep`, ignoring separators nested in brackets or strings."""
    parts = []
    depth = 0
    in_string = False
    escape = False
    current = []
    for ch in text:
        if in_string:
            current.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            current.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts]


def balanced(text: str, start: int, open_ch: str = "{", close_ch: str = "}") -> str:
    """The text between `start` (at `open_ch`) and its matching close."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced")


# --------------------------------------------------------------- i18n catalog
FTL_ENTRY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*=\s*(.*)$")


def parse_fluent(text: str) -> dict[str, str]:
    """The message catalog of one Fluent (.ftl) file.

    Fluent entries are `key = value`, one per line. A value may continue on
    the next line when that line is indented and holds no `=`. A literal brace
    is written `{"{"}` and comes back out as `{`.
    """
    out: dict[str, str] = {}
    last_key = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = FTL_ENTRY.match(stripped)
        if match:
            last_key = match.group(1)
            out[last_key] = match.group(2).strip()
        elif last_key is not None and line.startswith((" ", "\t")):
            out[last_key] = (out[last_key] + " " + stripped).strip()
    return {k: v.replace('{"{"}', "{").replace('{"}"}', "}") for k, v in out.items()}


# ------------------------------------------------------------------- scopes
CONST_STR = re.compile(
    r'\bconst\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*&\s*(?:\'static\s+)?str\s*=\s*"((?:[^"\\]|\\.)*)"'
)
CONST_NUM = re.compile(
    r"\bconst\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[A-Za-z_][A-Za-z0-9_:<>]*\s*=\s*(-?[\d_]+(?:\.[\d_]+)?)\s*[;,]"
)
CONST_SLICE = re.compile(
    r"\bconst\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*&\s*(?:'static\s+)?"
    r"\[(?:\s*&\s*(?:'static\s+)?str\s*)?\]\s*=\s*&\["
)
ASSOC_STR = re.compile(
    r'\bconst\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*&\s*(?:\'static\s+)?str\s*=\s*"((?:[^"\\]|\\.)*)"'
)
ASSOC_ANY = re.compile(
    r"\bconst\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[^=;]+?\s*=\s*([^;]+);"
)
ASSOC_SLICE = re.compile(
    r"\bconst\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*&\s*(?:'static\s+)?"
    r"\[(?:\s*&\s*(?:'static\s+)?str\s*)?\]\s*=\s*&\["
)


class Scope:
    """The symbols one Rust file defines, resolved as far as the source allows."""

    def __init__(self, text: str, messages: dict[str, str] | None = None,
                 global_assoc: dict[str, object] | None = None):
        self.text = text
        self.messages = messages or {}
        self.global_assoc = global_assoc or {}
        self.str_consts: dict[str, str] = {}
        self.num_consts: dict[str, float | int] = {}
        self.slice_consts: dict[str, list[str]] = {}
        self.assoc: dict[str, object] = {}          # "Type::NAME" -> value
        self.impl_types: list[str] = []
        self.tables: dict[str, list[dict]] = {}     # "NAME" -> [{field: value}]
        self.locals: dict[str, object] = {}
        self.assoc_exprs: dict[str, str] = {}    # "Type::NAME" -> initializer
        self.const_exprs: dict[str, str] = {}    # "NAME" -> initializer
        self.enum_wires: dict[str, list[str]] = {}  # "Type" -> wire names
        self.enum_variants: dict[str, dict[str, str]] = {}  # "Type" -> {Variant: wire}
        self.function_bodies: dict[str, str] = {}   # "name" -> body text
        self.tree: "Tree | None" = None
        self._parse()

    # -- parsing ---------------------------------------------------------
    def _parse(self) -> None:
        text = self.text
        for name, value in CONST_STR.findall(text):
            self.str_consts.setdefault(name, unescape_rust_string(f'"{value}"'))
        for name, value in CONST_NUM.findall(text):
            cleaned = value.replace("_", "")
            self.num_consts.setdefault(
                name, int(cleaned) if "." not in cleaned else float(cleaned)
            )
        for m in ASSOC_ANY.finditer(text):
            name, value = m.group(1), m.group(2).strip()
            if name not in self.str_consts and name not in self.num_consts:
                self.const_exprs.setdefault(name, value)
        for m in CONST_SLICE.finditer(text):
            name = m.group(1)
            start = m.end() - 1
            try:
                body = balanced(text, start, "[", "]")
            except ValueError:
                continue
            self.slice_consts.setdefault(name, self._string_items(body))

        # associated consts, per impl block
        for type_name, body in impl_blocks(text):
            self.impl_types.append(type_name)
            for name, value in ASSOC_STR.findall(body):
                self.assoc.setdefault(f"{type_name}::{name}", unescape_rust_string(f'"{value}"'))
            for m in ASSOC_ANY.finditer(body):
                name, value = m.group(1), m.group(2).strip()
                key = f"{type_name}::{name}"
                if key not in self.assoc:
                    self.assoc_exprs.setdefault(key, value)
            for m in ASSOC_SLICE.finditer(body):
                try:
                    items = self._string_items(balanced(body, m.end() - 1, "[", "]"))
                except ValueError:
                    continue
                # a slice may list the impl's own consts: `&[Self::CREATE_ROOM]`
                resolved = []
                for item in items:
                    resolved.append(self._resolve_in_impl(item, type_name))
                self.assoc.setdefault(f"{type_name}::{m.group(1)}", resolved)

        # `Self::X` inside an impl refers to that impl's type
        for type_name, body in impl_blocks(text):
            for name in re.findall(r"\bSelf::([A-Za-z_][A-Za-z0-9_]*)", body):
                key = f"{type_name}::{name}"
                if key in self.assoc and f"Self::{name}" not in self.assoc:
                    self.assoc[f"Self::{name}"] = self.assoc[key]

        # static tables of struct literals: `static CELLS: &[Cell] = &[Cell { .. }, ...];`
        for m in re.finditer(r"\bstatic\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*&\s*\[", text):
            name = m.group(1)
            # the type's own bracket comes first; the table's bracket is after `=`
            equals = text.find("=", m.end())
            if equals == -1:
                continue
            start = text.find("[", equals)
            if start == -1:
                continue
            try:
                body = balanced(text, start, "[", "]")
            except ValueError:
                continue
            rows = self._struct_rows(body)
            if rows:
                self.tables.setdefault(name, rows)

        self._parse_enums()
        self._parse_macro_enums()
        self._parse_functions()

    def _parse_enums(self) -> None:
        """The wire name of every enum variant that declares one.

        An enum that maps its variants to strings — `Self::Delegate => "delegate"` —
        carries the vocabulary a schema advertises, in the order the enum declares
        it.
        """
        for type_name, body in impl_blocks(self.text):
            match = re.search(
                r"fn\s+as_str\s*\(\s*(?:&\s*)?self\s*\)\s*->\s*&(?:\s*&)?(?:\s*'static\s+)?str\s*\{(.*?)\n\s*\}",
                body,
                re.S,
            )
            if not match:
                continue
            arms = WIRE_ARM.findall(match.group(1))
            if arms:
                self.enum_wires.setdefault(
                    type_name, [unescape_rust_string(f'"{w}"') for _, w in arms]
                )
                self.enum_variants.setdefault(
                    type_name,
                    {v: unescape_rust_string(f'"{w}"') for v, w in arms},
                )

    def _parse_macro_enums(self) -> None:
        """Enums a macro declares: `knowledge_enum! { pub enum NodeType { .. } }`.

        The macro invocation carries the variant-to-wire pairs, and the enum name
        it declares — either in the invocation or in the macro's own definition.
        """
        for m in re.finditer(r"\b([a-z_][a-z0-9_]*)!\s*\{", self.text):
            macro = m.group(1)
            brace = self.text.find("{", m.end() - 1)
            try:
                body = balanced(self.text, brace, "{", "}")
            except ValueError:
                continue
            pairs = MACRO_PAIR.findall(body)
            if not pairs:
                continue
            enum_name = None
            inner = re.search(r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", body)
            if inner:
                enum_name = inner.group(1)
            else:
                # the macro declares the enum in its own definition
                definition = re.search(
                    r"macro_rules!\s+%s\s*\{" % re.escape(macro), self.text
                )
                if definition:
                    dbrace = self.text.find("{", definition.end() - 1)
                    try:
                        dbody = balanced(self.text, dbrace, "{", "}")
                    except ValueError:
                        dbody = ""
                    inner = re.search(r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", dbody)
                    if inner:
                        enum_name = inner.group(1)
            if enum_name:
                self.enum_wires.setdefault(
                    enum_name, [unescape_rust_string(f'"{w}"') for _, w in pairs]
                )
                self.enum_variants.setdefault(
                    enum_name,
                    {v: unescape_rust_string(f'"{w}"') for v, w in pairs},
                )

    def _parse_functions(self) -> None:
        """The body of every free function that returns a value.

        A function whose body is a single expression is resolvable: the
        expression is evaluated in the file that defines it.
        """
        for m in re.finditer(
            r"^\s*(?:pub(?:\([^)]*\))?\s+)?fn\s+([a-z_][a-z0-9_]*)\s*\(([^)]*)\)"
            r"\s*->\s*[^;{]*\{",
            self.text,
            re.M,
        ):
            name = m.group(1)
            if name in self.function_bodies:
                continue
            brace = self.text.find("{", m.end() - 1)
            try:
                body = balanced(self.text, brace, "{", "}")
            except ValueError:
                continue
            inner = body[1:-1].strip()
            if not inner or ";" in inner or inner.endswith(","):
                continue
            self.function_bodies[name] = inner

    def _string_items(self, body: str) -> list[str]:
        """The items of a `&["a", "b"]` literal.

        A literal string is decoded; a const reference is kept as text so the
        caller can resolve it against the scope it came from.
        """
        inner = body[1:-1] if body.startswith("[") and body.endswith("]") else body
        items = []
        for part in split_top_level(inner):
            part = part.strip()
            if not part:
                continue
            if part.startswith('"') and part.endswith('"'):
                items.append(unescape_rust_string(part))
            else:
                items.append(part)
        return items

    def _struct_rows(self, body: str) -> list[dict]:
        """The rows of a `&[Type { field: "value", .. }, ..]` literal."""
        rows = []
        for m in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\{", body):
            try:
                chunk = balanced(body, m.end() - 1, "{", "}")
            except ValueError:
                continue
            row = {}
            for fm in re.finditer(
                r'\b([a-z_][a-z0-9_]*)\s*:\s*"((?:[^"\\]|\\.)*)"', chunk
            ):
                row[fm.group(1)] = unescape_rust_string(f'"{fm.group(2)}"')
            if row:
                rows.append(row)
        return rows

    def _resolve_in_impl(self, item: str, type_name: str):
        """Resolve one slice item against the impl that owns the slice."""
        if item.startswith('"'):
            return item
        parts = item.split("::")
        if len(parts) == 2 and parts[0] == "Self":
            value = self.assoc.get(f"{type_name}::{parts[1]}")
            if value is not None:
                return value
        if len(parts) == 1 and parts[0] in self.str_consts:
            return self.str_consts[parts[0]]
        return item

    # -- lookup ----------------------------------------------------------
    def assoc_value(self, type_name: str, const_name: str):
        key = f"{type_name}::{const_name}"
        if key in self.assoc:
            return self.assoc[key]
        if key in self.global_assoc:
            return self.global_assoc[key]
        if self.tree is not None:
            return self.tree.assoc_value(key)
        return None

    def assoc_raw(self, key: str):
        if key in self.assoc:
            return self.assoc[key]
        if key in self.global_assoc:
            return self.global_assoc[key]
        if self.tree is not None:
            return self.tree.assoc_value(key)
        return None

    def const_value(self, name: str):
        if name in self.locals:
            return self.locals[name]
        if name in self.str_consts:
            return self.str_consts[name]
        if name in self.num_consts:
            return self.num_consts[name]
        if name in self.slice_consts:
            return self.slice_consts[name]
        return None


def impl_blocks(text: str) -> list[tuple[str, str]]:
    """(type name, body) for every `impl [Trait for] Type { ... }` block."""
    return [(name, body) for name, body, _ in impl_blocks_spanned(text)]


def impl_blocks_spanned(text: str) -> list[tuple[str, str, int]]:
    """(type name, body, body start offset) for every impl block."""
    out = []
    for m in re.finditer(r"^[ \t]*impl(?:\s+[^\n{]*?\s+for\s+)?\s*([A-Za-z_][A-Za-z0-9_]*)", text, re.M):
        brace = text.find("{", m.end())
        if brace == -1:
            continue
        try:
            body = balanced(text, brace, "{", "}")
        except ValueError:
            continue
        out.append((m.group(1), body, brace))
    return out


# ---------------------------------------------------------------- evaluation
class Ctx:
    """The evaluation context for one `parameters_schema()` body."""

    def __init__(self, scope: Scope, impl_type: str | None = None):
        self.scope = scope
        self.impl_type = impl_type
        self.locals: dict[str, object] = {}

    def lookup(self, name: str):
        if name in self.locals:
            return self.locals[name]
        value = self.scope.const_value(name)
        if value is not None:
            return value
        if self.scope.tree is not None:
            return self.scope.tree.const(name)
        return None

    def tree(self):
        return self.scope.tree

    def enum_wires(self, type_name: str):
        """The wire names of an enum, wherever the enum is declared."""
        if type_name in self.scope.enum_wires:
            return self.scope.enum_wires[type_name]
        if self.scope.tree is not None:
            return self.scope.tree.enum(type_name)
        return None

    def enum_variant(self, type_name: str, variant: str):
        table = self.scope.enum_variants.get(type_name)
        if table is not None:
            return table.get(variant)
        if self.scope.tree is not None:
            return self.scope.tree.variant(type_name, variant)
        return None

    def tree_function(self, name: str):
        if self.scope.tree is None:
            return None
        return self.scope.tree.function(name)

    def assoc(self, type_name: str, const_name: str):
        if type_name == "Self":
            type_name = self.impl_type or ""
        value = self.scope.assoc_value(type_name, const_name)
        if value is not None:
            return value
        # a `Self::` reference may belong to another impl in the same file
        value = self.scope.assoc.get(f"Self::{const_name}")
        if value is not None:
            return value
        return None


def _resolve_placeholder(name: str, args: list[str], ctx: Ctx) -> str:
    value = ctx.lookup(name)
    if value is None:
        return MARKER
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def eval_expr(expr: str, ctx: Ctx, depth: int = 0):
    """Evaluate one Rust expression to a Python value, or return None."""
    e = expr.strip()
    if not e or depth > 12:
        return None

    if e.startswith('"') and e.endswith('"') and len(e) >= 2:
        return unescape_rust_string(e)
    if e in ("true", "false"):
        return e == "true"
    if e == "null":
        return None
    if re.fullmatch(r"-?\d+", e):
        return int(e)
    if re.fullmatch(r"-?\d+\.\d+", e):
        return float(e)

    # format!("template {NAME} {}", args...)
    if e.startswith("format!(") and e.endswith(")"):
        inner = e[len("format!(") : -1]
        args = split_top_level(inner)
        if not args:
            return MARKER
        template = eval_expr(args[0], ctx, depth + 1)
        if not isinstance(template, str):
            return MARKER
        rest = args[1:]
        positional = 0

        def named(match: re.Match) -> str:
            return _resolve_placeholder(match.group(1), rest, ctx)

        def numbered(match: re.Match) -> str:
            nonlocal positional
            index = int(match.group(1))
            if index < len(rest):
                value = eval_expr(rest[index], ctx, depth + 1)
                return MARKER if value is None else str(value)
            return MARKER

        def unnamed(_match: re.Match) -> str:
            nonlocal positional
            while positional < len(rest) and "{" in rest[positional]:
                positional += 1
            if positional >= len(rest):
                return MARKER
            value = eval_expr(rest[positional], ctx, depth + 1)
            positional += 1
            return MARKER if value is None else str(value)

        out = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", named, template)
        out = re.sub(r"\{(\d+)\}", numbered, out)
        out = re.sub(r"\{\}", unnamed, out)
        return out

    # a table fold: Self::cell_vocab(|c| c.action, "/")
    vocab = re.fullmatch(
        r"(?:[A-Za-z_][A-Za-z0-9_]*::)*cell_vocab\(\s*\|[A-Za-z_]+\|\s*"
        r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
        r'"((?:[^"\\]|\\.)*)"\s*\)',
        e,
    )
    if vocab:
        table, field, sep = vocab.groups()
        rows = ctx.scope.tables.get(table)
        if rows is None:
            # `Self::cell_vocab` — the table is a module-level static
            for candidate in ctx.scope.tables:
                rows = ctx.scope.tables[candidate]
                break
        if not rows:
            return MARKER
        seen = []
        for row in rows:
            value = row.get(field)
            if value is not None and value not in seen:
                seen.append(value)
        return unescape_rust_string(f'"{sep}"').join(seen)

    # a string conversion: "text".to_string(), "text".into()
    converted = re.fullmatch(r"(.+?)\.(?:to_string|to_owned|into)\(\)", e, re.S)
    if converted:
        return eval_expr(converted.group(1), ctx, depth + 1)

    # a duration converted to a number: CONST.as_millis(), CONST.as_secs()
    duration = re.fullmatch(
        r"(?P<base>.+?)\.(?P<unit>as_millis|as_secs|as_micros)\(\)", e
    )
    if duration:
        base = eval_expr(duration.group("base"), ctx, depth + 1)
        if isinstance(base, (int, float)):
            unit = duration.group("unit")
            if unit == "as_millis":
                return base * 1000
            if unit == "as_secs":
                return base / 1000
            return base * 10000
        return None

    # a duration literal: Duration::from_secs(120)
    made = re.fullmatch(
        r"(?:[A-Za-z_][A-Za-z0-9_]*::)*Duration::from_(secs|millis|micros)\(\s*(-?[\d_]+)\s*\)",
        e,
    )
    if made:
        unit, amount = made.groups()
        value = int(amount.replace("_", ""))
        if unit == "secs":
            return value
        if unit == "millis":
            return value / 1000
        return value / 1000000

    # a method on a const slice: CHANNELS.join("|")
    joined = re.fullmatch(
        r"([A-Za-z_][A-Za-z0-9_]*)\.join\(\s*\"((?:[^\"\\]|\\.)*)\"\s*\)", e
    )
    if joined:
        name, sep = joined.groups()
        value = ctx.lookup(name)
        if isinstance(value, list):
            return unescape_rust_string(f'"{sep}"').join(str(v) for v in value)
        return None

    # a call to a free function the tree defines
    fn_call = re.fullmatch(
        r"(?:[A-Za-z_][A-Za-z0-9_]*::)*([a-z_][A-Za-z0-9_]*)\s*\(\s*\)", e
    )
    if fn_call:
        entry = ctx.tree_function(fn_call.group(1))
        if entry is not None:
            fn_scope, body = entry
            sub = Ctx(fn_scope, fn_scope.impl_types[0] if fn_scope.impl_types else None)
            value = eval_expr(body, sub, depth + 1)
            if value is not None:
                return value

    # an enum's advertised vocabulary: Type::schema_values(), Type::wire_names()
    enum_call = re.fullmatch(
        r"([A-Za-z_][A-Za-z0-9_]*)::([A-Za-z_][A-Za-z0-9_]*)\(\)", e
    )
    if enum_call:
        type_name, method = enum_call.groups()
        if method in ("schema_values", "wire_names", "SCHEMA_VALUES", "ALL_WIRE"):
            if type_name == "Self" and ctx.impl_type:
                type_name = ctx.impl_type
            wires = ctx.enum_wires(type_name)
            if wires is not None:
                return wires

    # one variant of an enum: Type::Variant.as_str()
    variant = re.fullmatch(
        r"([A-Za-z_][A-Za-z0-9_]*)::([A-Za-z_][A-Za-z0-9_]*)\.as_str\(\)", e
    )
    if variant:
        type_name, variant_name = variant.groups()
        if type_name == "Self" and ctx.impl_type:
            type_name = ctx.impl_type
        wire = ctx.enum_variant(type_name, variant_name)
        if wire is not None:
            return wire

    # a localised message lookup: tool_msg("key") / tool_msg_with_args("key", ..)
    call = re.fullmatch(
        r"(?:[A-Za-z_][A-Za-z0-9_]*::)*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)",
        e,
        re.S,
    )
    if call:
        fname = call.group(1)
        args = split_top_level(call.group(2))
        if fname in MESSAGE_FUNCTIONS and args:
            key = eval_expr(args[0], ctx, depth + 1)
            if isinstance(key, str):
                message = ctx.scope.messages.get(key)
                if message is None:
                    return MARKER
                if len(args) > 1:
                    pairs = re.findall(
                        r'\(\s*"([^"]*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)', args[1]
                    )
                    for name, value in pairs:
                        message = message.replace(
                            "{ $%s }" % name, unescape_rust_string(f'"{value}"')
                        ).replace("{%s}" % name, unescape_rust_string(f'"{value}"'))
                return message
            return MARKER
        return None

    # an array literal
    if e.startswith("[") and e.endswith("]"):
        inner = e[1:-1].strip()
        if not inner:
            return []
        items = []
        for part in split_top_level(inner):
            value = eval_expr(part, ctx, depth + 1)
            items.append(value if value is not None else MARKER)
        return items

    # a path to a const: Self::X, Type::X, module::CONST
    path = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(?:::[A-Za-z_][A-Za-z0-9_]*)+", e)
    if path:
        parts = e.split("::")
        direct = ctx.scope.assoc_raw(e)
        if direct is not None:
            return _resolve_slice_items(direct, ctx)
        # try the longest type prefix first
        for split in range(len(parts) - 1, 0, -1):
            type_name = "::".join(parts[:split])
            const_name = parts[split]
            value = ctx.scope.assoc_value(type_name, const_name)
            if value is not None:
                return _resolve_slice_items(value, ctx)
        value = ctx.lookup(parts[-1])
        if value is not None:
            return value
        initializer = ctx.scope.assoc_exprs.get(e) or ctx.scope.const_exprs.get(parts[-1])
        if initializer is not None:
            return eval_expr(initializer, ctx, depth + 1)
        return None

    # a bare identifier
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", e):
        value = ctx.lookup(e)
        if value is not None:
            return _resolve_slice_items(value, ctx)
        return None

    return None


def _resolve_slice_items(value, ctx: Ctx):
    """Resolve const references inside a resolved string slice."""
    if isinstance(value, list):
        return [_resolve_slice_items(v, ctx) for v in value]
    if not isinstance(value, str):
        return value
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        resolved = ctx.lookup(value)
        if resolved is not None:
            return _resolve_slice_items(resolved, ctx)
        return value
    # a path to a const: Self::X, Type::X
    parts = value.split("::")
    if len(parts) > 1:
        direct = ctx.scope.assoc_raw(value)
        if direct is not None:
            return _resolve_slice_items(direct, ctx)
        for split in range(len(parts) - 1, 0, -1):
            type_name = "::".join(parts[:split])
            const_name = parts[split]
            resolved = ctx.assoc(type_name, const_name)
            if resolved is not None:
                return _resolve_slice_items(resolved, ctx)
    return value


# ------------------------------------------------------------- json! bodies
CALL_START = re.compile(
    r"\s*((?:[A-Za-z_][A-Za-z0-9_]*::)*[A-Za-z_][A-Za-z0-9_]*!?)\s*\("
)


def read_raw(body: str, i: int) -> tuple[str, int]:
    """Read one raw (Rust) expression token out of a json! body.

    A call expression is read whole — `format!("… {X}", y)` must arrive as one
    token, commas and all. Anything else runs to the next JSON punctuation.
    """
    n = len(body)
    m = CALL_START.match(body, i)
    if m:
        open_idx = m.end() - 1
        try:
            close = balanced(body, open_idx, "(", ")")
        except ValueError:
            close = None
        if close:
            end = open_idx + len(close)
            return body[i:end], end
    start = i
    while i < n:
        c = body[i]
        if c in "{}[]," or c == '"':
            break
        if c == ":":
            if i + 1 < n and body[i + 1] == ":":
                i += 2
                continue
            break
        i += 1
    return body[start:i], i


def tokenize(body: str) -> list[tuple[str, str]]:
    """Split a json! body into string / punctuation / raw-expression tokens."""
    tokens: list[tuple[str, str]] = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == '"':
            start = i
            i += 1
            while i < n:
                if body[i] == "\\":
                    i += 2
                    continue
                if body[i] == '"':
                    i += 1
                    break
                i += 1
            tokens.append(("str", body[start:i]))
            continue
        if ch in "{}[],":
            tokens.append(("punct", ch))
            i += 1
            continue
        if ch == ":":
            tokens.append(("punct", ":"))
            i += 1
            continue
        raw, i = read_raw(body, i)
        if raw.strip():
            tokens.append(("raw", raw))
    return tokens


def resolve_json_body(body: str, ctx: Ctx) -> str:
    """Rewrite a json! body so that it parses as plain JSON."""
    tokens = tokenize(body)
    out = []
    for kind, text in tokens:
        if kind == "str":
            out.append(text)
            continue
        if kind == "punct":
            out.append(text)
            continue
        raw = text.strip()
        if not raw:
            continue
        if raw in ("true", "false", "null"):
            out.append(raw)
            continue
        value = eval_expr(raw, ctx)
        if value is None:
            # an expression we cannot resolve: keep the shape, mark the value
            out.append(json_string(MARKER))
            continue
        out.append(to_json(value))
    return "".join(out)


def json_string(text: str) -> str:
    import json

    return json.dumps(text)


def to_json(value) -> str:
    import json

    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ",".join(to_json(v) for v in value) + "]"
    return json.dumps(MARKER)


# ------------------------------------------------------------------- locals
def collect_locals(body: str, ctx: Ctx) -> None:
    """Resolve the `let` bindings a schema body depends on."""
    for m in re.finditer(r"\blet\s+(?:mut\s+)?([a-z_][a-z0-9_]*)\s*(?::[^=;]+)?=\s*", body):
        name = m.group(1)
        start = m.end()
        # the expression runs to the next `;` at the top level of this statement
        end = find_semicolon(body, start)
        if end == -1:
            continue
        expr = body[start:end]
        value = eval_expr(expr, ctx)
        if value is not None:
            ctx.locals[name] = value

    # a tuple binding: `let (a, b) = (first, second);`
    for m in re.finditer(r"\blet\s+\(([^)]*)\)\s*=\s*", body):
        names = [n.strip() for n in m.group(1).split(",") if n.strip()]
        start = m.end()
        end = find_semicolon(body, start)
        if end == -1:
            continue
        expr = body[start:end].strip()
        # an `if` binding takes the first branch: the general case. The other
        # branch narrows the schema at run time, which the source cannot say.
        branch = re.match(r"if\b[^{]*\{(.*)\}\s*else\s*\{", expr, re.S)
        if branch:
            expr = branch.group(1).strip()
        if not (expr.startswith("(") and expr.endswith(")")):
            continue
        items = split_top_level(expr[1:-1])
        for name, item in zip(names, items):
            value = eval_expr(item, ctx)
            if value is not None:
                ctx.locals[name] = value


def find_semicolon(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ";" and depth == 0:
            return i
    return -1


# ------------------------------------------------------------- the whole tree
WIRE_ARM = re.compile(r"Self::([A-Za-z_][A-Za-z0-9_]*)\s*=>\s*\"((?:[^\"\\]|\\.)*)\"")
MACRO_PAIR = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=>\s*\"((?:[^\"\\]|\\.)*)\"")


class Tree:
    """The symbols the whole tree defines.

    A schema may name a constant, a function or an enum that lives in another
    crate. This index holds those, and only holds a name when every file that
    defines it agrees on the value — a name with two meanings is not
    resolvable, and is left alone.
    """

    def __init__(self) -> None:
        self.consts: dict[str, list] = {}
        self.functions: dict[str, list] = {}
        self.enums: dict[str, list] = {}
        self.variants: dict[str, list] = {}
        self.assoc: dict[str, list] = {}

    def _add(self, table: dict[str, list], key: str, value) -> None:
        table.setdefault(key, []).append(value)

    def build(self, scopes: list["Scope"]) -> None:
        for scope in scopes:
            for name, value in scope.str_consts.items():
                self._add(self.consts, name, value)
            for name, value in scope.num_consts.items():
                self._add(self.consts, name, value)
            for name, value in scope.slice_consts.items():
                self._add(self.consts, name, value)
            for key, value in scope.assoc.items():
                if not key.startswith("Self::"):
                    self._add(self.assoc, key, value)
            for name, wires in scope.enum_wires.items():
                self._add(self.enums, name, wires)
            for name, mapping in scope.enum_variants.items():
                self._add(self.variants, name, mapping)
            for name, body in scope.function_bodies.items():
                self._add(self.functions, name, (scope, body))

    def finalize(self) -> None:
        self._consts = self._unambiguous(self.consts)
        self._enums = self._unambiguous(self.enums)
        self._assoc = self._unambiguous(self.assoc)
        self._variants = self._unambiguous(self.variants)
        self._functions = {}
        for key, values in self.functions.items():
            first = values[0]
            if all(value[1] == first[1] for value in values[1:]):
                self._functions[key] = first

    def const(self, name: str):
        return getattr(self, "_consts", {}).get(name)

    def enum(self, name: str):
        return getattr(self, "_enums", {}).get(name)

    def assoc_value(self, key: str):
        return getattr(self, "_assoc", {}).get(key)

    def function(self, name: str):
        return getattr(self, "_functions", {}).get(name)

    def variant(self, type_name: str, variant: str):
        table = getattr(self, "_variants", {}).get(type_name)
        if not table:
            return None
        return table.get(variant)

    @staticmethod
    def _unambiguous(table: dict[str, list]) -> dict[str, object]:
        out = {}
        for key, values in table.items():
            first = values[0]
            if all(_same(value, first) for value in values[1:]):
                out[key] = first
        return out

    def resolved_consts(self) -> dict[str, object]:
        return self._unambiguous(self.consts)

    def resolved_enums(self) -> dict[str, list]:
        return self._unambiguous(self.enums)

    def resolved_assoc(self) -> dict[str, object]:
        return self._unambiguous(self.assoc)

    def resolved_functions(self) -> dict[str, tuple]:
        out = {}
        for key, values in self.functions.items():
            first = values[0]
            if all(value[1] == first[1] for value in values[1:]):
                out[key] = first
        return out


def _same(a, b) -> bool:
    try:
        return a == b
    except Exception:
        return False
