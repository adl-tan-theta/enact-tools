"""enact_bridge — one canonical tool registry, two hosts.

The bridge exposes enact-agent's 109 tool names (244 operations) as a single
canonical registry of 83 tools over MCP, and hands that same registry to both
Codex CLI and Claude Code.

Layout:
    model.py      the registry data model
    aliases.py    host vocabularies -> canonical names
    policy.py     reads each host's own policy and mirrors its decisions
    discovery.py  search over the registry (lazy tool surface)
    executor.py   real execution for the core tools, sandboxed to a workspace
    server.py     MCP stdio server (JSON-RPC 2.0)
    adapters.py   installers for Claude Code and Codex
    cli.py        command line entry point
"""
from __future__ import annotations

__all__ = ["__version__", "SERVER_NAME"]

__version__ = "0.1.0"
SERVER_NAME = "enact-bridge"
