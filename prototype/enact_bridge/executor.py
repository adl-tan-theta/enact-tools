"""Real execution for the core tools, sandboxed to a workspace root.

The prototype executes the tools that are safe and useful without a running
agent runtime — files, search, shell, calculator, and a read-mostly slice of
git. Every other tool returns an explicit, structured "not implemented in the
prototype" result that names the exact enact-agent source operation it stands
for, so nothing silently disappears.
"""
from __future__ import annotations

import fnmatch
import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import read_modes
from .model import Registry, Tool

DEFAULT_TIMEOUT_MS = 30_000
MAX_OUTPUT_BYTES = 200_000


class SandboxError(Exception):
    """Raised when a path escapes the workspace root."""


@dataclass
class ExecutionResult:
    ok: bool
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "content": self.content}
        if self.data:
            out["data"] = self.data
        if self.error:
            out["error"] = self.error
        return out


class Executor:
    """Executes canonical tools against a workspace root."""

    def __init__(self, registry: Registry, workspace: str | os.PathLike | None = None) -> None:
        self.registry = registry
        self.root = Path(workspace or os.getcwd()).resolve()

    # ------------------------------------------------------------- sandboxing
    def resolve_path(self, relative: str) -> Path:
        """Resolve a workspace-relative path, refusing to leave the root."""
        candidate = (self.root / relative).resolve() if not os.path.isabs(relative) else Path(relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise SandboxError(
                f"path {relative!r} resolves outside the workspace root {self.root}"
            ) from None
        return candidate

    def _relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    # ---------------------------------------------------------------- dispatch
    def execute(self, tool_name: str, action: str | None = None, args: dict[str, Any] | None = None) -> ExecutionResult:
        args = dict(args or {})
        tool = self.registry.get(tool_name)
        if tool is None:
            return ExecutionResult(False, f"unknown canonical tool {tool_name!r}", error="unknown_tool")
        if tool.disabled:
            return ExecutionResult(
                False,
                f"tool {tool_name!r} is compiled out of the Enact build and is not exposed",
                error="disabled_tool",
            )
        try:
            resolved_action = tool.resolve_action(action)
        except KeyError as exc:
            return ExecutionResult(False, str(exc), error="unknown_action")

        # `action` is part of the schema for family tools; strip it before the
        # operation body sees it.
        args.pop("action", None)

        handler = getattr(self, f"_op_{tool_name}", None)
        if handler is None:
            source_tool, source_op = tool.source_of(resolved_action)
            return ExecutionResult(
                False,
                (
                    f"{tool_name}.{resolved_action} is not implemented in the prototype. "
                    f"It maps to enact-agent's {source_tool}.{source_op} "
                    f"({tool.source_files[0] if tool.source_files else 'n/a'}). "
                    "Run enact-agent for the full implementation."
                ),
                data={
                    "canonical_tool": tool_name,
                    "action": resolved_action,
                    "source_tool": source_tool,
                    "source_operation": source_op,
                    "implemented": False,
                },
                error="not_implemented",
            )

        try:
            return handler(tool, resolved_action, args)
        except SandboxError as exc:
            return ExecutionResult(False, str(exc), error="sandbox_violation")
        except FileNotFoundError as exc:
            return ExecutionResult(False, f"not found: {exc.filename}", error="not_found")
        except Exception as exc:  # pragma: no cover - defensive
            return ExecutionResult(False, f"{type(exc).__name__}: {exc}", error="execution_failed")

    # ------------------------------------------------------------ core tools
    def _op_shell(self, tool: Tool, action: str, args: dict[str, Any]) -> ExecutionResult:
        command = args.get("command")
        if not command:
            return ExecutionResult(False, "shell requires a 'command' argument", error="invalid_arguments")
        cwd = self.root
        if args.get("cwd"):
            cwd = self.resolve_path(str(args["cwd"]))
        timeout_ms = int(args.get("timeout_ms") or DEFAULT_TIMEOUT_MS)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.root),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "ENACT_WORKSPACE": str(self.root),
        }
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, f"command timed out after {timeout_ms} ms", error="timeout")
        stdout = (proc.stdout or "")[:MAX_OUTPUT_BYTES]
        stderr = (proc.stderr or "")[:MAX_OUTPUT_BYTES]
        content = stdout if not stderr else f"{stdout}\n[stderr]\n{stderr}"
        return ExecutionResult(
            proc.returncode == 0,
            content or f"(exit {proc.returncode}, no output)",
            data={"exit_code": proc.returncode, "stdout": stdout, "stderr": stderr, "cwd": str(cwd)},
            error=None if proc.returncode == 0 else "non_zero_exit",
        )

    def _op_file_read(self, tool: Tool, action: str, args: dict[str, Any]) -> ExecutionResult:
        path = self.resolve_path(str(args.get("path", "")))
        if not path.exists():
            return ExecutionResult(False, f"file not found: {args.get('path')}", error="not_found")
        if path.is_dir():
            return ExecutionResult(False, f"path is a directory: {args.get('path')}", error="invalid_arguments")
        text = path.read_text(errors="replace")
        mode = str(args.get("mode") or "")
        if mode and mode != "full":
            # The read modes answer a smaller question than "give me the
            # file". They are a parameter of the read operation, exactly as
            # in the native server's file_read.
            rendered = read_modes.render(mode, text, args)
            return ExecutionResult(
                True,
                rendered,
                data={"path": self._relative(path), "mode": mode},
            )
        lines = text.splitlines()
        offset = int(args.get("offset") or 1)
        limit = args.get("limit")
        selected = lines[offset - 1 :]
        if limit:
            selected = selected[: int(limit)]
        body = "\n".join(f"{offset + i}\t{line}" for i, line in enumerate(selected))
        return ExecutionResult(True, body or "(empty)", data={"path": self._relative(path), "lines": len(selected)})

    def _op_file_write(self, tool: Tool, action: str, args: dict[str, Any]) -> ExecutionResult:
        path = self.resolve_path(str(args.get("path", "")))
        content = args.get("content")
        if content is None:
            return ExecutionResult(False, "file_write requires a 'content' argument", error="invalid_arguments")
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        path.write_text(str(content))
        return ExecutionResult(
            True,
            f"{'updated' if existed else 'created'} {self._relative(path)} ({len(str(content))} bytes)",
            data={"path": self._relative(path), "created": not existed},
        )

    def _op_file_edit(self, tool: Tool, action: str, args: dict[str, Any]) -> ExecutionResult:
        path = self.resolve_path(str(args.get("path", "")))
        old = args.get("old_string")
        new = args.get("new_string")
        if old is None or new is None:
            return ExecutionResult(
                False, "file_edit requires 'old_string' and 'new_string'", error="invalid_arguments"
            )
        if not path.exists():
            return ExecutionResult(False, f"file not found: {args.get('path')}", error="not_found")
        text = path.read_text()
        if old not in text:
            return ExecutionResult(False, "old_string not found in file", error="no_match")
        count = text.count(old)
        text = text.replace(old, str(new))
        path.write_text(text)
        return ExecutionResult(
            True,
            f"replaced {count} occurrence(s) in {self._relative(path)}",
            data={"path": self._relative(path), "replacements": count},
        )

    def _op_glob_search(self, tool: Tool, action: str, args: dict[str, Any]) -> ExecutionResult:
        pattern = str(args.get("pattern") or "*")
        subtree = args.get("path") or "."
        base = self.resolve_path(str(subtree))
        matches: list[str] = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__", ".venv"}]
            for fname in filenames:
                rel = str(Path(dirpath, fname).relative_to(base))
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(fname, pattern):
                    matches.append(str(Path(dirpath, fname).relative_to(self.root)))
        matches.sort()
        return ExecutionResult(
            True,
            "\n".join(matches) or "(no matches)",
            data={"pattern": pattern, "base": self._relative(base), "count": len(matches)},
        )

    def _op_content_search(self, tool: Tool, action: str, args: dict[str, Any]) -> ExecutionResult:
        pattern = str(args.get("pattern") or "")
        if not pattern:
            return ExecutionResult(False, "content_search requires a 'pattern'", error="invalid_arguments")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return ExecutionResult(False, f"invalid regular expression: {exc}", error="invalid_arguments")
        subtree = args.get("path") or "."
        base = self.resolve_path(str(subtree))
        limit = int(args.get("max_results") or 100)
        hits: list[str] = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__", ".venv"}]
            for fname in filenames:
                fpath = Path(dirpath, fname)
                try:
                    text = fpath.read_text(errors="ignore")
                except OSError:
                    continue
                for lineno, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        rel = fpath.relative_to(self.root)
                        hits.append(f"{rel}:{lineno}: {line.strip()[:200]}")
                        if len(hits) >= limit:
                            break
                if len(hits) >= limit:
                    break
            if len(hits) >= limit:
                break
        return ExecutionResult(
            True,
            "\n".join(hits) or "(no matches)",
            data={"pattern": pattern, "count": len(hits), "truncated": len(hits) >= limit},
        )

    def _op_calculator(self, tool: Tool, action: str, args: dict[str, Any]) -> ExecutionResult:
        expression = args.get("expression") or args.get("input") or args.get("value")
        if not expression:
            return ExecutionResult(False, "calculator requires an 'expression'", error="invalid_arguments")
        allowed = re.compile(r"^[0-9+\-*/().% ]+$")
        if not allowed.match(str(expression)):
            return ExecutionResult(False, "expression contains disallowed characters", error="invalid_arguments")
        try:
            value = eval(str(expression), {"__builtins__": {}}, {})  # noqa: S307 - chars are whitelisted above
        except Exception as exc:
            return ExecutionResult(False, f"could not evaluate: {exc}", error="invalid_arguments")
        return ExecutionResult(True, str(value), data={"expression": expression, "value": value})

    def _op_git_operations(self, tool: Tool, action: str, args: dict[str, Any]) -> ExecutionResult:
        """A read-mostly slice of git; write actions are refused by design."""
        readonly = {"status", "log", "diff", "list", "branch", "show"}
        if action not in readonly:
            return ExecutionResult(
                False,
                f"git_operations.{action} is not executable in the prototype (read-only slice: {', '.join(sorted(readonly))})",
                error="not_implemented",
            )
        cmd = ["git", action]
        if action == "log":
            cmd += ["--oneline", "-n", str(int(args.get("limit") or 20))]
        if action == "diff":
            if args.get("staged"):
                cmd.append("--staged")
            if args.get("path"):
                cmd.append(str(args["path"]))
        if action == "status":
            cmd.append("--short")
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT_MS / 1000,
                env={**os.environ, "GIT_PAGER": "cat"},
            )
        except FileNotFoundError:
            return ExecutionResult(False, "git executable not found", error="not_found")
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, "git command timed out", error="timeout")
        out = (proc.stdout or proc.stderr or "").strip()
        return ExecutionResult(
            proc.returncode == 0,
            out or f"(exit {proc.returncode})",
            data={"exit_code": proc.returncode, "argv": cmd},
            error=None if proc.returncode == 0 else "non_zero_exit",
        )

    # ------------------------------------------------------------------ utils
    @staticmethod
    def shell_words(command: str) -> list[str]:
        try:
            return shlex.split(command)
        except ValueError:
            return command.split()
