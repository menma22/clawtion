"""CLI entry points for running the clawtion API and MCP servers.

These functions are called from the Click CLI commands
(``clawtion api-serve``, ``clawtion mcp-serve``) defined in
``clawtion.interfaces.cli.main``.
"""

from __future__ import annotations

import sys

import structlog

logger = structlog.get_logger("clawtion.api")


def run_api_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the FastAPI REST API server.

    Args:
        host: Bind address (default 127.0.0.1).
        port: Bind port (default 8080).
    """
    import uvicorn

    logger.info("starting_api_server", host=host, port=port)

    uvicorn.run(
        "clawtion.interfaces.api.app:create_app",
        host=host,
        port=port,
        factory=True,
        log_level="info",
        reload=False,
        lifespan="on",
    )


def run_mcp_server() -> None:
    """Run the clawtion MCP server over stdio.

    The MCP server communicates via stdin/stdout using the Model Context
    Protocol, enabling Claude Code to call clawtion tools directly.

    This function loads the MCP server implementation from
    ``clawtion.interfaces.mcp.server``.  If that module is not yet available
    (e.g. during parallel development), a clear error message is shown.
    """
    logger.info("starting_mcp_server")

    try:
        from clawtion.interfaces.mcp.server import create_mcp_server
    except ImportError as exc:
        logger.error("mcp_server_module_not_found", error=str(exc))
        print(
            "Error: The MCP server module is not yet available.\n"
            "       Expected location: clawtion.interfaces.mcp.server\n"
            "       Ensure the module is implemented and installed.",
            file=sys.stderr,
        )
        sys.exit(1)

    server = create_mcp_server()
    logger.info("mcp_server_running")

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("mcp_server_stopped")
    except Exception as exc:
        logger.error("mcp_server_error", error=str(exc))
        sys.exit(1)
