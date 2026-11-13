"""The canonical registry data model.

The registry is loaded from `data/registry.generated.json`, which is produced
by `tools/generate_registry.py` straight out of enact-agent's real tool
inventory. Nothing here is hand-authored.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Iterable

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REGISTRY_PATH = os.path.join(os.path.dirname(_HERE), "data", "registry.generated.json")


@dataclass(frozen=True)
class Operation:
    """One operation of one canonical tool, traced back to its source."""

    action: str
    tool: str
    operation: str
    disabled: bool = False

    @property
    def source(self) -> str:
        return f"{self.tool}.{self.operation}"


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    operations: list[str]
    op_map: dict[str, dict[str, Any]]
    merged_from: list[str]
    tier: str
    compilation: str
    disabled: bool
    destructive: bool
    source_files: list[str]

    # ------------------------------------------------------------------ views
    @property
    def actions(self) -> list[str]:
        """The canonical action names of this tool."""
        return list(self.operations)

    @property
    def op_list(self) -> list[Operation]:
        return [
            Operation(
                action=action,
                tool=meta.get("tool", self.name),
                operation=meta.get("operation", action),
                disabled=bool(meta.get("disabled", False)),
            )
            for action, meta in self.op_map.items()
        ]

    def resolve_action(self, action: str | None) -> str:
        """Map a requested action onto a canonical action name.

        A tool with exactly one operation does not require an action; any
        other spelling of the operation name is accepted.
        """
        if action:
            if action in self.op_map:
                return action
            raise KeyError(
                f"unknown action {action!r} for tool {self.name!r}; "
                f"expected one of: {', '.join(self.operations)}"
            )
        if len(self.operations) == 1:
            return self.operations[0]
        raise KeyError(
            f"tool {self.name!r} requires an action; expected one of: "
            f"{', '.join(self.operations)}"
        )

    def source_of(self, action: str) -> tuple[str, str]:
        meta = self.op_map[action]
        return meta.get("tool", self.name), meta.get("operation", action)

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "actions": self.actions,
            "tier": self.tier,
            "compilation": self.compilation,
            "destructive": self.destructive,
            "disabled": self.disabled,
            "merged_from": self.merged_from,
        }


@dataclass
class Registry:
    tools: list[Tool]
    meta: dict[str, Any] = field(default_factory=dict)
    _index: dict[str, Tool] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._index = {t.name: t for t in self.tools}

    # ---------------------------------------------------------------- loading
    @classmethod
    def from_path(cls, path: str | None = None) -> "Registry":
        path = path or DEFAULT_REGISTRY_PATH
        with open(path) as fh:
            raw = json.load(fh)
        tools = [
            Tool(
                name=t["name"],
                description=t["description"],
                parameters=t["parameters"],
                operations=t["operations"],
                op_map=t["op_map"],
                merged_from=t["merged_from"],
                tier=t["tier"],
                compilation=t["compilation"],
                disabled=t["disabled"],
                destructive=t["destructive"],
                source_files=t.get("source_files", []),
            )
            for t in raw["tools"]
        ]
        meta = {k: v for k, v in raw.items() if k != "tools"}
        return cls(tools=tools, meta=meta)

    # ----------------------------------------------------------------- views
    def __len__(self) -> int:
        return len(self.tools)

    def __iter__(self) -> Iterable[Tool]:
        return iter(self.tools)

    def get(self, name: str) -> Tool | None:
        return self._index.get(name)

    def enabled_tools(self) -> list[Tool]:
        return [t for t in self.tools if not t.disabled]

    @property
    def operation_count(self) -> int:
        return sum(len(t.operations) for t in self.tools)

    @property
    def enabled_operation_count(self) -> int:
        return sum(len(t.operations) for t in self.tools if not t.disabled)

    def stats(self) -> dict[str, Any]:
        by_tier: dict[str, int] = {}
        for t in self.tools:
            by_tier[t.tier] = by_tier.get(t.tier, 0) + 1
        return {
            "canonical_tools": len(self.tools),
            "enabled_tools": len(self.enabled_tools()),
            "operations": self.operation_count,
            "enabled_operations": self.enabled_operation_count,
            "source_tools": self.meta.get("source_tool_count"),
            "tiers": by_tier,
        }
