#!/usr/bin/env python
"""Run the MCP server without installing the package.

Point an MCP client at this file:
    {"command": "python", "args": ["<repo>/scripts/run_server.py"]}
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from vre.server import main  # noqa: E402

if __name__ == "__main__":
    main()
