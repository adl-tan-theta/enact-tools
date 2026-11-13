#!/usr/bin/env python3
"""End-to-end check of the native `enact-agent mcp serve` server.

Drives the real binary over stdio with the same JSON-RPC a host would send:
initialize, tools/list, mcp_search, then a real mcp_call that writes and reads
a file inside the workspace.

    python3 tools/verify_native_server.py --binary /path/to/zeroclaw [--workspace DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


class Client:
    """A minimal MCP stdio client."""

    def __init__(self, command: list[str], workspace: Path) -> None:
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(workspace),
            env={**os.environ, "ENACT_BRIDGE_WORKSPACE": str(workspace)},
        )
        self.next_id = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            message["params"] = params
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read() if self.proc.stderr else ""
            raise SystemExit(f"server closed the stream\nstderr:\n{stderr}")
        return json.loads(line)

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, help="path to the enact-agent binary")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--agent", default=None)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve() if args.workspace else Path(tempfile.mkdtemp()).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    command = [args.binary, "mcp", "serve", "--workspace", str(workspace)]
    if args.agent:
        command += ["--agent", args.agent]

    print(f"workspace : {workspace}")
    print(f"command   : {' '.join(command)}\n")

    client = Client(command, workspace)
    checks: list[tuple[str, bool, str]] = []
    try:
        init = client.send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "native-verify", "version": "0"},
            },
        )
        result = init.get("result", {})
        checks.append(
            (
                "initialize",
                "result" in init,
                f"protocol={result.get('protocolVersion')} server={result.get('serverInfo', {}).get('name')}",
            )
        )

        listed = client.send("tools/list")
        tools = listed.get("result", {}).get("tools", [])
        names = [tool["name"] for tool in tools]
        checks.append(
            (
                "tools/list",
                names == ["mcp_search", "mcp_call"],
                ", ".join(names),
            )
        )

        found = client.send(
            "tools/call",
            {"name": "mcp_search", "arguments": {"query": "read a file", "limit": 3}},
        )
        payload = json.loads(found["result"]["content"][0]["text"])
        top = payload["results"][0]["name"] if payload["results"] else "(none)"
        checks.append(("mcp_search", not found["result"]["isError"], f"top={top}"))

        written = client.send(
            "tools/call",
            {
                "name": "mcp_call",
                "arguments": {
                    "tool": "file_write",
                    "arguments": {"path": "native-selftest.txt", "content": "native bridge works\n"},
                },
            },
        )
        checks.append(
            ("mcp_call file_write", not written["result"]["isError"], written["result"]["content"][0]["text"][:80])
        )

        read = client.send(
            "tools/call",
            {
                "name": "mcp_call",
                "arguments": {
                    "tool": "file_read",
                    "arguments": {"path": "native-selftest.txt"},
                },
            },
        )
        text = read["result"]["content"][0]["text"]
        checks.append(
            ("mcp_call file_read", "native bridge works" in text, text.strip().splitlines()[-1][:80] if text.strip() else "")
        )
    finally:
        client.close()

    width = max(len(name) for name, _, _ in checks)
    ok = True
    for name, passed, detail in checks:
        ok = ok and passed
        print(f"  {'PASS' if passed else 'FAIL'}  {name.ljust(width)}  {detail}")
    print()
    print("NATIVE VERIFY OK" if ok else "NATIVE VERIFY FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
