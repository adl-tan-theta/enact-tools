"""Read each host's own policy and mirror its decisions.

The bridge never invents a policy language. It reads what the host already
declared and answers the same question the host would answer:

    Claude Code   ~/.claude/settings.json  ->  permissions.allow / .deny / .ask
    Codex CLI     ~/.codex/rules/*.rules   ->  execpolicy `prefix_rule(... decision=...)`
                  ~/.codex/config.toml     ->  approval_policy, sandbox_mode

A decision is one of `allow`, `prompt` or `forbidden`. The host remains the
enforcement point; the bridge uses the decision to fail fast with a clear
message instead of letting a call be silently refused later.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import aliases
from .aliases import BRIDGE_TOOLS as BRIDGE

ALLOW = "allow"
PROMPT = "prompt"
FORBIDDEN = "forbidden"

CLAUDE_SETTINGS = Path(os.path.expanduser("~/.claude/settings.json"))
CODEX_HOME = Path(os.path.expanduser("~/.codex"))
CODEX_RULES_DIR = CODEX_HOME / "rules"
CODEX_CONFIG = CODEX_HOME / "config.toml"

_RULE_RE = re.compile(
    r"prefix_rule\s*\(\s*pattern\s*=\s*\[(?P<pattern>[^\]]*)\]\s*,\s*decision\s*=\s*"
    r"\"(?P<decision>[a-z_]+)\"\s*(?:,\s*justification\s*=\s*\"(?P<just>[^\"]*)\")?\s*\)"
)
_TOKEN_RE = re.compile(r"\"((?:[^\"\\]|\\.)*)\"")


@dataclass
class Decision:
    decision: str
    reason: str
    source: str

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.decision} ({self.source}: {self.reason})"


# --------------------------------------------------------------------- helpers
def _tool_from_rule(rule: str) -> tuple[str, str | None]:
    """`Bash(git status)` -> ("Bash", "git status");  `Read` -> ("Read", None)."""
    rule = rule.strip()
    if "(" in rule and rule.endswith(")"):
        tool, _, spec = rule.partition("(")
        return tool.strip(), spec[:-1]
    return rule, None


def _spec_matches(canonical: str, action: str | None, args: dict[str, Any], spec: str) -> bool:
    """Does a permission specifier apply to this particular call?"""
    spec = spec.strip()
    if not spec:
        return True

    if canonical in BRIDGE:
        # `mcp__enact__mcp_call(action=cron_add)` style specifiers.
        m = re.match(r"^action\s*=\s*(?P<a>[A-Za-z0-9_.-]+)$", spec)
        if m:
            return m.group("a") == action
        return True

    if canonical == "shell":
        command = str(args.get("command", ""))
        pattern = spec
        if pattern.endswith(":*"):
            pattern = pattern[:-2]
        if pattern.endswith("*"):
            pattern = pattern[:-1].rstrip()
        head = pattern.split()
        if not head:
            return True
        argv = command.split()
        if len(argv) < len(head):
            return False
        return argv[: len(head)] == head

    if canonical in ("file_read", "file_write", "file_edit", "glob_search", "content_search"):
        path = str(args.get("path", ""))
        pattern = spec.lstrip("/")
        candidate = path.lstrip("/")
        if fnmatch.fnmatch(candidate, pattern) or fnmatch.fnmatch(candidate, f"**/{pattern}"):
            return True
        return fnmatch.fnmatch(path, spec)

    # Unknown tool: a bare specifier is treated as an action filter.
    return spec == action


# --------------------------------------------------------------- Claude Code
class ClaudeCodePolicy:
    """Mirrors `permissions.allow` / `.deny` / `.ask` from Claude Code settings."""

    host = aliases.CLAUDE_CODE

    def __init__(self, settings_path: str | os.PathLike | None = None) -> None:
        self.path = Path(settings_path) if settings_path else CLAUDE_SETTINGS
        self.data: dict[str, Any] = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text())
            except (ValueError, OSError):
                self.data = {}
        perms = self.data.get("permissions") or {}
        self.allow = [r for r in perms.get("allow", []) if isinstance(r, str)]
        self.deny = [r for r in perms.get("deny", []) if isinstance(r, str)]
        self.ask = [r for r in perms.get("ask", []) if isinstance(r, str)]
        self.default_mode = perms.get("defaultMode", "default")

    # -- matching
    def _match(self, rules: list[str], canonical: str, action: str | None, args: dict[str, Any]):
        for rule in rules:
            tool, spec = _tool_from_rule(rule)
            resolved = aliases.resolve(self.host, tool)
            if resolved != canonical:
                continue
            if _spec_matches(canonical, action, args, spec or ""):
                return rule
        return None

    def decide(self, canonical: str, action: str | None = None, args: dict[str, Any] | None = None) -> Decision:
        args = args or {}
        hit = self._match(self.deny, canonical, action, args)
        if hit:
            return Decision(FORBIDDEN, f"denied by rule {hit!r}", f"{self.host}:permissions.deny")
        hit = self._match(self.ask, canonical, action, args)
        if hit:
            return Decision(PROMPT, f"ask by rule {hit!r}", f"{self.host}:permissions.ask")
        hit = self._match(self.allow, canonical, action, args)
        if hit:
            return Decision(ALLOW, f"allowed by rule {hit!r}", f"{self.host}:permissions.allow")
        if self.default_mode == "bypassPermissions":
            return Decision(ALLOW, "defaultMode is bypassPermissions", f"{self.host}:permissions.defaultMode")
        return Decision(
            PROMPT,
            "no matching permission rule; Claude Code would ask",
            f"{self.host}:permissions",
        )

    def summary(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "settings": str(self.path),
            "exists": self.path.exists(),
            "defaultMode": self.default_mode,
            "allow": self.allow,
            "deny": self.deny,
            "ask": self.ask,
        }


# ------------------------------------------------------------------- Codex CLI
class CodexPolicy:
    """Mirrors Codex execpolicy `prefix_rule` decisions and its config posture."""

    host = aliases.CODEX

    def __init__(self, rules_dir: str | os.PathLike | None = None, config_path: str | os.PathLike | None = None) -> None:
        self.rules_dir = Path(rules_dir) if rules_dir else CODEX_RULES_DIR
        self.config_path = Path(config_path) if config_path else CODEX_CONFIG
        self.rules: list[dict[str, Any]] = []
        self.files: list[str] = []
        self._load_rules()
        self.config = self._load_config()

    def _load_rules(self) -> None:
        if not self.rules_dir.exists():
            return
        for path in sorted(self.rules_dir.glob("*.rules")):
            try:
                text = path.read_text()
            except OSError:
                continue
            self.files.append(str(path))
            for m in _RULE_RE.finditer(text):
                tokens = _TOKEN_RE.findall(m.group("pattern"))
                pattern = [t.replace('\\"', '"') for t in tokens]
                self.rules.append(
                    {
                        "pattern": pattern,
                        "decision": m.group("decision"),
                        "justification": m.group("just"),
                        "file": str(path),
                    }
                )

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as fh:
                return tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError):
            return {}

    # -- matching
    @staticmethod
    def _rule_matches(rule: dict[str, Any], argv: list[str]) -> bool:
        pattern = rule["pattern"]
        if not pattern:
            return False
        if len(argv) < len(pattern):
            return False
        return argv[: len(pattern)] == pattern

    def decide(self, canonical: str, action: str | None = None, args: dict[str, Any] | None = None) -> Decision:
        args = args or {}
        if canonical != "shell":
            return Decision(
                ALLOW,
                "execpolicy governs shell commands only; MCP tool calls are gated by the server",
                f"{self.host}:execpolicy",
            )
        command = str(args.get("command", ""))
        argv = command.split()
        matches = [r for r in self.rules if self._rule_matches(r, argv)]
        if matches:
            # Most specific (longest) pattern wins; ties resolve to the later rule.
            best = max(matches, key=lambda r: (len(r["pattern"]), self.rules.index(r)))
            return Decision(
                best["decision"],
                f"prefix_rule({best['pattern']}) in {os.path.basename(best['file'])}",
                f"{self.host}:execpolicy",
            )
        return Decision(
            PROMPT,
            "no execpolicy rule matches this command; Codex's own approval policy applies",
            f"{self.host}:execpolicy",
        )

    def summary(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "rules_dir": str(self.rules_dir),
            "rule_files": self.files,
            "rules": self.rules,
            "config": str(self.config_path),
            "approval_policy": self.config.get("approval_policy"),
            "sandbox_mode": self.config.get("sandbox_mode"),
        }


def policy_for(host: str, **kwargs: Any):
    if host == aliases.CLAUDE_CODE:
        return ClaudeCodePolicy(**kwargs)
    if host == aliases.CODEX:
        return CodexPolicy(**kwargs)
    raise ValueError(f"unknown host {host!r}")
