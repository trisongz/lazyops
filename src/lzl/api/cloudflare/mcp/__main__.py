"""
Entry point for running the Cloudflare MCP server as a module.

Usage:
    python -m lzl.api.cloudflare.mcp
"""

from .server import main

if __name__ == "__main__":
    main()
