"""The policy layer mirrors each host's own rules."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from enact_bridge.policy import ALLOW, FORBIDDEN, PROMPT, ClaudeCodePolicy, CodexPolicy


class ClaudeCodePolicyTest(unittest.TestCase):
    def _policy(self, permissions: dict) -> ClaudeCodePolicy:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"permissions": permissions}, tmp)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return ClaudeCodePolicy(tmp.name)

    def test_deny_wins(self) -> None:
        policy = self._policy({"allow": ["Read"], "deny": ["Read"]})
        decision = policy.decide("file_read")
        self.assertEqual(decision.decision, FORBIDDEN)

    def test_allow_grants(self) -> None:
        policy = self._policy({"allow": ["Read"]})
        self.assertEqual(policy.decide("file_read").decision, ALLOW)

    def test_unmatched_asks(self) -> None:
        policy = self._policy({"allow": []})
        self.assertEqual(policy.decide("file_read").decision, PROMPT)

    def test_ask_rule_prompts(self) -> None:
        policy = self._policy({"allow": ["Read"], "ask": ["Read"]})
        self.assertEqual(policy.decide("file_read").decision, PROMPT)

    def test_host_vocabulary_rule_reaches_the_canonical_tool(self) -> None:
        """A Claude Code rule about `Grep` governs the canonical `content_search`."""
        policy = self._policy({"deny": ["Grep"]})
        self.assertEqual(policy.decide("content_search").decision, FORBIDDEN)
        self.assertEqual(policy.decide("file_read").decision, PROMPT)

    def test_bash_specifier_matches_the_command(self) -> None:
        policy = self._policy({"allow": ["Bash(git status)"]})
        self.assertEqual(policy.decide("shell", args={"command": "git status"}).decision, ALLOW)
        self.assertEqual(policy.decide("shell", args={"command": "rm -rf /"}).decision, PROMPT)

    def test_mcp_rule_matches_the_bridge_tool(self) -> None:
        policy = self._policy({"allow": ["mcp__enact__mcp_call"]})
        self.assertEqual(policy.decide("mcp_call").decision, ALLOW)


class CodexPolicyTest(unittest.TestCase):
    def _policy(self, rules: str) -> CodexPolicy:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / "test.rules"
        path.write_text(rules)
        config = Path(tmpdir.name) / "config.toml"
        config.write_text('approval_policy = "on-request"\nsandbox_mode = "workspace-write"\n')
        return CodexPolicy(rules_dir=Path(tmpdir.name), config_path=config)

    def test_prefix_rule_is_parsed(self) -> None:
        policy = self._policy('prefix_rule(pattern = ["git", "status"], decision = "allow")\n')
        self.assertEqual(len(policy.rules), 1)
        self.assertEqual(policy.rules[0]["pattern"], ["git", "status"])
        self.assertEqual(policy.rules[0]["decision"], "allow")

    def test_allowed_prefix(self) -> None:
        policy = self._policy('prefix_rule(pattern = ["git", "status"], decision = "allow")\n')
        decision = policy.decide("shell", args={"command": "git status --short"})
        self.assertEqual(decision.decision, ALLOW)

    def test_forbidden_prefix(self) -> None:
        policy = self._policy('prefix_rule(pattern = ["rm", "-rf"], decision = "forbidden")\n')
        decision = policy.decide("shell", args={"command": "rm -rf /tmp/x"})
        self.assertEqual(decision.decision, FORBIDDEN)

    def test_unmatched_command_prompts(self) -> None:
        policy = self._policy('prefix_rule(pattern = ["git", "status"], decision = "allow")\n')
        self.assertEqual(policy.decide("shell", args={"command": "curl example.com"}).decision, PROMPT)

    def test_longest_pattern_wins(self) -> None:
        policy = self._policy(
            'prefix_rule(pattern = ["git"], decision = "prompt")\n'
            'prefix_rule(pattern = ["git", "status"], decision = "allow")\n'
        )
        self.assertEqual(policy.decide("shell", args={"command": "git status"}).decision, ALLOW)

    def test_non_shell_tools_are_not_gated_by_execpolicy(self) -> None:
        policy = self._policy('prefix_rule(pattern = ["rm"], decision = "forbidden")\n')
        self.assertEqual(policy.decide("file_read").decision, ALLOW)

    def test_config_posture_is_reported(self) -> None:
        policy = self._policy("")
        self.assertEqual(policy.summary()["approval_policy"], "on-request")
        self.assertEqual(policy.summary()["sandbox_mode"], "workspace-write")


if __name__ == "__main__":
    unittest.main()
