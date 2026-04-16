#!/usr/bin/env python3
"""Entrypoint for the Lucid MCP server."""

import sys
from pathlib import Path

src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

if __name__ == '__main__':
    from lucid_mcp.server import main

    main()
