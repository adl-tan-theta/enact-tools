"""The host adapters write real config, idempotently, and can undo it."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from enact_bridge import aliases
from enact_bridge.adapters import (
    BEGIN,
    END,
    install_claude_code,
    install_codex,
    uninstall_claude_code,
    uninstall_codex,
)
from enact_bridge.model import Registry


class AdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = Registry.from_path()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    # ------------------------------------------------------------- Claude Code
    def test_claude_install_writes_mcp_json_and_keeps_other_servers(self) -> None:
        mcp_path = self.project / ".mcp.json"
        mcp_path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
        report = install_claude_code(self.project, self.registry, scope="project")
        self.assertTrue(any("wrote" in w or ".mcp.json" in w for w in report.written))
        data = json.loads(mcp_path.read_text())
        self.assertIn("other", data["mcpServers"])
        self.assertIn("enact", data["mcpServers"])
        self.assertTrue(data["mcpServers"]["enact"]["args"][0].endswith("serve.py"))

    def test_claude_install_is_idempotent(self) -> None:
        install_claude_code(self.project, self.registry, scope="project")
        first = (self.project / "AGENTS.md").read_text()
        install_claude_code(self.project, self.registry, scope="project")
        second = (self.project / "AGENTS.md").read_text()
        self.assertEqual(first, second)
        self.assertEqual(first.count(BEGIN), 1)

    def test_claude_install_writes_permissions_and_claude_md(self) -> None:
        install_claude_code(self.project, self.registry, scope="project")
        settings = json.loads((self.project / ".claude" / "settings.json").read_text())
        self.assertIn("mcp__enact__mcp_call", settings["permissions"]["allow"])
        self.assertIn("@AGENTS.md", (self.project / "CLAUDE.md").read_text())

    def test_claude_uninstall_removes_only_our_block(self) -> None:
        install_claude_code(self.project, self.registry, scope="project")
        (self.project / "AGENTS.md").write_text(
            (self.project / "AGENTS.md").read_text() + "\nkeep me\n"
        )
        uninstall_claude_code(self.project, scope="project")
        text = (self.project / "AGENTS.md").read_text()
        self.assertNotIn(BEGIN, text)
        self.assertIn("keep me", text)
        data = json.loads((self.project / ".mcp.json").read_text())
        self.assertNotIn("enact", data["mcpServers"])

    # -------------------------------------------------------------------- Codex
    def test_codex_install_writes_agents_md_and_rules(self) -> None:
        rules = self.project / "rules" / "enact.rules"
        report = install_codex(
            self.project, self.registry, scope="project", dry_run=True, rules_path=rules
        )
        self.assertTrue(report.written)
        # a dry run must not touch the filesystem
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse(rules.exists())

    def test_codex_project_scope_writes_a_config_table(self) -> None:
        rules = self.project / "rules" / "enact.rules"
        install_codex(self.project, self.registry, scope="project", rules_path=rules)
        text = (self.project / ".codex" / "config.toml").read_text()
        self.assertIn("[mcp_servers.enact]", text)
        self.assertIn("serve.py", text)
        self.assertIn("prefix_rule", rules.read_text())

    def test_codex_config_is_valid_toml(self) -> None:
        import tomllib

        rules = self.project / "rules" / "enact.rules"
        install_codex(self.project, self.registry, scope="project", rules_path=rules)
        with open(self.project / ".codex" / "config.toml", "rb") as fh:
            data = tomllib.load(fh)
        self.assertIn("enact", data["mcp_servers"])

    def test_codex_install_is_idempotent(self) -> None:
        import tomllib

        rules = self.project / "rules" / "enact.rules"
        for _ in range(3):
            install_codex(self.project, self.registry, scope="project", rules_path=rules)
        text = (self.project / ".codex" / "config.toml").read_text()
        self.assertEqual(text.count("[mcp_servers.enact]"), 1)
        self.assertEqual(text.count("# enact-bridge:begin"), 1)
        with open(self.project / ".codex" / "config.toml", "rb") as fh:
            tomllib.load(fh)
        self.assertEqual(rules.read_text().count("enact-bridge:begin"), 1)

    def test_codex_rules_are_starlark_safe(self) -> None:
        """Codex parses `~/.codex/rules/*.rules` as Starlark, not as text."""
        rules = self.project / "rules" / "enact.rules"
        install_codex(self.project, self.registry, scope="project", rules_path=rules)
        text = rules.read_text()
        self.assertNotIn("<!--", text)
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            self.assertTrue(
                stripped.startswith("prefix_rule(") and stripped.endswith(")"),
                f"not a Starlark expression: {line!r}",
            )

    def test_codex_rules_are_marked_and_undoable(self) -> None:
        rules = self.project / "rules" / "enact.rules"
        install_codex(self.project, self.registry, scope="project", rules_path=rules)
        agents = (self.project / "AGENTS.md").read_text()
        self.assertIn(BEGIN, agents)
        self.assertIn(END, agents)
        self.assertIn("canonical", agents.lower())
        uninstall_codex(self.project, scope="project", rules_path=rules)
        self.assertNotIn(BEGIN, (self.project / "AGENTS.md").read_text())
        self.assertNotIn("enact-bridge:begin", rules.read_text())

    def test_uninstallers_exist_for_both_hosts(self) -> None:
        self.assertTrue(callable(uninstall_claude_code))
        self.assertTrue(callable(uninstall_codex))

    def test_agents_block_states_the_real_numbers(self) -> None:
        """The advertised numbers come from the registry, not from a literal."""
        install_claude_code(self.project, self.registry, scope="project")
        text = (self.project / "AGENTS.md").read_text()
        stats = self.registry.stats()
        self.assertIn(str(stats["canonical_tools"]), text)
        self.assertIn(str(stats["operations"]), text)


if __name__ == "__main__":
    unittest.main()
