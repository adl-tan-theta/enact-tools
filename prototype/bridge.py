#!/usr/bin/env python3
"""Command line entry point for the enact-bridge.

    python3 bridge.py show
    python3 bridge.py search "read a file"
    python3 bridge.py call file_read --args '{"path": "README.md"}'
    python3 bridge.py install --host both --scope project
    python3 bridge.py verify

The MCP server itself is launched through `serve.py`, which is what the host
adapters point a host at.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from enact_bridge.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
