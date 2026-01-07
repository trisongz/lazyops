"""
Cloudflare MCP Server

An MCP (Model Context Protocol) server that exposes Cloudflare DNS management
functionality as tools for AI assistants.

Usage:
    uv run cloudflare-mcp

Or directly:
    python -m lzl.api.cloudflare.mcp
"""

from .server import serve, create_server, main

__all__ = ["serve", "create_server", "main"]
