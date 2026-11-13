"""Host adapters: install the bridge into Claude Code and Codex.

Both hosts speak MCP, so the adapter's job is small and concrete:

  Claude Code   `.mcp.json` (project) or `~/.claude.json` (user), plus
                `.claude/settings.json` permissions and a `CLAUDE.md` pointer.
  Codex CLI     `~/.codex/config.toml` `[mcp_servers.enact]`, plus
                `~/.codex/rules/enact.rules` execpolicy and `AGENTS.md`.

Everything written is marker-guarded, so installing twice is idempotent and
uninstalling removes exactly what the installer added.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import aliases
from .model import Registry

SERVER_KEY = "enact"
BEGIN = "<!-- enact-bridge:begin -->"
END = "<!-- enact-bridge:end -->"

# Codex execpolicy rule files are parsed as Starlark, so their markers and
# comments have to be valid Starlark too.
BEGIN_RULES = "# enact-bridge:begin"
END_RULES = "# enact-bridge:end"

# TOML comments start with '#'.
BEGIN_TOML = "# enact-bridge:begin"
END_TOML = "# enact-bridge:end"

PROTOTYPE_DIR = Path(__file__).resolve().parent.parent
SERVE_SCRIPT = PROTOTYPE_DIR / "serve.py"

CLAUDE_MCP_NAME = "enact"
CODEX_MCP_NAME = "enact"

# The two servers the bridge can point a host at.
SERVER_PYTHON = "python"
SERVER_NATIVE = "native"


def native_server_command(workspace: Path, binary: str = "enact-agent") -> dict[str, Any]:
    """The stdio command for the native Enact MCP server.

    `enact-agent mcp serve` exposes the same canonical registry from inside the
    product binary, so a host can be pointed at the real thing instead of the
    Python prototype.
    """
    return {
        "command": binary,
        "args": ["mcp", "serve", "--workspace", str(workspace)],
        "env": {},
    }


@dataclass
class InstallReport:
    host: str
    scope: str
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dry_run: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "scope": self.scope,
            "written": self.written,
            "skipped": self.skipped,
            "notes": self.notes,
            "dry_run": self.dry_run,
        }


# --------------------------------------------------------------------- helpers
def server_command(workspace: Path, server: str = SERVER_PYTHON) -> dict[str, Any]:
    """The stdio command a host should run to start the bridge."""
    if server == SERVER_NATIVE:
        return native_server_command(workspace)
    return {
        "command": sys.executable or "python3",
        "args": [str(SERVE_SCRIPT)],
        "env": {"ENACT_BRIDGE_WORKSPACE": str(workspace)},
    }


def _write_text(path: Path, content: str, report: InstallReport, dry_run: bool) -> None:
    if dry_run:
        report.written.append(f"{path} (dry run)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    report.written.append(str(path))


def _merge_block(existing: str, block: str, begin: str = BEGIN, end: str = END) -> str:
    """Replace the marker-guarded block in `existing` with `block`."""
    if begin in existing and end in existing:
        start = existing.index(begin)
        finish = existing.index(end) + len(end)
        return existing[:start] + block + existing[finish:]
    if begin in existing and end not in existing:
        # A dangling begin marker: drop it rather than nest a second block.
        existing = existing.replace(begin, "", 1)
    if existing.strip():
        return existing.rstrip() + "\n\n" + block + "\n"
    return block + "\n"


def _strip_block(existing: str, begin: str = BEGIN, end: str = END) -> str:
    if begin in existing and end in existing:
        start = existing.index(begin)
        finish = existing.index(end) + len(end)
        return (existing[:start] + existing[finish:]).strip() + "\n"
    return existing


def _remove_toml_table(text: str, dotted: str) -> str:
    """Drop a `[a.b]` table and its body from a TOML document.

    A TOML file cannot declare the same table twice, so an existing
    `[mcp_servers.enact]` has to go before a new one is written.
    """
    header = f"[{dotted}]"
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            inside = stripped == header
        if not inside:
            out.append(line)
    return "".join(out)


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# -------------------------------------------------------------- shared content
def agents_block(registry: Registry, hosts: list[str] | None = None) -> str:
    """The shared instruction block.

    One block, one registry: the bridge serves the same canonical surface to
    every host, so the block describes the bridge rather than one installer.
    """
    stats = registry.stats()
    return f"""{BEGIN}
## enact-bridge — one canonical tool registry

This project is wired to **enact-bridge**, an MCP server that publishes enact-agent's
tool surface as a single canonical registry. The same registry is served to
Codex CLI and Claude Code.

- Canonical tools: **{stats['canonical_tools']}** (from {stats['source_tools']} enact-agent tools)
- Operations preserved: **{stats['operations']}** — consolidation merges sibling
  tools, it never drops an operation
- Discover tools with `mcp_search` (by intent), run them with `mcp_call`
  (by canonical name + `action`)

Consolidated families use a typed `action` enum: one canonical tool, several
operations. `mcp_search` returns the exact action names.

Do not guess canonical tool names — call `mcp_search` first. A host's own tool
vocabulary (`Bash`, `Read`, `Grep`, …) is mapped onto the canonical registry,
and the host's own permission rules apply to the canonical tool.
{END}"""


def claude_permissions_block(registry: Registry) -> dict[str, Any]:
    """Claude Code permission entries for the bridge's own surface."""
    allow = [
        f"mcp__{CLAUDE_MCP_NAME}__{aliases.BRIDGE_TOOLS[0]}",
        f"mcp__{CLAUDE_MCP_NAME}__{aliases.BRIDGE_TOOLS[1]}",
    ]
    return {"allow": allow, "ask": [], "deny": []}


def codex_rules_block() -> str:
    """Execpolicy rules for the commands the bridge is allowed to run.

    Codex execpolicy gates shell commands, so these rules cover the command
    families the bridge's `shell` tool can reach. `forbidden` stays forbidden.
    """
    return f"""{BEGIN_RULES}
# enact-bridge execpolicy
# allow the read-only command families the bridge's shell tool needs
prefix_rule(pattern = ["git", "status"], decision = "allow")
prefix_rule(pattern = ["git", "log"], decision = "allow")
prefix_rule(pattern = ["git", "diff"], decision = "allow")
prefix_rule(pattern = ["ls"], decision = "allow")
prefix_rule(pattern = ["cat"], decision = "allow")
prefix_rule(pattern = ["rg"], decision = "allow")
prefix_rule(pattern = ["find"], decision = "allow")
# destructive shapes stay forbidden
prefix_rule(pattern = ["rm", "-rf"], decision = "forbidden")
prefix_rule(pattern = ["sudo"], decision = "forbidden")
{END_RULES}
"""


# ------------------------------------------------------------------- Claude Code
# The skill file is shared by both hosts, so its body never depends on
# which installer wrote it last.
SHARED_SKILL_HOSTS = ["Codex CLI", "Claude Code"]


def skill_markdown(registry: Registry, hosts: list[str]) -> str:
    """The portable skill body.

    The same file is installed into every host's skill directory, so both
    hosts load one instruction set rather than two that drift.
    """
    stats = registry.stats()
    host_list = " and ".join(hosts) if hosts else "the coding host"
    return f"""---
name: enact-bridge
description: Use when a task needs Enact's tool registry - reading or writing files, searching code, running shell commands, scheduling jobs, memory, or any other built-in capability. The registry is reached through the enact MCP server's mcp_search and mcp_call tools.
---

# Enact tool registry

Enact's built-in tools are served to {host_list} through one MCP server.
The registry holds **{stats['canonical_tools']} canonical tools** carrying
**{stats['operations']} operations** — sibling tools are consolidated behind a
typed `action` enum, and no operation is lost in the merge.

## How to use it

1. **Find the tool first.** `mcp_search` takes a plain-language query and
   returns the canonical tool names, their actions and their parameters.
   Do not guess a tool name.
2. **Then call it.** `mcp_call` takes `tool`, an optional `action`, and
   `arguments`.

```json
{{"tool": "file_read", "arguments": {{"path": "README.md"}}}}
{{"tool": "cron", "action": "schedule_add", "arguments": {{"...": "..."}}}}
```

Consolidated families (cron, sop, memory, a2a, sessions, model, mcp, cloud,
file_upload, email) expose several operations under one tool. `mcp_search`
returns the exact `action` names; a family without an `action` is a mistake.

## What the host's own rules mean here

The canonical registry is shared, but policy is not. The host's own permission
rules apply to the canonical tool: a rule about the host's own `Grep` also
governs the registry's `content_search`. A tool the host forbids is refused
here too, with the host's reason.
"""


def write_skill_files(project: Path, registry: Registry, hosts: list[str]) -> list[str]:
    """Install the same skill into every host's skill directory."""
    body = skill_markdown(registry, hosts)
    written: list[str] = []
    for relative in (
        Path(".claude") / "skills" / "enact-bridge" / "SKILL.md",
        Path(".codex") / "skills" / "enact-bridge" / "SKILL.md",
    ):
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
        written.append(str(target))
    return written


def install_claude_code(
    project: Path,
    registry: Registry,
    scope: str = "project",
    dry_run: bool = False,
    write_permissions: bool = True,
    python: str | None = None,
    server: str = SERVER_PYTHON,
) -> InstallReport:
    report = InstallReport(host=aliases.CLAUDE_CODE, scope=scope, dry_run=dry_run)
    project = Path(project).resolve()
    cmd = server_command(project, server)
    if python:
        cmd["command"] = python

    if scope == "project":
        mcp_path = project / ".mcp.json"
        existing: dict[str, Any] = {}
        if mcp_path.exists():
            try:
                existing = json.loads(mcp_path.read_text())
            except ValueError:
                report.notes.append(f"{mcp_path} was not valid JSON; rewriting it")
                existing = {}
        servers = existing.setdefault("mcpServers", {})
        servers[CLAUDE_MCP_NAME] = cmd
        _write_text(mcp_path, json.dumps(existing, indent=2) + "\n", report, dry_run)
    else:
        claude = shutil.which("claude")
        if not claude:
            report.skipped.append("claude CLI not found; cannot add a user-scope server")
        else:
            argv = [claude, "mcp", "add", CLAUDE_MCP_NAME, "--scope", scope]
            for key, value in (cmd.get("env") or {}).items():
                argv += ["-e", f"{key}={value}"]
            argv += ["--", cmd["command"], *cmd["args"]]
            code, out = _run(argv)
            if code == 0:
                report.written.append(f"claude mcp add ({scope})")
            else:
                report.skipped.append(f"claude mcp add failed: {out.strip()}")
                report.notes.append(
                    "write .mcp.json manually with the command shown by `bridge.py install --dry-run`"
                )

    # project instructions: AGENTS.md is the canonical file both hosts read
    agents_path = project / "AGENTS.md"
    block = agents_block(registry, ["Claude Code"])
    current = agents_path.read_text() if agents_path.exists() else ""
    _write_text(agents_path, _merge_block(current, block), report, dry_run)

    # Claude Code does not read AGENTS.md on its own; point CLAUDE.md at it.
    claude_md = project / "CLAUDE.md"
    claude_block = f"{BEGIN}\n<!-- Claude Code: the shared instructions live in AGENTS.md -->\n@AGENTS.md\n{END}"
    current = claude_md.read_text() if claude_md.exists() else ""
    _write_text(claude_md, _merge_block(current, claude_block), report, dry_run)

    if write_permissions:
        settings_path = project / ".claude" / "settings.json"
        existing_settings: dict[str, Any] = {}
        if settings_path.exists():
            try:
                existing_settings = json.loads(settings_path.read_text())
            except ValueError:
                existing_settings = {}
        perms = existing_settings.setdefault("permissions", {})
        block_perms = claude_permissions_block(registry)
        for key, values in block_perms.items():
            merged = list(dict.fromkeys(list(perms.get(key) or []) + values))
            perms[key] = merged
        _write_text(settings_path, json.dumps(existing_settings, indent=2) + "\n", report, dry_run)

    for path in write_skill_files(project, registry, SHARED_SKILL_HOSTS):
        if dry_run:
            report.written.append(f"{path} (dry run)")
        else:
            report.written.append(path)

    return report


def uninstall_claude_code(project: Path, scope: str = "project", dry_run: bool = False) -> InstallReport:
    report = InstallReport(host=aliases.CLAUDE_CODE, scope=scope, dry_run=dry_run)
    project = Path(project).resolve()

    mcp_path = project / ".mcp.json"
    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text())
        except ValueError:
            data = {}
        servers = data.get("mcpServers") or {}
        if CLAUDE_MCP_NAME in servers:
            servers.pop(CLAUDE_MCP_NAME)
            _write_text(mcp_path, json.dumps(data, indent=2) + "\n", report, dry_run)
    if scope != "project":
        claude = shutil.which("claude")
        if claude:
            code, out = _run([claude, "mcp", "remove", CLAUDE_MCP_NAME, "--scope", scope])
            report.written.append("claude mcp remove") if code == 0 else report.skipped.append(out.strip())

    for path in (project / "AGENTS.md", project / "CLAUDE.md"):
        if path.exists():
            text = path.read_text()
            if BEGIN in text:
                _write_text(path, _strip_block(text), report, dry_run)
    for skill in (
        project / ".claude" / "skills" / "enact-bridge" / "SKILL.md",
        project / ".codex" / "skills" / "enact-bridge" / "SKILL.md",
    ):
        if skill.exists():
            if dry_run:
                report.written.append(f"{skill} (dry run)")
            else:
                skill.unlink()
                report.written.append(str(skill))
    return report


# -------------------------------------------------------------------- Codex CLI
def install_codex(
    project: Path,
    registry: Registry,
    scope: str = "user",
    dry_run: bool = False,
    python: str | None = None,
    rules_path: Path | None = None,
    server: str = SERVER_PYTHON,
) -> InstallReport:
    report = InstallReport(host=aliases.CODEX, scope=scope, dry_run=dry_run)
    project = Path(project).resolve()
    cmd = server_command(project, server)
    if python:
        cmd["command"] = python

    if scope == "project":
        config_path = project / ".codex" / "config.toml"
        existing = config_path.read_text() if config_path.exists() else ""
        # Strip our marked block first, then any stray copy of the table.
        if BEGIN_TOML in existing:
            existing = _strip_block(existing, BEGIN_TOML, END_TOML)
        existing = _remove_toml_table(existing, f"mcp_servers.{CODEX_MCP_NAME}")
        args = ", ".join(json.dumps(a) for a in cmd["args"])
        block = (
            f"{BEGIN_TOML}\n"
            f"[mcp_servers.{CODEX_MCP_NAME}]\n"
            f"command = {json.dumps(cmd['command'])}\n"
            f"args = [{args}]\n"
            f"startup_timeout_sec = 30\n"
            f"{END_TOML}"
        )
        _write_text(config_path, _merge_block(existing, block, BEGIN_TOML, END_TOML), report, dry_run)
        report.notes.append(
            "project-scoped Codex MCP servers are not listed by `codex mcp list` on "
            "every Codex build; use --scope user if the server does not appear"
        )
    else:
        codex = shutil.which("codex")
        if not codex:
            report.skipped.append("codex CLI not found; cannot add a user-scope server")
        else:
            argv = [codex, "mcp", "add", CODEX_MCP_NAME]
            for key, value in (cmd.get("env") or {}).items():
                argv += ["--env", f"{key}={value}"]
            argv += ["--", cmd["command"], *cmd["args"]]
            code, out = _run(argv)
            if code == 0:
                report.written.append(f"codex mcp add ({scope})")
            else:
                report.skipped.append(f"codex mcp add failed: {out.strip()}")

    # Codex reads AGENTS.md natively
    agents_path = project / "AGENTS.md"
    block = agents_block(registry, ["Codex CLI"])
    current = agents_path.read_text() if agents_path.exists() else ""
    _write_text(agents_path, _merge_block(current, block), report, dry_run)

    # Codex execpolicy
    rules_file = rules_path or (Path(os.path.expanduser("~/.codex/rules")) / "enact.rules")
    existing = rules_file.read_text() if rules_file.exists() else ""
    _write_text(
        rules_file,
        _merge_block(existing, codex_rules_block(), BEGIN_RULES, END_RULES),
        report,
        dry_run,
    )

    for path in write_skill_files(project, registry, SHARED_SKILL_HOSTS):
        if dry_run:
            report.written.append(f"{path} (dry run)")
        else:
            report.written.append(path)

    return report


def uninstall_codex(
    project: Path,
    scope: str = "user",
    dry_run: bool = False,
    rules_path: Path | None = None,
) -> InstallReport:
    report = InstallReport(host=aliases.CODEX, scope=scope, dry_run=dry_run)
    project = Path(project).resolve()

    if scope == "project":
        config_path = project / ".codex" / "config.toml"
        if config_path.exists():
            text = config_path.read_text()
            if BEGIN_TOML in text:
                _write_text(config_path, _strip_block(text, BEGIN_TOML, END_TOML), report, dry_run)
    else:
        codex = shutil.which("codex")
        if codex:
            code, out = _run([codex, "mcp", "remove", CODEX_MCP_NAME])
            if code == 0:
                report.written.append("codex mcp remove")
            else:
                report.skipped.append(out.strip())

    agents_path = project / "AGENTS.md"
    if agents_path.exists():
        text = agents_path.read_text()
        if BEGIN in text:
            _write_text(agents_path, _strip_block(text), report, dry_run)

    rules_file = rules_path or (Path(os.path.expanduser("~/.codex/rules")) / "enact.rules")
    if rules_file.exists():
        text = rules_file.read_text()
        if BEGIN_RULES in text:
            _write_text(rules_file, _strip_block(text, BEGIN_RULES, END_RULES), report, dry_run)
    for skill in (
        project / ".claude" / "skills" / "enact-bridge" / "SKILL.md",
        project / ".codex" / "skills" / "enact-bridge" / "SKILL.md",
    ):
        if skill.exists():
            if dry_run:
                report.written.append(f"{skill} (dry run)")
            else:
                skill.unlink()
                report.written.append(str(skill))
    return report


INSTALLERS = {
    aliases.CLAUDE_CODE: install_claude_code,
    aliases.CODEX: install_codex,
}
UNINSTALLERS = {
    aliases.CLAUDE_CODE: uninstall_claude_code,
    aliases.CODEX: uninstall_codex,
}
