"""Host vocabularies map onto the canonical registry."""
from __future__ import annotations

import unittest

from enact_bridge import aliases


class AliasTest(unittest.TestCase):
    def test_claude_code_tools_resolve(self) -> None:
        cases = {
            "Bash": "shell",
            "Read": "file_read",
            "Write": "file_write",
            "Edit": "file_edit",
            "Grep": "content_search",
            "Glob": "glob_search",
            "WebFetch": "web_fetch",
            "WebSearch": "web_search_tool",
            "Task": "spawn_subagent",
            "TodoWrite": "TodoWrite",
        }
        for host_name, canonical in cases.items():
            self.assertEqual(aliases.resolve(aliases.CLAUDE_CODE, host_name), canonical, host_name)

    def test_codex_tools_resolve(self) -> None:
        cases = {
            "shell": "shell",
            "apply_patch": "file_edit",
            "update_plan": "TodoWrite",
            "view_image": "image_info",
            "web_search": "web_search_tool",
        }
        for host_name, canonical in cases.items():
            self.assertEqual(aliases.resolve(aliases.CODEX, host_name), canonical, host_name)

    def test_mcp_tool_names_unwrap(self) -> None:
        self.assertEqual(aliases.split_mcp_name("mcp__enact__mcp_call"), ("enact", "mcp_call"))
        self.assertEqual(aliases.split_mcp_name("enact__mcp_search"), ("enact", "mcp_search"))
        self.assertEqual(aliases.resolve(aliases.CLAUDE_CODE, "mcp__enact__mcp_call"), "mcp_call")

    def test_unknown_names_do_not_resolve(self) -> None:
        self.assertIsNone(aliases.resolve(aliases.CLAUDE_CODE, "NoSuchTool"))
        self.assertIsNone(aliases.resolve_any(""))

    def test_reverse_map(self) -> None:
        names = aliases.host_names_for("content_search")
        self.assertEqual(names[aliases.CLAUDE_CODE], "Grep")
        names = aliases.host_names_for("shell")
        self.assertEqual(names[aliases.CLAUDE_CODE], "Bash")
        self.assertEqual(names[aliases.CODEX], "shell")


if __name__ == "__main__":
    unittest.main()
