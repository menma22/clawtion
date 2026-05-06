"""Queue management API endpoints for clawtion.

Provides visibility into the indexing queue (pending, failed, in-progress
jobs) as well as administrative actions to retry or clear failed items.
"""

from __future__ import annotations

import time as _time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from clawtion.interfaces.api.app import APIResponse

logger = structlog.get_logger("clawtion.api.queue")

router = APIRouter(tags=["queue"])

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class QueueStats(BaseModel):
    """Aggregate queue statistics."""

    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    cancelled: int


class QueueItem(BaseModel):
    """A single entry in the indexing queue."""

    queue_id: str
    document_id: str
    file_path: str
    operation: str
    status: str
    priority: int
    retry_count: int
    max_retries: int
    last_error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class SystemMetrics(BaseModel):
    """System-level metrics exposed via the /metrics endpoint."""

    total_documents: int
    total_chunks: int
    indexing_queue_pending: int
    indexing_queue_failed: int
    total_queue_items: int
    db_size_mb: float | None = None
    vault_path: str
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_queue_manager(request: Request) -> Any:
    """FastAPI dependency: return the QueueManager from app state."""
    return request.app.state.queue_manager


def _get_note_service(request: Request) -> Any:
    """FastAPI dependency: return the note service from app state."""
    return request.app.state.note_service


def _get_db(request: Request) -> Any:
    """FastAPI dependency: return the DatabaseManager from app state."""
    return request.app.state.db


def _serialize_queue_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw queue item dict into the API format."""
    result: dict[str, Any] = {}
    for field in QueueItem.model_fields:
        value = raw.get(field)
        if hasattr(value, "isoformat"):
            result[field] = value.isoformat()
        else:
            result[field] = value
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/queue/status",
    response_model=APIResponse[QueueStats],
    summary="Get indexing queue status",
)
async def queue_status(
    request: Request,
    queue_manager: Any = Depends(_get_queue_manager),
) -> dict[str, Any]:
    """Return aggregate statistics about the indexing queue."""
    start = _time.monotonic()

    stats = await queue_manager.get_stats()

    elapsed_ms = (_time.monotonic() - start) * 1000.0

    return {
        "data": QueueStats(
            total=stats.get("total", 0),
            pending=stats.get("pending", 0),
            processing=stats.get("processing", 0),
            completed=stats.get("completed", 0),
            failed=stats.get("failed", 0),
            cancelled=stats.get("cancelled", 0),
        ),
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }


@router.get(
    "/queue/pending",
    response_model=APIResponse[list[QueueItem]],
    summary="List pending queue items",
)
async def list_pending(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    queue_manager: Any = Depends(_get_queue_manager),
) -> dict[str, Any]:
    """Return pending jobs in the indexing queue."""
    start = _time.monotonic()

    items = await queue_manager.get_pending(limit=limit, offset=offset)

    elapsed_ms = (_time.monotonic() - start) * 1000.0

    return {
        "data": [_serialize_queue_item(i) for i in items],
        "meta": {
            "limit": limit,
            "offset": offset,
            "total": len(items),
            "execution_time_ms": round(elapsed_ms, 2),
        },
    }


@router.get(
    "/queue/failed",
    response_model=APIResponse[list[QueueItem]],
    summary="List failed queue items",
)
async def list_failed(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    queue_manager: Any = Depends(_get_queue_manager),
) -> dict[str, Any]:
    """Return failed jobs in the indexing queue."""
    start = _time.monotonic()

    items = await queue_manager.get_failed(limit=limit, offset=offset)

    elapsed_ms = (_time.monotonic() - start) * 1000.0

    return {
        "data": [_serialize_queue_item(i) for i in items],
        "meta": {
            "limit": limit,
            "offset": offset,
            "total": len(items),
            "execution_time_ms": round(elapsed_ms, 2),
        },
    }


@router.post(
    "/queue/process",
    response_model=APIResponse[dict[str, Any]],
    summary="Process pending queue items",
)
async def process_queue(
    request: Request,
    queue_manager: Any = Depends(_get_queue_manager),
) -> dict[str, Any]:
    """Trigger processing of the indexing queue.

    The actual processing runs in the background; this endpoint returns
    immediately after enqueueing the processing request.
    """
    start = _time.monotonic()

    result = await queue_manager.process_queue()

    elapsed_ms = (_time.monotonic() - start) * 1000.0

    return {
        "data": {
            "triggered": True,
            "processed": result.get("processed", 0),
            "failed": result.get("failed", 0),
            "skipped": result.get("skipped", 0),
        },
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }


@router.post(
    "/queue/retry/{queue_id}",
    response_model=APIResponse[QueueItem],
    summary="Retry a single failed queue item",
)
async def retry_queue_item(
    request: Request,
    queue_id: str,
    queue_manager: Any = Depends(_get_queue_manager),
) -> dict[str, Any]:
    """Reset a failed queue item to 'pending' so it is retried."""
    start = _time.monotonic()

    item = await queue_manager.retry(queue_id=queue_id)

    elapsed_ms = (_time.monotonic() - start) * 1000.0

    return {
        "data": _serialize_queue_item(item) if item else None,
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }


@router.post(
    "/queue/clear-failed",
    response_model=APIResponse[dict[str, Any]],
    summary="Clear all failed queue items",
)
async def clear_failed(
    request: Request,
    queue_manager: Any = Depends(_get_queue_manager),
) -> dict[str, Any]:
    """Remove all failed items from the indexing queue."""
    start = _time.monotonic()

    removed = await queue_manager.clear_failed()

    elapsed_ms = (_time.monotonic() - start) * 1000.0

    return {
        "data": {"removed": removed},
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }


@router.get(
    "/metrics",
    response_model=APIResponse[SystemMetrics],
    summary="System-wide metrics",
)
async def metrics(
    request: Request,
    queue_manager: Any = Depends(_get_queue_manager),
    note_service: Any = Depends(_get_note_service),
    db: Any = Depends(_get_db),
) -> dict[str, Any]:
    """Return aggregate system metrics for monitoring."""
    start = _time.monotonic()

    stats = await queue_manager.get_stats()

    # Count total documents directly (list_notes with limit=0 returns nothing)
    doc_count = await db.execute(
        "SELECT COUNT(*) as cnt FROM documents WHERE is_deleted = false", {},
    )
    total_docs = doc_count[0]["cnt"] if doc_count else 0

    # Count total chunks
    chunk_count = await db.execute(
        "SELECT COUNT(*) as cnt FROM document_chunks", {},
    )
    total_chunks = chunk_count[0]["cnt"] if chunk_count else 0

    elapsed_ms = (_time.monotonic() - start) * 1000.0

    return {
        "data": SystemMetrics(
            total_documents=total_docs,
            total_chunks=total_chunks,
            indexing_queue_pending=stats.get("pending", 0),
            indexing_queue_failed=stats.get("failed", 0),
            total_queue_items=stats.get("total", 0),
            db_size_mb=None,
            vault_path=request.app.state.vault_path,
        ),
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }
