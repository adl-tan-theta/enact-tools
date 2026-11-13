"""The canonical registry must be a lossless consolidation of the real inventory."""
from __future__ import annotations

import csv
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

from enact_bridge.model import Registry
from tools.merge_map import MERGE_FAMILIES

PROTOTYPE = Path(__file__).resolve().parent.parent
INVENTORY = PROTOTYPE.parent / "zeroclaw-tools-operations.csv"
sys.path.insert(0, str(PROTOTYPE.parent))
from enact_paths import overlay_csv_optional  # noqa: E402

OVERLAY = overlay_csv_optional()


class RegistryIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = Registry.from_path()
        with open(INVENTORY, newline="") as fh:
            cls.rows = list(csv.DictReader(fh))

    def test_counts_match_the_real_inventory(self) -> None:
        """The counts are derived, never written down.

        A hardcoded count is a number that goes stale the moment a tool is
        added; these assertions read the inventory and the merge map instead.
        """
        stats = self.registry.stats()
        source_tools = len({r["tool_name"] for r in self.rows})
        source_operations = len({(r["tool_name"], r["operation"]) for r in self.rows})
        collapsed = sum(len(family) - 1 for family in MERGE_FAMILIES.values())
        self.assertEqual(stats["source_tools"], source_tools)
        self.assertEqual(stats["operations"], source_operations)
        self.assertEqual(stats["canonical_tools"], source_tools - collapsed)

    def test_every_source_operation_is_reachable_exactly_once(self) -> None:
        source = {(r["tool_name"], r["operation"]) for r in self.rows}
        reachable = [(op.tool, op.operation) for tool in self.registry for op in tool.op_list]
        self.assertEqual(len(reachable), len(set(reachable)), "an operation was duplicated")
        self.assertEqual(source, set(reachable), "an operation was lost or invented")

    def test_action_names_are_unique_inside_a_canonical_tool(self) -> None:
        for tool in self.registry:
            self.assertEqual(
                len(tool.operations), len(set(tool.operations)), f"{tool.name} has duplicate actions"
            )

    def test_families_keep_all_their_members(self) -> None:
        merged = {t.name: t for t in self.registry if len(t.merged_from) > 1}
        self.assertGreaterEqual(len(merged), 10)
        for tool in merged.values():
            for member in tool.merged_from:
                self.assertIn(member, tool.merged_from)
                # every member's operations are reachable through some action
                actions = {a for a in tool.op_map}
                self.assertTrue(actions)

    def test_compiled_out_tools_are_flagged(self) -> None:
        disabled = sorted(t.name for t in self.registry if t.disabled)
        self.assertEqual(len(disabled), 13)
        self.assertIn("notion", disabled)
        self.assertIn("codex_cli", disabled)
        self.assertNotIn("shell", disabled)

    def test_overlay_flags_are_the_source_of_truth(self) -> None:
        if OVERLAY is None or not OVERLAY.exists():
            self.skipTest("enact-agent overlay not present")
        with open(OVERLAY, newline="") as fh:
            rows = list(csv.DictReader(fh))
        expected = {r["tool_name"].lstrip("#") for r in rows if r["compiled_in_enact"].strip() != "true"}
        actual = {t.name for t in self.registry if t.disabled}
        self.assertEqual(expected, actual)

    def test_the_inventory_trap_column_is_not_used(self) -> None:
        """`compiled_in_enact_all_tools` is TRUE everywhere in the workspace CSV."""
        with open(INVENTORY, newline="") as fh:
            rows = list(csv.DictReader(fh))
        values = {r["compiled_in_enact_all_tools"] for r in rows}
        self.assertEqual(values, {"TRUE"})
        self.assertGreater(len({r["tool_name"] for r in rows}), 0)

    def test_schemas_declare_a_typed_action_enum(self) -> None:
        for tool in self.registry:
            props = tool.parameters.get("properties", {})
            if len(tool.operations) > 1:
                self.assertIn("action", props, f"{tool.name} has no action enum")
                self.assertEqual(sorted(props["action"]["enum"]), sorted(tool.operations))
                self.assertIn("action", tool.parameters.get("required", []))

    def test_tiers_are_known(self) -> None:
        for tool in self.registry:
            self.assertIn(tool.tier, {"Core", "Host", "Optional"})


class MergeMapTest(unittest.TestCase):
    def test_no_operation_is_dropped_by_the_merge(self) -> None:
        sys.path.insert(0, str(PROTOTYPE / "tools"))
        from merge_map import MERGE_FAMILIES  # noqa: PLC0415

        with open(INVENTORY, newline="") as fh:
            rows = list(csv.DictReader(fh))
        by_tool = {}
        for row in rows:
            by_tool.setdefault(row["tool_name"], []).append(row["operation"])
        for family, members in MERGE_FAMILIES.items():
            total = sum(len(by_tool.get(m, [])) for m in members)
            self.assertGreater(total, 0, family)

    def test_family_action_names_do_not_collide(self) -> None:
        registry = Registry.from_path()
        counter: Counter = Counter()
        for tool in registry:
            for action in tool.operations:
                counter[(tool.name, action)] += 1
        self.assertTrue(all(v == 1 for v in counter.values()))


if __name__ == "__main__":
    unittest.main()
