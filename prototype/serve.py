#!/usr/bin/env python3
"""Launcher for the enact-bridge MCP server.

Hosts spawn this over stdio:

    python3 /abs/path/to/prototype/serve.py --workspace /abs/path/to/project

Environment:
    ENACT_BRIDGE_WORKSPACE   default workspace root for file and shell tools
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from enact_bridge.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["serve", *sys.argv[1:]]))
