"""The MCP server speaks the protocol both hosts expect."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from enact_bridge.model import Registry
from enact_bridge.server import BridgeServer, serve_stdio

PROTOTYPE = Path(__file__).resolve().parent.parent


class ServerProtocolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = Registry.from_path()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = BridgeServer(self.registry, workspace=self.tmp.name)

    def call(self, method: str, params=None, msg_id=1):
        message = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            message["params"] = params
        return self.server.handle(message)

    def notify(self, method: str, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        return self.server.handle(message)

    def test_initialize(self) -> None:
        result = self.call(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "claude-code", "version": "2.0.0"},
            },
        )
        payload = result["result"]
        self.assertEqual(payload["protocolVersion"], "2024-11-05")
        self.assertIn("tools", payload["capabilities"])
        self.assertEqual(payload["serverInfo"]["name"], "enact-bridge")
        self.assertIn("mcp_search", payload["instructions"])

    def test_initialize_echoes_a_known_newer_version(self) -> None:
        result = self.call(
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "codex"}},
        )
        self.assertEqual(result["result"]["protocolVersion"], "2025-06-18")

    def test_notification_gets_no_response(self) -> None:
        self.assertIsNone(self.notify("notifications/initialized"))

    def test_unknown_method(self) -> None:
        response = self.call("does/not/exist")
        self.assertEqual(response["error"]["code"], -32601)

    def test_minimal_tool_surface(self) -> None:
        tools = self.call("tools/list")["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["mcp_search", "mcp_call"])
        for tool in tools:
            self.assertIn("inputSchema", tool)
            self.assertIn("description", tool)

    def test_full_tool_surface(self) -> None:
        server = BridgeServer(self.registry, workspace=self.tmp.name, expose="full")
        server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "codex"}}})
        tools = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertEqual(len(names), len(self.registry.enabled_tools()) + 2)
        self.assertIn("cron", names)
        self.assertNotIn("notion", names)  # compiled out of the Enact build

    def test_search_then_call(self) -> None:
        found = self.call(
            "tools/call", {"name": "mcp_search", "arguments": {"query": "read a file"}}, msg_id=2
        )
        self.assertFalse(found["result"]["isError"])
        payload = json.loads(found["result"]["content"][0]["text"])
        self.assertEqual(payload["results"][0]["name"], "file_read")

        written = self.call(
            "tools/call",
            {
                "name": "mcp_call",
                "arguments": {"tool": "file_write", "arguments": {"path": "x.txt", "content": "hi"}},
            },
            msg_id=3,
        )
        self.assertFalse(written["result"]["isError"])
        read = self.call(
            "tools/call",
            {"name": "mcp_call", "arguments": {"tool": "file_read", "arguments": {"path": "x.txt"}}},
            msg_id=4,
        )
        self.assertIn("hi", read["result"]["content"][0]["text"])

    def test_family_action_is_required_and_routed(self) -> None:
        response = self.call(
            "tools/call",
            {"name": "mcp_call", "arguments": {"tool": "cron", "action": "cron_add"}},
            msg_id=5,
        )
        text = response["result"]["content"][0]["text"]
        # cron is not implemented in the prototype, but the action routed correctly
        # and the result names the enact-agent source operation.
        self.assertIn("cron_add.add", text)

    def test_unknown_action_is_reported(self) -> None:
        response = self.call(
            "tools/call",
            {"name": "mcp_call", "arguments": {"tool": "cron", "action": "nope"}},
            msg_id=6,
        )
        self.assertTrue(response["result"]["isError"])
        self.assertIn("unknown action", response["result"]["content"][0]["text"])

    def test_unknown_tool_is_reported(self) -> None:
        response = self.call(
            "tools/call", {"name": "mcp_call", "arguments": {"tool": "not_a_tool"}}, msg_id=7
        )
        self.assertTrue(response["result"]["isError"])

    def test_disabled_tool_is_refused(self) -> None:
        response = self.call(
            "tools/call", {"name": "mcp_call", "arguments": {"tool": "notion"}}, msg_id=8
        )
        self.assertTrue(response["result"]["isError"])
        self.assertIn("compiled out", response["result"]["content"][0]["text"])

    def test_prompts_and_resources_are_empty(self) -> None:
        self.assertEqual(self.call("prompts/list")["result"]["prompts"], [])
        self.assertEqual(self.call("resources/list")["result"]["resources"], [])


class StdioTransportTest(unittest.TestCase):
    def test_round_trip_over_a_real_pipe(self) -> None:
        registry = Registry.from_path()
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.Popen(
                [sys.executable, str(PROTOTYPE / "serve.py"), "--workspace", tmp],
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
                            "clientInfo": {"name": "codex-cli", "version": "1"},
                        },
                    }
                )
                self.assertEqual(init["result"]["protocolVersion"], "2024-11-05")
                listed = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
                self.assertEqual(len(listed["result"]["tools"]), 2)
                called = send(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "mcp_call",
                            "arguments": {
                                "tool": "shell",
                                "arguments": {"command": "echo bridged"},
                            },
                        },
                    }
                )
                self.assertIn("bridged", called["result"]["content"][0]["text"])
            finally:
                proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=10)
                if proc.stdout:
                    proc.stdout.close()


if __name__ == "__main__":
    unittest.main()
