"""Execution is real for the core tools and sandboxed to the workspace."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from enact_bridge.executor import Executor
from enact_bridge.model import Registry


class ExecutorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = Registry.from_path()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.executor = Executor(self.registry, self.root)

    def test_write_then_read(self) -> None:
        write = self.executor.execute("file_write", None, {"path": "a/b.txt", "content": "hello\nworld"})
        self.assertTrue(write.ok, write.content)
        read = self.executor.execute("file_read", None, {"path": "a/b.txt"})
        self.assertTrue(read.ok)
        self.assertIn("hello", read.content)
        self.assertIn("1\thello", read.content)

    def test_edit_replaces_exact_text(self) -> None:
        self.executor.execute("file_write", None, {"path": "c.txt", "content": "alpha beta"})
        edit = self.executor.execute(
            "file_edit", None, {"path": "c.txt", "old_string": "beta", "new_string": "gamma"}
        )
        self.assertTrue(edit.ok, edit.content)
        self.assertIn("gamma", self.executor.execute("file_read", None, {"path": "c.txt"}).content)

    def test_edit_without_match_fails(self) -> None:
        self.executor.execute("file_write", None, {"path": "d.txt", "content": "alpha"})
        edit = self.executor.execute(
            "file_edit", None, {"path": "d.txt", "old_string": "zzz", "new_string": "y"}
        )
        self.assertFalse(edit.ok)
        self.assertEqual(edit.error, "no_match")

    def test_glob_and_content_search(self) -> None:
        self.executor.execute("file_write", None, {"path": "x.py", "content": "import os\n"})
        self.executor.execute("file_write", None, {"path": "y.txt", "content": "nothing here"})
        glob = self.executor.execute("glob_search", None, {"pattern": "*.py"})
        self.assertTrue(glob.ok)
        self.assertIn("x.py", glob.content)
        search = self.executor.execute("content_search", None, {"pattern": "import"})
        self.assertTrue(search.ok)
        self.assertIn("x.py", search.content)

    def test_shell_runs_in_the_workspace(self) -> None:
        result = self.executor.execute("shell", None, {"command": "pwd"})
        self.assertTrue(result.ok, result.content)
        self.assertIn(str(self.root), result.content)

    def test_shell_reports_a_non_zero_exit(self) -> None:
        result = self.executor.execute("shell", None, {"command": "exit 3"})
        self.assertFalse(result.ok)
        self.assertEqual(result.data["exit_code"], 3)

    def test_path_escape_is_refused(self) -> None:
        result = self.executor.execute("file_read", None, {"path": "../../etc/passwd"})
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sandbox_violation")

    def test_absolute_path_escape_is_refused(self) -> None:
        result = self.executor.execute("file_read", None, {"path": "/etc/passwd"})
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sandbox_violation")

    def test_calculator(self) -> None:
        result = self.executor.execute("calculator", None, {"expression": "2 * (3 + 4)"})
        self.assertTrue(result.ok)
        self.assertEqual(result.content, "14")

    def test_calculator_rejects_code(self) -> None:
        result = self.executor.execute("calculator", None, {"expression": "__import__('os')"})
        self.assertFalse(result.ok)

    def test_unimplemented_tool_names_its_source_operation(self) -> None:
        result = self.executor.execute("web_fetch", None, {"url": "https://example.com"})
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "not_implemented")
        self.assertIn("web_fetch", result.content)

    def test_family_action_maps_back_to_the_source_operation(self) -> None:
        result = self.executor.execute("cron", "schedule_add", {})
        self.assertFalse(result.ok)
        self.assertEqual(result.data["source_tool"], "schedule")
        self.assertEqual(result.data["source_operation"], "add")

    def test_git_read_only_slice(self) -> None:
        ok = self.executor.execute("git_operations", "status", {})
        refused = self.executor.execute("git_operations", "commit", {"message": "x"})
        self.assertFalse(refused.ok)
        self.assertEqual(refused.error, "not_implemented")


if __name__ == "__main__":
    unittest.main()
