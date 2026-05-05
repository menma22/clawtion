"""clawtion MCP server interface package.

Provides a Model Context Protocol (MCP) server for AI agent integration.
The server exposes search, note, and file chunk access tools over stdio.

Usage::

    clawtion mcp-serve
"""

from clawtion.interfaces.mcp.server import create_mcp_server, run_mcp_server

__all__ = [
    "create_mcp_server",
    "run_mcp_server",
]
