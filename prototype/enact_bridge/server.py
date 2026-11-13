"""MCP stdio server exposing the canonical registry to any MCP host.

Transport: newline-delimited JSON-RPC 2.0 on stdin/stdout (the MCP stdio
transport). Protocol version: 2024-11-05, which both Codex CLI and Claude
Code speak; the server echoes the client's requested version when it is one
it knows, so newer clients stay on their own dialect.

Default surface: two tools.

    mcp_search   find canonical tools by intent
    mcp_call     run one canonical tool

`--expose full` advertises every canonical tool with its real schema instead.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, TextIO

from . import SERVER_NAME, __version__, aliases
from .discovery import detail, search
from .executor import Executor
from .model import Registry
from .policy import FORBIDDEN, ClaudeCodePolicy, CodexPolicy

PROTOCOL_VERSION = "2024-11-05"
KNOWN_PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")

SEARCH_TOOL = "mcp_search"
CALL_TOOL = "mcp_call"

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "What you want to do, in plain language (e.g. 'search files by content').",
        },
        "tool": {
            "type": "string",
            "description": "Exact canonical tool name. When given, the full schema is returned.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 32,
            "description": "Maximum number of tool references to return.",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}

CALL_SCHEMA = {
    "type": "object",
    "properties": {
        "tool": {
            "type": "string",
            "description": "Canonical tool name, as returned by mcp_search.",
        },
        "action": {
            "type": "string",
            "description": "Operation to perform, when the tool has more than one.",
        },
        "arguments": {
            "type": "object",
            "description": "Arguments for the operation.",
            "default": {},
        },
    },
    "required": ["tool"],
    "additionalProperties": False,
}

INSTRUCTIONS = (
    "One canonical registry of enact-agent's tools, shared by Codex CLI and Claude Code. "
    f"{SEARCH_TOOL} finds a tool by intent; {CALL_TOOL} runs it. "
    "Sibling tools are consolidated: one canonical tool with a typed `action` enum, "
    "and every original operation is preserved."
)


def _tool_descriptor(name: str, description: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "description": description, "inputSchema": schema}


class BridgeServer:
    """The MCP server. Transport-agnostic so it can be driven from tests."""

    def __init__(
        self,
        registry: Registry,
        workspace: str | os.PathLike | None = None,
        expose: str = "minimal",
        policy: Any = None,
    ) -> None:
        self.registry = registry
        self.executor = Executor(registry, workspace)
        self.expose = expose
        self.host: str | None = None
        self.policy = policy
        self.client_info: dict[str, Any] = {}

    # -------------------------------------------------------------- lifecycle
    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC message. Returns None for notifications."""
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}

        if method is None:
            return self._error(msg_id, -32600, "invalid request: missing method")

        try:
            if method == "initialize":
                result = self._initialize(params)
            elif method in ("notifications/initialized", "initialized"):
                return None
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": self._list_tools()}
            elif method == "tools/call":
                result = self._call_tool(params)
            elif method == "prompts/list":
                result = {"prompts": []}
            elif method == "resources/list":
                result = {"resources": []}
            elif method == "resources/templates/list":
                result = {"resourceTemplates": []}
            elif method == "logging/setLevel":
                result = {}
            else:
                return self._error(msg_id, -32601, f"method not found: {method}")
        except Exception as exc:  # pragma: no cover - defensive
            return self._error(msg_id, -32603, f"internal error: {type(exc).__name__}: {exc}")

        if msg_id is None:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion") or PROTOCOL_VERSION
        version = requested if requested in KNOWN_PROTOCOLS else PROTOCOL_VERSION
        self.client_info = params.get("clientInfo") or {}
        self.host = self._detect_host(self.client_info)
        if self.host and self.policy is None:
            self.policy = self._load_policy(self.host)
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
            "instructions": INSTRUCTIONS,
        }

    @staticmethod
    def _detect_host(client_info: dict[str, Any]) -> str | None:
        name = str(client_info.get("name") or "").lower()
        if not name:
            return None
        if "claude" in name:
            return aliases.CLAUDE_CODE
        if "codex" in name:
            return aliases.CODEX
        return None

    @staticmethod
    def _load_policy(host: str):
        try:
            if host == aliases.CLAUDE_CODE:
                return ClaudeCodePolicy()
            if host == aliases.CODEX:
                return CodexPolicy()
        except Exception:  # pragma: no cover - policy must never break the server
            return None
        return None

    # ------------------------------------------------------------------ tools
    def _list_tools(self) -> list[dict[str, Any]]:
        listed = [
            _tool_descriptor(
                SEARCH_TOOL,
                "Find a canonical tool by intent. Returns the tool name, its actions and a summary.",
                SEARCH_SCHEMA,
            ),
            _tool_descriptor(
                CALL_TOOL,
                "Call a canonical tool. Use the name and action returned by mcp_search.",
                CALL_SCHEMA,
            ),
        ]
        if self.expose != "full":
            return listed
        for tool in self.registry.enabled_tools():
            listed.append(_tool_descriptor(tool.name, tool.description, tool.parameters))
        return listed

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            return self._tool_error("tool call is missing 'name'")
        if not isinstance(arguments, dict):
            return self._tool_error("tool call 'arguments' must be an object")

        if name == SEARCH_TOOL:
            return self._do_search(arguments)
        if name == CALL_TOOL:
            return self._do_call(arguments)
        return self._call_canonical(name, None, arguments)

    def _do_search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query") or "")
        limit = int(arguments.get("limit") or 8)
        exact = arguments.get("tool")
        if exact:
            info = detail(self.registry, str(exact))
            if not info:
                return self._tool_error(f"unknown canonical tool {exact!r}")
            return self._tool_text(json.dumps(info, indent=1))
        result = search(self.registry, query, limit=limit)
        return self._tool_text(json.dumps(result, indent=1))

    def _do_call(self, arguments: dict[str, Any]) -> dict[str, Any]:
        tool_name = arguments.get("tool")
        if not tool_name:
            return self._tool_error("mcp_call requires a 'tool'")
        action = arguments.get("action")
        call_args = arguments.get("arguments") or {}
        if not isinstance(call_args, dict):
            return self._tool_error("mcp_call 'arguments' must be an object")
        return self._call_canonical(str(tool_name), action, call_args)

    def _call_canonical(self, tool_name: str, action: str | None, args: dict[str, Any]) -> dict[str, Any]:
        canonical = aliases.resolve(self.host, tool_name) if self.host else None
        canonical = canonical or tool_name

        tool = self.registry.get(canonical)
        if tool is None:
            return self._tool_error(
                f"unknown canonical tool {canonical!r}. Use {SEARCH_TOOL} to find the right name."
            )
        if tool.disabled:
            return self._tool_error(
                f"tool {canonical!r} is compiled out of the Enact build and is not exposed"
            )

        # The host's own policy decides whether this call may happen.
        decision = self._policy_decision(canonical, action, args)
        if decision is not None and decision.decision == FORBIDDEN:
            return self._tool_error(
                f"blocked by {decision.source}: {decision.reason} (tool {canonical!r})"
            )

        # Resolve the action here so an unknown action is a clean tool error
        # rather than an internal fault, and so the source trace is exact.
        try:
            resolved_action = tool.resolve_action(action)
        except KeyError as exc:
            return self._tool_error(str(exc))

        result = self.executor.execute(canonical, resolved_action, args)
        text = result.content
        if len(tool.merged_from) > 1:
            source_tool, source_op = tool.source_of(resolved_action)
            text = f"{text}\n\n[source: {source_tool}.{source_op}]"
        if not result.ok:
            text = f"{text}\n\n[error: {result.error}]"
        return {
            "content": [{"type": "text", "text": text}],
            "isError": not result.ok,
        }

    def _policy_decision(self, canonical: str, action: str | None, args: dict[str, Any]):
        if self.policy is None:
            return None
        try:
            return self.policy.decide(canonical, action, args)
        except Exception:  # pragma: no cover - policy must never break a call
            return None

    @staticmethod
    def _tool_text(text: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": text}], "isError": False}

    @staticmethod
    def _tool_error(message: str) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": message}], "isError": True}

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


# ------------------------------------------------------------------ transport
def serve_stdio(
    registry: Registry,
    workspace: str | os.PathLike | None = None,
    expose: str = "minimal",
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Serve MCP over stdio until the input stream closes."""
    server = BridgeServer(registry, workspace=workspace, expose=expose)
    src = stdin or sys.stdin
    dst = stdout or sys.stdout

    for line in src:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            dst.write(json.dumps(BridgeServer._error(None, -32700, "parse error")) + "\n")
            dst.flush()
            continue
        response = server.handle(message)
        if response is not None:
            dst.write(json.dumps(response) + "\n")
            dst.flush()
