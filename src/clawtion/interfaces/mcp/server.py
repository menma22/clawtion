"""MCP server for clawtion -- provides tools for AI agents (Claude Code).

The server runs over stdio and registers all tools defined in the
``tools`` module. It uses the ``mcp`` Python SDK to communicate
with the MCP protocol.

Usage::

    clawtion mcp-serve

"""

from __future__ import annotations

import os
from typing import Any

from clawtion.config.loader import get_config
from clawtion.config.secrets import get_secret

# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

_db_instance: Any = None
_embedder_instance: Any = None
_config_instance: dict[str, Any] | None = None


def get_config_cached() -> dict[str, Any]:
    """Return cached config, reloading once per session."""
    global _config_instance
    if _config_instance is None:
        _config_instance = get_config()
    return _config_instance


async def get_db() -> Any:
    """Return a singleton DatabaseManager, connecting on first access."""
    global _db_instance
    if _db_instance is None:
        from clawtion.core.db.connection import DatabaseManager

        get_config_cached()
        db_url = os.environ.get(
            "CLAWTION_DB_URL",
            "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion",
        )
        _db_instance = DatabaseManager(db_url)
        await _db_instance.connect()
    return _db_instance


async def get_embedder() -> Any:
    """Return a singleton EmbeddingClient."""
    global _embedder_instance
    if _embedder_instance is None:
        from clawtion.core.embedding.gemini import GeminiEmbeddingClient

        cfg = get_config_cached()
        api_key = get_secret("gemini_api_key") or ""
        _embedder_instance = GeminiEmbeddingClient(
            api_key=api_key,
            output_dimensionality=cfg.get("embedding", {}).get("output_dimensionality", 768),
            use_manual_prefix=cfg.get("embedding", {}).get("use_manual_prefix_fallback", True),
        )
    return _embedder_instance


async def get_search_service() -> Any:
    """Return a singleton SearchService."""
    from clawtion.core.search.service import SearchService

    db = await get_db()
    embedder = await get_embedder()
    return SearchService(db=db, embedder=embedder)


async def get_namespace_service() -> Any:
    """Return a singleton NamespaceService."""
    from clawtion.core.namespace.service import NamespaceService

    db = await get_db()
    return NamespaceService(db=db)


async def get_note_service() -> Any:
    """Return a singleton NoteService."""
    from clawtion.core.indexing.queue import QueueManager
    from clawtion.core.indexing.service import IndexingService
    from clawtion.core.note.service import NoteService

    cfg = get_config_cached()
    db = await get_db()
    embedder = await get_embedder()
    vault_path = os.path.expandvars(os.path.expanduser(cfg.get("vault", {}).get("path", "~/Documents/clawtion-vault")))

    queue = QueueManager(db)
    indexing_service = IndexingService(
        db=db,
        embedder=embedder,
        queue=queue,
        vault_path=vault_path,
        config=cfg,
    )
    return NoteService(db=db, vault_path=vault_path, indexing_service=indexing_service)


async def get_graph_service() -> Any:
    """Return a singleton GraphService."""
    from clawtion.core.graph.service import GraphService

    db = await get_db()
    embedder = await get_embedder()
    return GraphService(db=db, embedder=embedder)


async def get_note_editor() -> Any:
    """Return a singleton NoteEditor."""
    from clawtion.core.note.editor import NoteEditor

    cfg = get_config_cached()
    vault_path = os.path.expandvars(os.path.expanduser(cfg.get("vault", {}).get("path", "~/Documents/clawtion-vault")))
    return NoteEditor(vault_path=vault_path)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------


def create_mcp_server() -> Any:
    """Create and configure the MCP server with all tools registered.

    Returns:
        An ``mcp.Server`` instance with all tools registered.
    """
    from mcp.server import Server

    server = Server("clawtion")

    # Register all tools
    from clawtion.interfaces.mcp.tools import register_all_tools

    register_all_tools(server)

    return server


async def run_mcp_server() -> None:
    """Run the MCP server over stdio.

    This is the main entry point called by the CLI ``mcp-serve`` command.
    """
    from mcp.server.stdio import stdio_server

    server = create_mcp_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
