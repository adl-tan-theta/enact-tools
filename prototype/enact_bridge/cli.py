"""Command line entry point for the bridge."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__, aliases
from .adapters import INSTALLERS, UNINSTALLERS
from .discovery import detail, search
from .executor import Executor
from .model import DEFAULT_REGISTRY_PATH, Registry
from .policy import ClaudeCodePolicy, CodexPolicy
from .server import BridgeServer, serve_stdio

HOST_CHOICES = (aliases.CLAUDE_CODE, aliases.CODEX)


def _registry(path: str | None) -> Registry:
    return Registry.from_path(path)


# --------------------------------------------------------------------- commands
def cmd_serve(args: argparse.Namespace) -> int:
    registry = _registry(args.registry)
    workspace = args.workspace or os.environ.get("ENACT_BRIDGE_WORKSPACE") or os.getcwd()
    if args.expose == "full":
        print(
            f"[enact-bridge] exposing {len(registry.enabled_tools())} canonical tools "
            f"({registry.enabled_operation_count} operations) over stdio",
            file=sys.stderr,
        )
    else:
        print(
            f"[enact-bridge] exposing mcp_search + mcp_call over a canonical registry of "
            f"{len(registry)} tools / {registry.operation_count} operations",
            file=sys.stderr,
        )
    serve_stdio(registry, workspace=workspace, expose=args.expose)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    registry = _registry(args.registry)
    if args.json:
        print(json.dumps(registry.stats(), indent=2))
        return 0
    stats = registry.stats()
    print(f"canonical tools : {stats['canonical_tools']}")
    print(f"enabled tools  : {stats['enabled_tools']}")
    print(f"operations     : {stats['operations']} ({stats['enabled_operations']} enabled)")
    print(f"source tools   : {stats['source_tools']}")
    print(f"tiers          : {stats['tiers']}")
    print()
    for tool in registry.tools:
        flag = " (compiled out)" if tool.disabled else ""
        merged = f"  <- {', '.join(tool.merged_from)}" if len(tool.merged_from) > 1 else ""
        print(f"  {tool.name:22s} {tool.tier:8s} {len(tool.operations):3d} ops{flag}{merged}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    registry = _registry(args.registry)
    if args.tool:
        info = detail(registry, args.tool)
        if not info:
            print(f"unknown canonical tool {args.tool!r}", file=sys.stderr)
            return 1
        print(json.dumps(info, indent=2))
        return 0
    result = search(registry, args.query, limit=args.limit)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"query: {result['query']!r}   matched {result['matched']} of {result['registry_tools']} tools")
    for entry in result["results"]:
        print(f"\n  {entry['name']}  [{entry['tier']}]  score={entry['score']}")
        print(f"    {entry['description']}")
        print(f"    actions: {', '.join(entry['actions'])}")
    return 0


def cmd_call(args: argparse.Namespace) -> int:
    registry = _registry(args.registry)
    workspace = args.workspace or os.getcwd()
    call_args: dict[str, Any] = {}
    if args.args:
        try:
            call_args = json.loads(args.args)
        except ValueError as exc:
            print(f"--args is not valid JSON: {exc}", file=sys.stderr)
            return 1
    executor = Executor(registry, workspace)
    result = executor.execute(args.tool, args.action, call_args)
    print(result.content)
    if result.data:
        print(json.dumps(result.data, indent=2))
    return 0 if result.ok else 1


def cmd_install(args: argparse.Namespace) -> int:
    registry = _registry(args.registry)
    project = Path(args.project or os.getcwd()).resolve()
    hosts = HOST_CHOICES if args.host == "both" else (args.host,)
    for host in hosts:
        report = INSTALLERS[host](
            project,
            registry,
            scope=args.scope,
            dry_run=args.dry_run,
            server=args.server,
        )
        print(f"[{host}] scope={report.scope}{' (dry run)' if report.dry_run else ''}")
        for path in report.written:
            print(f"  wrote   {path}")
        for path in report.skipped:
            print(f"  skipped {path}")
        for note in report.notes:
            print(f"  note    {note}")
        print()
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    project = Path(args.project or os.getcwd()).resolve()
    hosts = HOST_CHOICES if args.host == "both" else (args.host,)
    for host in hosts:
        report = UNINSTALLERS[host](project, scope=args.scope, dry_run=args.dry_run)
        print(f"[{host}] scope={report.scope}")
        for path in report.written:
            print(f"  removed {path}")
        for path in report.skipped:
            print(f"  skipped {path}")
    return 0


def cmd_policy(args: argparse.Namespace) -> int:
    hosts = HOST_CHOICES if args.host == "both" else (args.host,)
    payload: dict[str, Any] = {}
    for host in hosts:
        policy = ClaudeCodePolicy() if host == aliases.CLAUDE_CODE else CodexPolicy()
        payload[host] = policy.summary()
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0
    for host, summary in payload.items():
        print(f"[{host}]")
        for key, value in summary.items():
            if isinstance(value, list) and len(value) > 6:
                print(f"  {key}: {len(value)} entries")
                for item in value[:6]:
                    print(f"      {item}")
                print("      ...")
            else:
                print(f"  {key}: {value}")
        print()
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Self-check: registry integrity, a live MCP handshake, and host reachability."""
    import shutil
    import subprocess
    import tempfile

    ok = True
    checks: list[tuple[str, bool, str]] = []

    registry = _registry(args.registry)
    stats = registry.stats()
    checks.append(("registry loads", True, f"{stats['canonical_tools']} canonical tools"))

    # The expectations are derived from the source inventory, never written
    # down: the registry is generated from that inventory, so a hard-coded
    # count would only ever report its own staleness.
    csv_path = Path(DEFAULT_REGISTRY_PATH).parent.parent.parent / "zeroclaw-tools-operations.csv"
    import csv as _csv

    source_tools: set[str] = set()
    source_pairs: set[tuple[str, str]] = set()
    with open(csv_path, newline="") as fh:
        for row in _csv.DictReader(fh):
            source_tools.add(row["tool_name"])
            source_pairs.add((row["tool_name"], row["operation"]))

    # The consolidation invariant: the canonical tools are exactly the source
    # tools the families did not absorb, plus the families themselves. It is
    # derived from the source inventory and the registry's own merge
    # metadata, never from a number written down here.
    merged = {member for tool in registry.tools for member in tool.merged_from}
    family_names = {tool.name for tool in registry.tools if tool.merged_from}
    expected_names = (source_tools - merged) | family_names
    actual_names = {tool.name for tool in registry.tools}

    checks.append(
        (
            "operation count preserved",
            stats["operations"] == len(source_pairs),
            f"{stats['operations']} operations (source inventory has {len(source_pairs)})",
        )
    )
    checks.append(
        (
            "consolidation ratio",
            actual_names == expected_names,
            f"{stats['source_tools']} source tools -> {stats['canonical_tools']} canonical",
        )
    )
    disabled = [t.name for t in registry.tools if t.disabled]
    checks.append(("compiled-out tools flagged", bool(disabled), f"{len(disabled)} disabled"))

    # every source operation is reachable exactly once
    if csv_path.exists():
        reachable = set()
        for tool in registry.tools:
            for op in tool.op_list:
                reachable.add((op.tool, op.operation))
        checks.append(
            ("no operation lost or duplicated", source_pairs == reachable, f"{len(reachable)} reachable pairs")
        )
    else:
        checks.append(("source inventory reachable", False, f"{csv_path} not found"))

    # live MCP handshake through a real subprocess
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "serve.py"), "--workspace", tmp],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        try:
            def send(msg):
                proc.stdin.write(json.dumps(msg) + "\n")
                proc.stdin.flush()
                return json.loads(proc.stdout.readline())

            init = send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "enact-bridge-selftest", "version": "0"},
                    },
                }
            )
            checks.append(("MCP initialize", "result" in init, init.get("result", {}).get("protocolVersion", "")))
            listed = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            names = [t["name"] for t in listed.get("result", {}).get("tools", [])]
            checks.append(("MCP tools/list", names == ["mcp_search", "mcp_call"], ", ".join(names)))
            found = send(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "mcp_search", "arguments": {"query": "read a file"}},
                }
            )
            checks.append(("MCP mcp_search", not found.get("result", {}).get("isError", False), ""))
            written = send(
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "mcp_call",
                        "arguments": {
                            "tool": "file_write",
                            "arguments": {"path": "selftest.txt", "content": "hello"},
                        },
                    },
                }
            )
            read = send(
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "mcp_call",
                        "arguments": {"tool": "file_read", "arguments": {"path": "selftest.txt"}},
                    },
                }
            )
            text = read.get("result", {}).get("content", [{}])[0].get("text", "")
            checks.append(
                (
                    "MCP write then read",
                    not written.get("result", {}).get("isError", False) and "hello" in text,
                    text.strip().splitlines()[-1] if text.strip() else "",
                )
            )
        finally:
            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=10)

    for host, cli in (("claude-code", "claude"), ("codex", "codex")):
        found = shutil.which(cli)
        checks.append((f"{host} CLI present", bool(found), found or "not found"))

    width = max(len(name) for name, _, _ in checks)
    for name, passed, detail in checks:
        ok = ok and passed
        print(f"  {'PASS' if passed else 'FAIL'}  {name.ljust(width)}  {detail}")
    print()
    print("VERIFY OK" if ok else "VERIFY FAILED")
    return 0 if ok else 1


# ---------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="enact-bridge", description=__doc__)
    parser.add_argument("--version", action="version", version=f"enact-bridge {__version__}")
    parser.add_argument("--registry", default=None, help="path to registry.generated.json")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the MCP stdio server")
    p.add_argument("--expose", choices=("minimal", "full"), default="minimal")
    p.add_argument("--workspace", default=None)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("show", help="show the canonical registry")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("search", help="search the canonical registry")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--tool", default=None, help="exact canonical tool name")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("call", help="run one canonical tool")
    p.add_argument("tool")
    p.add_argument("--action", default=None)
    p.add_argument("--args", default=None, help="JSON object of arguments")
    p.add_argument("--workspace", default=None)
    p.set_defaults(func=cmd_call)

    p = sub.add_parser("install", help="install the bridge into a host")
    p.add_argument("--host", choices=(*HOST_CHOICES, "both"), default="both")
    p.add_argument("--scope", choices=("project", "user", "local"), default="project")
    p.add_argument("--project", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--server",
        choices=("python", "native"),
        default="python",
        help="Which server the host should run: the Python prototype or `enact-agent mcp serve`.",
    )
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("uninstall", help="remove the bridge from a host")
    p.add_argument("--host", choices=(*HOST_CHOICES, "both"), default="both")
    p.add_argument("--scope", choices=("project", "user", "local"), default="project")
    p.add_argument("--project", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("policy", help="show each host's own policy")
    p.add_argument("--host", choices=(*HOST_CHOICES, "both"), default="both")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_policy)

    p = sub.add_parser("verify", help="run the bridge self-check")
    p.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
