"""Search API endpoints for clawtion.

Provides semantic, keyword, and hybrid search over the knowledge base,
along with chunk-level navigation (get chunks by document, neighbours, parent).
"""

from __future__ import annotations

import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from clawtion.interfaces.api.app import APIResponse
from clawtion.utils.exceptions import DocumentNotFoundError, ValidationError

logger = structlog.get_logger("clawtion.api.search")

router = APIRouter(tags=["search"])

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """Payload for search endpoints."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query text")
    granularity: str = Field(
        default="file",
        pattern=r"^(all|file|coarse|fine)$",
        description="Chunk granularity level to search across",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    metadata_filter: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata filter dict (e.g. folder, tags, extension)",
    )


class SearchResultItem(BaseModel):
    """A single search result entry."""

    document_id: str
    chunk_id: str | None = None
    file_path: str
    title: str | None = None
    folder_path: str | None = None
    content: str
    content_with_context: str | None = None
    score: float
    chunk_level: str | None = None
    chunk_index: int | None = None
    heading_path: str | None = None


class SearchMeta(BaseModel):
    """Metadata attached to every search response."""

    query: str
    total_results: int
    granularity: str
    search_type: str
    execution_time_ms: float
    cached: bool = False


class ChunkItem(BaseModel):
    """A single chunk entry returned by navigation endpoints."""

    chunk_id: str
    document_id: str
    chunk_level: str
    chunk_index: int
    chunk_total: int
    parent_chunk_id: str | None = None
    heading_path: str | None = None
    content: str
    content_with_context: str | None = None
    token_count: int | None = None
    char_count: int | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_search_service(request: Request) -> Any:
    """FastAPI dependency: return the search service from app state."""
    return request.app.state.search_service


async def _timed_search(
    search_type: str,
    query: str,
    granularity: str,
    top_k: int,
    metadata_filter: dict[str, Any] | None,
    search_service: Any,
) -> tuple[list[dict[str, Any]], SearchMeta]:
    """Execute a search with timing, returning (results, meta)."""
    import time

    start = time.monotonic()

    method_map = {
        "semantic": search_service.semantic_search,
        "keyword": search_service.keyword_search,
        "hybrid": search_service.hybrid_search,
    }

    method = method_map.get(search_type)
    if method is None:
        raise ValidationError(message=f"Unknown search type: {search_type}")

    results: list[dict[str, Any]] = await method(
        query=query,
        granularity=granularity,
        top_k=top_k,
        metadata_filter=metadata_filter,
    )

    elapsed_ms = (time.monotonic() - start) * 1000.0

    meta = SearchMeta(
        query=query,
        total_results=len(results),
        granularity=granularity,
        search_type=search_type,
        execution_time_ms=round(elapsed_ms, 2),
    )

    return results, meta


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/search/semantic",
    response_model=APIResponse[list[SearchResultItem]],
    summary="Semantic (vector) search",
)
async def semantic_search(
    request: Request,
    body: SearchRequest,
    search_service: Any = Depends(_get_search_service),
) -> dict[str, Any]:
    """Search the knowledge base using vector similarity (semantic search)."""
    results, meta = await _timed_search(
        "semantic",
        body.query,
        body.granularity,
        body.top_k,
        body.metadata_filter,
        search_service,
    )
    return {"data": [SearchResultItem(**r) for r in results], "meta": meta.model_dump()}


@router.post(
    "/search/keyword",
    response_model=APIResponse[list[SearchResultItem]],
    summary="Keyword (full-text) search",
)
async def keyword_search(
    request: Request,
    body: SearchRequest,
    search_service: Any = Depends(_get_search_service),
) -> dict[str, Any]:
    """Search the knowledge base using full-text keyword matching."""
    results, meta = await _timed_search(
        "keyword",
        body.query,
        body.granularity,
        body.top_k,
        body.metadata_filter,
        search_service,
    )
    return {"data": [SearchResultItem(**r) for r in results], "meta": meta.model_dump()}


@router.post(
    "/search/hybrid",
    response_model=APIResponse[list[SearchResultItem]],
    summary="Hybrid (vector + keyword) search",
)
async def hybrid_search(
    request: Request,
    body: SearchRequest,
    search_service: Any = Depends(_get_search_service),
) -> dict[str, Any]:
    """Search the knowledge base combining vector similarity and keyword matching."""
    results, meta = await _timed_search(
        "hybrid",
        body.query,
        body.granularity,
        body.top_k,
        body.metadata_filter,
        search_service,
    )
    return {"data": [SearchResultItem(**r) for r in results], "meta": meta.model_dump()}


@router.get(
    "/chunks/{document_id}/all",
    response_model=APIResponse[list[ChunkItem]],
    summary="Get all chunks for a document",
)
async def get_file_chunks(
    request: Request,
    document_id: str,
    level: str = Query(default="file", pattern=r"^(file|coarse|fine)$"),
    search_service: Any = Depends(_get_search_service),
) -> dict[str, Any]:
    """Retrieve all chunks belonging to a document at the specified granularity level."""
    import time

    start = time.monotonic()

    chunks = await search_service.get_file_chunks(
        document_id=document_id,
        level=level,
    )

    if chunks is None:
        raise DocumentNotFoundError(document_id=document_id)

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": [ChunkItem(**c) for c in chunks],
        "meta": {
            "document_id": document_id,
            "level": level,
            "total_chunks": len(chunks),
            "execution_time_ms": round(elapsed_ms, 2),
        },
    }


@router.get(
    "/chunks/{chunk_id}/neighbors",
    response_model=APIResponse[list[ChunkItem]],
    summary="Get neighbouring chunks around a chunk",
)
async def get_neighbor_chunks(
    request: Request,
    chunk_id: str,
    before: int = Query(default=1, ge=0, le=10, description="Chunks before"),
    after: int = Query(default=1, ge=0, le=10, description="Chunks after"),
    search_service: Any = Depends(_get_search_service),
) -> dict[str, Any]:
    """Return chunks that appear before and after the given chunk in its document."""
    import time

    start = time.monotonic()

    chunks = await search_service.get_neighbor_chunks(
        chunk_id=chunk_id,
        before=before,
        after=after,
    )

    if chunks is None:
        raise DocumentNotFoundError(document_id=chunk_id)

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": [ChunkItem(**c) for c in chunks],
        "meta": {
            "center_chunk_id": chunk_id,
            "before": before,
            "after": after,
            "total_chunks": len(chunks),
            "execution_time_ms": round(elapsed_ms, 2),
        },
    }


@router.get(
    "/chunks/{chunk_id}/parent",
    response_model=APIResponse[ChunkItem | None],
    summary="Get the parent chunk of a given chunk",
)
async def get_parent_chunk(
    request: Request,
    chunk_id: str,
    search_service: Any = Depends(_get_search_service),
) -> dict[str, Any]:
    """Return the parent chunk for a hierarchical chunk (multi-resolution)."""
    import time

    start = time.monotonic()

    parent = await search_service.get_parent_chunk(chunk_id=chunk_id)

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": ChunkItem(**parent) if parent else None,
        "meta": {
            "chunk_id": chunk_id,
            "has_parent": parent is not None,
            "execution_time_ms": round(elapsed_ms, 2),
        },
    }
