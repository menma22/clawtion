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

from datetime import datetime
from typing import Any

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
        return obj.to_dict()  # type: ignore[no-any-return]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[no-any-return]
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
        granularity: str = "all",
        filter: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Perform semantic vector search.

        Args:
            query: Search query text.
            top_k: Maximum number of results (default 10).
            granularity: Chunk granularity: "file", "coarse", "fine", or "all" (default "all").
            filter: Optional JSON string with filter criteria.
            namespace: Optional namespace UUID to scope the search.

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
                namespace=namespace,
            )
            return _success_response(
                {
                    "query": query,
                    "granularity": granularity,
                    "namespace": namespace,
                    "count": len(results),
                    "results": [_format_search_result(r) for r in results],
                }
            )
        except Exception as exc:
            return _error_response("semantic_search", str(exc))

    @server.tool()
    async def keyword_search(
        query: str,
        top_k: int = 10,
        granularity: str = "all",
        filter: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Perform keyword full-text search.

        Args:
            query: Search query text.
            top_k: Maximum number of results (default 10).
            granularity: Chunk granularity: "file", "coarse", "fine", or "all" (default "all").
            filter: Optional JSON string with filter criteria.
            namespace: Optional namespace UUID to scope the search.

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
                namespace=namespace,
            )
            return _success_response(
                {
                    "query": query,
                    "granularity": granularity,
                    "namespace": namespace,
                    "count": len(results),
                    "results": [_format_search_result(r) for r in results],
                }
            )
        except Exception as exc:
            return _error_response("keyword_search", str(exc))

    @server.tool()
    async def hybrid_search(
        query: str,
        top_k: int = 10,
        semantic_weight: float = 0.5,
        granularity: str = "all",
        filter: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Perform hybrid search (semantic + keyword combined).

        Args:
            query: Search query text.
            top_k: Maximum number of results (default 10).
            semantic_weight: Weight for semantic score vs keyword (0.0-1.0, default 0.5).
            granularity: Chunk granularity: "file", "coarse", "fine", or "all" (default "all").
            filter: Optional JSON string with filter criteria.
            namespace: Optional namespace UUID to scope the search.

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
                namespace=namespace,
            )
            return _success_response(
                {
                    "query": query,
                    "granularity": granularity,
                    "semantic_weight": semantic_weight,
                    "namespace": namespace,
                    "count": len(results),
                    "results": [_format_search_result(r) for r in results],
                }
            )
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

            notes = await service.list_notes(
                folder=filter_dict.pop("folder", None),
                limit=100,
            )
            # Apply remaining filters manually
            tag_filter = filter_dict.pop("tags", None)
            extension_filter = filter_dict.pop("extension", None)
            if tag_filter:
                notes = [n for n in notes if any(t in n.get("tags", []) for t in tag_filter)]
            if extension_filter:
                notes = [n for n in notes if n.get("file_extension") == extension_filter]
            return _success_response(
                {
                    "count": len(notes),
                    "results": [_format_note(n) for n in notes],
                }
            )
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
            chunks = await service.get_file_chunks(document_id=document_id, level=level)
            return _success_response(
                {
                    "document_id": document_id,
                    "level": level,
                    "count": len(chunks),
                    "chunks": [_format_chunk(c) for c in chunks],
                }
            )
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
            return _success_response(
                {
                    "anchor_chunk_id": chunk_id,
                    "before": before,
                    "after": after,
                    "count": len(chunks),
                    "chunks": [_format_chunk(c) for c in chunks],
                }
            )
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
                return _success_response(
                    {
                        "chunk_id": chunk_id,
                        "parent": None,
                        "message": "No parent chunk found (already at top level).",
                    }
                )
            return _success_response(
                {
                    "chunk_id": chunk_id,
                    "parent": _format_chunk(parent),
                }
            )
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
            result = await service.create(
                title=title,
                content=content,
                folder=folder or "",
                tags=tag_list,
            )
            return _success_response(
                {
                    "document_id": result.get("document_id", ""),
                    "file_path": result.get("file_path", ""),
                    "title": title,
                }
            )
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
            note_data = await service.get(document_id)
            if not note_data:
                return _success_response(
                    {
                        "found": False,
                        "document_id": document_id,
                        "note": None,
                    }
                )
            return _success_response(
                {
                    "found": True,
                    "document_id": document_id,
                    "note": _format_note(note_data),
                }
            )
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
                return _success_response(
                    {
                        "success": True,
                        "message": "No changes requested.",
                    }
                )

            result = await service.update(document_id, **update_fields)
            return _success_response(
                {
                    "success": bool(result),
                    "document_id": document_id,
                }
            )
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
            success = await service.delete(document_id, permanent=permanent)
            return _success_response(
                {
                    "success": bool(success),
                    "in_trash": not permanent,
                    "document_id": document_id,
                    "permanent": permanent,
                }
            )
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
            return _success_response(
                {
                    "count": len(notes),
                    "limit": limit,
                    "offset": offset,
                    "folder": folder,
                    "notes": [_format_note(n) for n in notes],
                }
            )
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
            return _success_response(
                {
                    "count": len(folders),
                    "folders": folders,
                }
            )
        except Exception as exc:
            return _error_response("list_folders", str(exc))

    # ==================================================================
    # Namespace tools
    # ==================================================================

    @server.tool()
    async def create_namespace(
        name: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a new namespace for logical partitioning.

        Args:
            name: Unique name for the namespace (max 100 chars).
            description: Optional human-readable description.

        Returns:
            The created Namespace object with id, name, description, created_at.
        """
        from clawtion.interfaces.mcp.server import get_namespace_service

        try:
            service = await get_namespace_service()
            ns = await service.create(name=name, description=description)
            return _success_response(
                {
                    "namespace_id": ns.namespace_id,
                    "name": ns.name,
                    "description": ns.description,
                    "created_at": ns.created_at,
                }
            )
        except Exception as exc:
            return _error_response("create_namespace", str(exc))

    @server.tool()
    async def list_namespaces() -> dict[str, Any]:
        """List all namespaces in the vault.

        Returns:
            A list of Namespace objects with id, name, description, chunk_count.
        """
        from clawtion.interfaces.mcp.server import get_namespace_service

        try:
            service = await get_namespace_service()
            namespaces = await service.list_all()
            return _success_response(
                {
                    "count": len(namespaces),
                    "namespaces": [
                        {
                            "namespace_id": ns.namespace_id,
                            "name": ns.name,
                            "description": ns.description,
                            "created_at": ns.created_at,
                            "chunk_count": ns.chunk_count,
                        }
                        for ns in namespaces
                    ],
                }
            )
        except Exception as exc:
            return _error_response("list_namespaces", str(exc))

    @server.tool()
    async def assign_to_namespace(
        document_id: str,
        namespace_id: str,
    ) -> dict[str, Any]:
        """Assign all chunks of a document to a namespace.

        Args:
            document_id: The document UUID to assign.
            namespace_id: The target namespace UUID.

        Returns:
            Object with success status, document_id, namespace_id, and chunks_updated count.
        """
        from clawtion.interfaces.mcp.server import get_namespace_service

        try:
            service = await get_namespace_service()
            chunks_updated = await service.assign_document(
                document_id=document_id,
                namespace_id=namespace_id,
            )
            return _success_response(
                {
                    "success": True,
                    "document_id": document_id,
                    "namespace_id": namespace_id,
                    "chunks_updated": chunks_updated,
                }
            )
        except Exception as exc:
            return _error_response("assign_to_namespace", str(exc))

    # ==================================================================
    # GraphRAG tools
    # ==================================================================

    @server.tool()
    async def graph_search(
        starting_entity: str,
        max_hops: int = 2,
        relation_types: str | None = None,
    ) -> dict[str, Any]:
        """Traverse the entity-relation graph from a starting entity.

        Uses a recursive SQL CTE to discover entities and their relations
        up to *max_hops* depth from the starting entity.  Results include
        a full entity list, a relation list, and an adjacency structure.

        Args:
            starting_entity: Entity name or UUID to start traversal from.
            max_hops: Maximum number of relation hops (default 2, max 10).
            relation_types: Optional comma-separated list of relation types
                to restrict traversal (e.g. ``"uses,mentions"``).

        Returns:
            A graph result with entities, relations, and adjacency data.
        """
        return await _graph_search_impl(
            starting_entity=starting_entity,
            max_hops=min(max_hops, 10),
            relation_types=relation_types,
        )

    @server.tool()
    async def get_related_chunks(
        chunk_id: str,
        max_hops: int = 1,
    ) -> dict[str, Any]:
        """Find chunks related to a given chunk via shared entities.

        Traces the entity graph from entities mentioned in the specified
        chunk, then discovers other chunks that reference the same entities.

        Args:
            chunk_id: The anchor chunk UUID.
            max_hops: Entity graph traversal depth (default 1, max 5).

        Returns:
            A list of related chunks with entity context.
        """
        return await _get_related_chunks_impl(
            chunk_id=chunk_id,
            max_hops=min(max_hops, 5),
        )

    @server.tool()
    async def extract_entities_from_chunk(
        chunk_id: str,
        store: bool = False,
    ) -> dict[str, Any]:
        """Extract entities from a document chunk using heuristic matching.

        Uses regex patterns and a known-entity dictionary to identify
        persons, organizations, technologies, and concepts in the chunk
        text.  Optionally stores extracted entities and co-occurrence
        relations in the graph database.

        Args:
            chunk_id: The chunk UUID to analyse.
            store: If True, store extracted entities and relations in
                the graph database (default False).

        Returns:
            Extracted entity list or stored entity/relation counts.
        """
        return await _extract_entities_from_chunk_impl(
            chunk_id=chunk_id,
            store=store,
        )

    # ==================================================================
    # Note editing tools
    # ==================================================================

    @server.tool()
    async def update_note_section(
        document_id: str,
        target_heading: str,
        new_content: str,
        match_context: str | None = None,
    ) -> dict[str, Any]:
        """Update a specific section of a note identified by a heading.

        Locates the heading in the note file, replaces all content between
        that heading and the next heading of equal or higher level, and
        triggers re-indexing.

        Args:
            document_id: The document UUID of the note to edit.
            target_heading: The heading text to target (without ``#``
                prefix).  Matching is case-insensitive.
            new_content: The new Markdown content for the section.
            match_context: Optional text that must appear in the section
                content to disambiguate when multiple headings match.

        Returns:
            Update result with section boundary info.
        """
        return await _update_note_section_mcp(
            document_id=document_id,
            target_heading=target_heading,
            new_content=new_content,
            match_context=match_context,
        )

    @server.tool()
    async def append_to_note(
        document_id: str,
        content: str,
        position: str = "end",
        target_heading: str | None = None,
    ) -> dict[str, Any]:
        """Append content to a note at the end or relative to a heading.

        Args:
            document_id: The document UUID of the note to edit.
            content: The Markdown content to append.
            position: Where to insert. One of:
                - ``"end"``: at the end of the file (default)
                - ``"after_heading"``: immediately after the target heading's section
                - ``"before_heading"``: immediately before the target heading
            target_heading: Required when *position* is not ``"end"``.
                The heading text to anchor the insertion.

        Returns:
            Append result with insertion line info.
        """
        return await _append_to_note_mcp(
            document_id=document_id,
            content=content,
            position=position,
            target_heading=target_heading,
        )


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
            "folder_path": result.get("folder_path", ""),
            "document_id": result.get("document_id", ""),
            "title": result.get("title", ""),
            "chunk_id": result.get("chunk_id"),
            "chunk_level": result.get("chunk_level", "file"),
            "chunk_index": result.get("chunk_index"),
            "chunk_total": result.get("chunk_total"),
            "heading_path": result.get("heading_path", ""),
            "content": result.get("content", "")[:500],
            "content_preview": result.get("content", "")[:200],
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


# ---------------------------------------------------------------------------
# GraphRAG tools
# ---------------------------------------------------------------------------


async def _graph_search_impl(
    starting_entity: str,
    max_hops: int = 2,
    relation_types: str | None = None,
) -> dict[str, Any]:
    """Implementation of graph_search — traverses entity-relation graph."""
    from clawtion.interfaces.mcp.server import get_graph_service

    try:
        service = await get_graph_service()
        rt_list = None
        if relation_types:
            rt_list = [t.strip() for t in relation_types.split(",")]
        result = await service.graph_search(
            starting_entity=starting_entity,
            max_hops=max_hops,
            relation_types=rt_list,
        )
        return _success_response(result)
    except Exception as exc:
        return _error_response("graph_search", str(exc))


async def _get_related_chunks_impl(
    chunk_id: str,
    max_hops: int = 1,
) -> dict[str, Any]:
    """Implementation of get_related_chunks — find related chunks via entity graph."""
    from clawtion.interfaces.mcp.server import get_graph_service

    try:
        service = await get_graph_service()
        related = await service.find_related(
            chunk_id=chunk_id,
            max_hops=max_hops,
        )
        return _success_response(
            {
                "chunk_id": chunk_id,
                "max_hops": max_hops,
                "count": len(related),
                "related_chunks": related,
            }
        )
    except Exception as exc:
        return _error_response("get_related_chunks", str(exc))


async def _extract_entities_from_chunk_impl(
    chunk_id: str,
    store: bool = False,
) -> dict[str, Any]:
    """Extract entities from a document chunk. Optionally store in the graph."""
    from clawtion.interfaces.mcp.server import get_graph_service

    try:
        service = await get_graph_service()
        if store:
            result = await service.extract_and_store(chunk_id)
            return _success_response(result)
        entities = await service.extract_entities(chunk_id)
        return _success_response(
            {
                "chunk_id": chunk_id,
                "count": len(entities),
                "entities": entities,
            }
        )
    except Exception as exc:
        return _error_response("extract_entities_from_chunk", str(exc))


# ---------------------------------------------------------------------------
# Note editing tools
# ---------------------------------------------------------------------------


async def _update_note_section_mcp(
    document_id: str,
    target_heading: str,
    new_content: str,
    match_context: str | None = None,
) -> dict[str, Any]:
    """Update a specific section of a note identified by heading."""
    from clawtion.interfaces.mcp.server import get_note_editor, get_note_service

    try:
        # Resolve document_id to file_path
        note_service = await get_note_service()
        note_data = await note_service.get(document_id)
        if not note_data:
            return _success_response(
                {
                    "found": False,
                    "document_id": document_id,
                    "note": None,
                }
            )
        file_path = note_data["file_path"]

        editor = await get_note_editor()
        result = editor.update_section(
            file_path=file_path,
            target_heading=target_heading,
            new_content=new_content,
            match_context=match_context,
        )
        # Re-read the updated file content and trigger re-indexing
        try:
            import os

            abs_path = os.path.join(editor._vault_path, file_path)
            with open(abs_path, encoding="utf-8") as f:
                updated_content = f.read()
            await note_service.update(document_id, content=updated_content)
        except Exception:
            pass

        return _success_response(
            {
                "document_id": document_id,
                "file_path": file_path,
                "target_heading": target_heading,
                "section_update": result,
            }
        )
    except Exception as exc:
        return _error_response("update_note_section", str(exc))


async def _append_to_note_mcp(
    document_id: str,
    content: str,
    position: str = "end",
    target_heading: str | None = None,
) -> dict[str, Any]:
    """Append content to a note at the end or after/before a specific heading."""
    from clawtion.interfaces.mcp.server import get_note_editor, get_note_service

    try:
        note_service = await get_note_service()
        note_data = await note_service.get(document_id)
        if not note_data:
            return _success_response(
                {
                    "found": False,
                    "document_id": document_id,
                    "note": None,
                }
            )
        file_path = note_data["file_path"]

        editor = await get_note_editor()
        result = editor.append_content(
            file_path=file_path,
            content=content,
            position=position,
            target_heading=target_heading,
        )
        # Re-read the updated file content and trigger re-indexing
        try:
            import os

            abs_path = os.path.join(editor._vault_path, file_path)
            with open(abs_path, encoding="utf-8") as f:
                updated_content = f.read()
            await note_service.update(document_id, content=updated_content)
        except Exception:
            pass

        return _success_response(
            {
                "document_id": document_id,
                "file_path": file_path,
                "position": position,
                "target_heading": target_heading,
                "append_result": result,
            }
        )
    except Exception as exc:
        return _error_response("append_to_note", str(exc))
