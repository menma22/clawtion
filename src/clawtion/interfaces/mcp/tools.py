"""MCP tool implementations for clawtion.

All tools are async functions that:
1. Accept typed parameters matching the TypeScript interface in the design doc
2. Instantiate the appropriate service via ``server.py`` singletons
3. Call the service method
4. Return structured results (serializable to JSON)
5. Handle errors gracefully (return error info, do not crash)

Tools are registered with the MCP server via ``register_all_tools(server)``.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from clawtion.i18n.translator import t

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error_response(tool: str, message: str) -> dict[str, Any]:
    """Return a structured error dictionary for MCP tool results."""
    return {
        "success": False,
        "error": {
            "tool": tool,
            "message": message,
        },
    }


def _success_response(data: Any) -> dict[str, Any]:
    """Wrap a successful result."""
    return {"success": True, "data": data}


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert an object to a dict, preferring ``to_dict()`` if available."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return dict(obj)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_all_tools(server: Any) -> None:
    """Register all MCP tools with the MCP server.

    Args:
        server: An ``mcp.Server`` instance.
    """

    # ==================================================================
    # Search tools
    # ==================================================================

    @server.tool()
    async def semantic_search(
        query: str,
        top_k: int = 10,
        granularity: str = "file",
        filter: str | None = None,
    ) -> dict[str, Any]:
        """Perform semantic vector search.

        Args:
            query: Search query text.
            top_k: Maximum number of results (default 10).
            granularity: Result granularity: "file" or "chunk" (default "file").
            filter: Optional JSON string with filter criteria.

        Returns:
            SearchResult with matches, scores, and file paths.
        """
        from clawtion.interfaces.mcp.server import get_search_service

        try:
            service = await get_search_service()
            filter_dict = _parse_filter(filter)
            results = await service.semantic_search(
                query=query,
                top_k=top_k,
                granularity=granularity,
                filter=filter_dict,
            )
            return _success_response({
                "query": query,
                "granularity": granularity,
                "count": len(results),
                "results": [_format_search_result(r) for r in results],
            })
        except Exception as exc:
            return _error_response("semantic_search", str(exc))

    @server.tool()
    async def keyword_search(
        query: str,
        top_k: int = 10,
        granularity: str = "file",
        filter: str | None = None,
    ) -> dict[str, Any]:
        """Perform keyword full-text search.

        Args:
            query: Search query text.
            top_k: Maximum number of results (default 10).
            granularity: Result granularity: "file" or "chunk" (default "file").
            filter: Optional JSON string with filter criteria.

        Returns:
            SearchResult with matches, scores, and file paths.
        """
        from clawtion.interfaces.mcp.server import get_search_service

        try:
            service = await get_search_service()
            filter_dict = _parse_filter(filter)
            results = await service.keyword_search(
                query=query,
                top_k=top_k,
                granularity=granularity,
                filter=filter_dict,
            )
            return _success_response({
                "query": query,
                "granularity": granularity,
                "count": len(results),
                "results": [_format_search_result(r) for r in results],
            })
        except Exception as exc:
            return _error_response("keyword_search", str(exc))

    @server.tool()
    async def hybrid_search(
        query: str,
        top_k: int = 10,
        semantic_weight: float = 0.5,
        granularity: str = "file",
        filter: str | None = None,
    ) -> dict[str, Any]:
        """Perform hybrid search (semantic + keyword combined).

        Args:
            query: Search query text.
            top_k: Maximum number of results (default 10).
            semantic_weight: Weight for semantic score vs keyword (0.0-1.0, default 0.5).
            granularity: Result granularity: "file" or "chunk" (default "file").
            filter: Optional JSON string with filter criteria.

        Returns:
            SearchResult with combined scores, matches, and file paths.
        """
        from clawtion.interfaces.mcp.server import get_search_service

        try:
            service = await get_search_service()
            filter_dict = _parse_filter(filter)
            results = await service.hybrid_search(
                query=query,
                top_k=top_k,
                semantic_weight=semantic_weight,
                granularity=granularity,
                filter=filter_dict,
            )
            return _success_response({
                "query": query,
                "granularity": granularity,
                "semantic_weight": semantic_weight,
                "count": len(results),
                "results": [_format_search_result(r) for r in results],
            })
        except Exception as exc:
            return _error_response("hybrid_search", str(exc))

    @server.tool()
    async def metadata_filter(
        folder: str | None = None,
        tags: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        extension: str | None = None,
    ) -> dict[str, Any]:
        """Filter notes and documents by metadata criteria.

        Args:
            folder: Filter by folder path (e.g. "tech/projects").
            tags: Comma-separated tag filter.
            date_from: Filter documents modified after this date (ISO 8601).
            date_to: Filter documents modified before this date (ISO 8601).
            extension: Filter by file extension (e.g. ".md", ".py").

        Returns:
            NoteList with all matching documents.
        """
        from clawtion.interfaces.mcp.server import get_search_service

        try:
            service = await get_search_service()
            filter_dict: dict[str, Any] = {}
            if folder:
                filter_dict["folder"] = folder
            if tags:
                filter_dict["tags"] = [t.strip() for t in tags.split(",")]
            if date_from:
                filter_dict["date_from"] = date_from
            if date_to:
                filter_dict["date_to"] = date_to
            if extension:
                filter_dict["extension"] = extension

            results = await service.metadata_filter(**filter_dict)
            return _success_response({
                "count": len(results),
                "results": [_format_metadata_result(r) for r in results],
            })
        except Exception as exc:
            return _error_response("metadata_filter", str(exc))

    # ==================================================================
    # File / chunk access tools
    # ==================================================================

    @server.tool()
    async def get_file_chunks(
        document_id: str,
        level: str = "file",
    ) -> dict[str, Any]:
        """Retrieve chunks for a given document.

        Args:
            document_id: The ID of the document to retrieve chunks for.
            level: Chunk level: "file", "coarse", or "fine" (default "file").

        Returns:
            ChunkList with chunk texts, positions, and metadata.
        """
        from clawtion.interfaces.mcp.server import get_search_service

        try:
            service = await get_search_service()
            chunks = await service.get_chunks(document_id=document_id, level=level)
            return _success_response({
                "document_id": document_id,
                "level": level,
                "count": len(chunks),
                "chunks": [_format_chunk(c) for c in chunks],
            })
        except Exception as exc:
            return _error_response("get_file_chunks", str(exc))

    @server.tool()
    async def get_neighbor_chunks(
        chunk_id: str,
        before: int = 1,
        after: int = 1,
    ) -> dict[str, Any]:
        """Retrieve neighboring chunks for context around a specific chunk.

        Args:
            chunk_id: The ID of the anchor chunk.
            before: Number of chunks to include before (default 1).
            after: Number of chunks to include after (default 1).

        Returns:
            ChunkList with the anchor chunk, neighbors, and positional info.
        """
        from clawtion.interfaces.mcp.server import get_search_service

        try:
            service = await get_search_service()
            chunks = await service.get_neighbor_chunks(
                chunk_id=chunk_id,
                before=before,
                after=after,
            )
            return _success_response({
                "anchor_chunk_id": chunk_id,
                "before": before,
                "after": after,
                "count": len(chunks),
                "chunks": [_format_chunk(c) for c in chunks],
            })
        except Exception as exc:
            return _error_response("get_neighbor_chunks", str(exc))

    @server.tool()
    async def get_parent_chunk(chunk_id: str) -> dict[str, Any]:
        """Retrieve the parent chunk of a given chunk (coarse -> file, fine -> coarse).

        Args:
            chunk_id: The ID of the child chunk.

        Returns:
            The parent Chunk object, or an error if no parent exists.
        """
        from clawtion.interfaces.mcp.server import get_search_service

        try:
            service = await get_search_service()
            parent = await service.get_parent_chunk(chunk_id=chunk_id)
            if parent is None:
                return _success_response({
                    "chunk_id": chunk_id,
                    "parent": None,
                    "message": "No parent chunk found (already at top level).",
                })
            return _success_response({
                "chunk_id": chunk_id,
                "parent": _format_chunk(parent),
            })
        except Exception as exc:
            return _error_response("get_parent_chunk", str(exc))

    # ==================================================================
    # Note CRUD tools
    # ==================================================================

    @server.tool()
    async def add_note(
        title: str,
        content: str = "",
        folder: str | None = None,
        tags: str | None = None,
    ) -> dict[str, Any]:
        """Create a new note in the vault.

        Args:
            title: Note title (becomes filename).
            content: Note body content (Markdown).
            folder: Optional folder path within vault.
            tags: Comma-separated tags.

        Returns:
            Object with document_id and file_path of the created note.
        """
        from clawtion.interfaces.mcp.server import get_note_service

        try:
            service = await get_note_service()
            tag_list: list[str] = [t.strip() for t in tags.split(",")] if tags else []
            result = await service.create_note(
                title=title,
                content=content,
                folder=folder or "",
                tags=tag_list,
            )
            return _success_response({
                "document_id": result.get("document_id", ""),
                "file_path": result.get("file_path", ""),
                "title": title,
            })
        except Exception as exc:
            return _error_response("add_note", str(exc))

    @server.tool()
    async def get_note(document_id: str) -> dict[str, Any]:
        """Retrieve a note by its document ID.

        Args:
            document_id: The document ID of the note.

        Returns:
            Full Note object with title, content, metadata, and tags.
        """
        from clawtion.interfaces.mcp.server import get_note_service

        try:
            service = await get_note_service()
            note_data = await service.get_note(document_id)
            if not note_data:
                return _success_response({
                    "found": False,
                    "document_id": document_id,
                    "note": None,
                })
            return _success_response({
                "found": True,
                "document_id": document_id,
                "note": _format_note(note_data),
            })
        except Exception as exc:
            return _error_response("get_note", str(exc))

    @server.tool()
    async def update_note(
        document_id: str,
        content: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing note's content and/or title.

        Args:
            document_id: The document ID of the note to update.
            content: New note content (Markdown). Omit to leave unchanged.
            title: New note title. Omit to leave unchanged.

        Returns:
            Object indicating success.
        """
        from clawtion.interfaces.mcp.server import get_note_service

        try:
            service = await get_note_service()
            update_fields: dict[str, Any] = {}
            if content is not None:
                update_fields["content"] = content
            if title is not None:
                update_fields["title"] = title

            if not update_fields:
                return _success_response({
                    "success": True,
                    "message": "No changes requested.",
                })

            success = await service.update_note(document_id, **update_fields)
            return _success_response({
                "success": success,
                "document_id": document_id,
            })
        except Exception as exc:
            return _error_response("update_note", str(exc))

    @server.tool()
    async def delete_note(
        document_id: str,
        permanent: bool = False,
    ) -> dict[str, Any]:
        """Delete a note. By default moves to trash.

        Args:
            document_id: The document ID of the note to delete.
            permanent: If True, permanently delete instead of trashing (default False).

        Returns:
            Object with success status and trash info.
        """
        from clawtion.interfaces.mcp.server import get_note_service

        try:
            service = await get_note_service()
            success = await service.delete_note(document_id, permanent=permanent)
            return _success_response({
                "success": success,
                "in_trash": not permanent,
                "document_id": document_id,
                "permanent": permanent,
            })
        except Exception as exc:
            return _error_response("delete_note", str(exc))

    @server.tool()
    async def list_notes(
        folder: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List notes, optionally filtered by folder.

        Args:
            folder: Filter by folder path. If omitted, lists all notes.
            limit: Maximum number of notes to return (default 50).
            offset: Pagination offset (default 0).

        Returns:
            NoteList with matching notes.
        """
        from clawtion.interfaces.mcp.server import get_note_service

        try:
            service = await get_note_service()
            notes = await service.list_notes(folder=folder, limit=limit, offset=offset)
            return _success_response({
                "count": len(notes),
                "limit": limit,
                "offset": offset,
                "folder": folder,
                "notes": [_format_note(n) for n in notes],
            })
        except Exception as exc:
            return _error_response("list_notes", str(exc))

    @server.tool()
    async def list_folders() -> dict[str, Any]:
        """List all folder paths in the vault.

        Returns:
            A list of folder path strings.
        """
        from clawtion.interfaces.mcp.server import get_note_service

        try:
            service = await get_note_service()
            folders = await service.list_folders()
            return _success_response({
                "count": len(folders),
                "folders": folders,
            })
        except Exception as exc:
            return _error_response("list_folders", str(exc))


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _parse_filter(filter_str: str | None) -> dict[str, Any] | None:
    """Parse an optional JSON filter string into a dict."""
    if not filter_str:
        return None
    import json
    try:
        return dict(json.loads(filter_str))
    except (json.JSONDecodeError, TypeError):
        return None


def _format_search_result(result: Any) -> dict[str, Any]:
    """Convert a search result object to a plain dict."""
    if isinstance(result, dict):
        return {
            "score": result.get("score", 0.0),
            "file_path": result.get("file_path", ""),
            "document_id": result.get("document_id", ""),
            "heading": result.get("heading", ""),
            "snippet": result.get("snippet", "") or result.get("content_preview", ""),
            "content_preview": result.get("content_preview", ""),
            "chunk_id": result.get("chunk_id"),
            "level": result.get("level", "file"),
        }
    try:
        return _to_dict(result)
    except Exception:
        return {"raw": str(result)}


def _format_chunk(chunk: Any) -> dict[str, Any]:
    """Convert a chunk object to a plain dict."""
    if isinstance(chunk, dict):
        return {
            "chunk_id": chunk.get("chunk_id", chunk.get("id", "")),
            "document_id": chunk.get("document_id", ""),
            "level": chunk.get("level", "file"),
            "position": chunk.get("position", 0),
            "content": chunk.get("content", chunk.get("text", "")),
            "heading_path": chunk.get("heading_path", ""),
            "token_count": chunk.get("token_count", 0),
            "embedding": None,  # Not sent in responses for brevity
        }
    try:
        d = _to_dict(chunk)
        d.pop("embedding", None)
        return d
    except Exception:
        return {"raw": str(chunk)}


def _format_note(note: Any) -> dict[str, Any]:
    """Convert a note object to a plain dict."""
    if isinstance(note, dict):
        return {
            "document_id": note.get("document_id", note.get("id", "")),
            "title": note.get("title", ""),
            "content": note.get("content", ""),
            "file_path": note.get("file_path", ""),
            "folder": note.get("folder", ""),
            "tags": note.get("tags", []),
            "created_at": _fmt_date(note.get("created_at") or note.get("created")),
            "updated_at": _fmt_date(note.get("updated_at") or note.get("updated")),
            "file_size": note.get("file_size", 0),
        }
    try:
        return _to_dict(note)
    except Exception:
        return {"raw": str(note)}


def _format_metadata_result(result: Any) -> dict[str, Any]:
    """Convert a metadata filter result to a plain dict."""
    if isinstance(result, dict):
        return {
            "document_id": result.get("document_id", result.get("id", "")),
            "title": result.get("title", ""),
            "file_path": result.get("file_path", ""),
            "folder": result.get("folder", ""),
            "tags": result.get("tags", []),
            "extension": result.get("extension", ""),
            "file_size": result.get("file_size", 0),
            "updated_at": _fmt_date(result.get("updated_at")),
        }
    try:
        return _to_dict(result)
    except Exception:
        return {"raw": str(result)}


def _fmt_date(dt: Any) -> str:
    """Format a datetime value as ISO 8601 string, or return empty string."""
    if not dt:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    if isinstance(dt, str):
        return dt
    return str(dt)
