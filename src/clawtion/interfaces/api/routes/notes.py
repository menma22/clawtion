"""Notes CRUD API endpoints for clawtion.

Provides full create / read / update / delete operations for notes managed
inside the vault, plus folder listing.
"""

from __future__ import annotations

import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from clawtion.interfaces.api.app import APIResponse
from clawtion.utils.exceptions import DocumentNotFoundError, ValidationError

logger = structlog.get_logger("clawtion.api.notes")

router = APIRouter(tags=["notes"])

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateNoteRequest(BaseModel):
    """Payload for creating a new note."""

    title: str = Field(..., min_length=1, max_length=500, description="Note title")
    content: str = Field(..., min_length=1, description="Note body (Markdown)")
    folder: str = Field(default="", description="Folder path within the vault (e.g. 'tech/rag')")
    tags: list[str] = Field(default_factory=list, description="Optional list of tags")


class UpdateNoteRequest(BaseModel):
    """Payload for updating an existing note's content."""

    content: str = Field(..., min_length=1, description="New note body (Markdown)")
    title: str | None = Field(default=None, min_length=1, max_length=500, description="Optional new title")
    folder: str | None = Field(default=None, description="Optional new folder path")
    tags: list[str] | None = Field(default=None, description="Optional new list of tags")


class NoteResponse(BaseModel):
    """A single note (document) as returned by the API."""

    document_id: str
    title: str
    content: str
    folder_path: str
    tags: list[str]
    file_path: str
    file_extension: str | None = None
    file_size_bytes: int | None = None
    total_chunks: int = 0
    last_indexed_at: str | None = None
    created_at: str
    updated_at: str


class NoteListItem(BaseModel):
    """Lightweight note representation used in list responses."""

    document_id: str
    title: str
    folder_path: str
    tags: list[str]
    file_path: str
    total_chunks: int = 0
    created_at: str
    updated_at: str


class FolderItem(BaseModel):
    """A folder within the vault."""

    folder_path: str
    note_count: int = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_note_service(request: Request) -> Any:
    """FastAPI dependency: return the note service from app state."""
    return request.app.state.note_service


def _serialize_note(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw note dict (from ORM / service) into the response format."""
    result: dict[str, Any] = {}
    for field in NoteResponse.model_fields:
        value = raw.get(field) or raw.get(field.replace("_", ""))
        if isinstance(value, datetime.datetime):
            result[field] = value.isoformat()
        elif isinstance(value, list):
            result[field] = list(value)
        else:
            result[field] = value
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/notes",
    response_model=APIResponse[NoteResponse],
    status_code=201,
    summary="Create a new note",
)
async def create_note(
    request: Request,
    body: CreateNoteRequest,
    note_service: Any = Depends(_get_note_service),
) -> dict[str, Any]:
    """Create a new Markdown note in the vault and queue it for indexing."""
    import time

    start = time.monotonic()

    note = await note_service.create(
        title=body.title,
        content=body.content,
        folder=body.folder,
        tags=body.tags,
    )

    if not note:
        raise ValidationError(message="Failed to create note")

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": _serialize_note(note),
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }


@router.get(
    "/notes/{document_id}",
    response_model=APIResponse[NoteResponse],
    summary="Get a single note by ID",
)
async def get_note(
    request: Request,
    document_id: str,
    note_service: Any = Depends(_get_note_service),
) -> dict[str, Any]:
    """Retrieve a single note including its full content."""
    import time

    start = time.monotonic()

    note = await note_service.get(document_id=document_id)

    if not note:
        raise DocumentNotFoundError(document_id=document_id)

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": _serialize_note(note),
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }


@router.put(
    "/notes/{document_id}",
    response_model=APIResponse[NoteResponse],
    summary="Update a note's content",
)
async def update_note(
    request: Request,
    document_id: str,
    body: UpdateNoteRequest,
    note_service: Any = Depends(_get_note_service),
) -> dict[str, Any]:
    """Update an existing note's content (and optionally title, folder, tags).

    The updated note will be re-queued for indexing.
    """
    import time

    start = time.monotonic()

    existing = await note_service.get(document_id=document_id)
    if not existing:
        raise DocumentNotFoundError(document_id=document_id)

    update_kwargs: dict[str, Any] = {"content": body.content}
    if body.title is not None:
        update_kwargs["title"] = body.title
    if body.folder is not None:
        update_kwargs["folder"] = body.folder
    if body.tags is not None:
        update_kwargs["tags"] = body.tags

    note = await note_service.update(document_id=document_id, **update_kwargs)

    if not note:
        raise DocumentNotFoundError(document_id=document_id)

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": _serialize_note(note),
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }


@router.delete(
    "/notes/{document_id}",
    status_code=200,
    summary="Delete a note",
)
async def delete_note(
    request: Request,
    document_id: str,
    permanent: bool = Query(default=False, description="If true, skip trash and delete permanently"),
    note_service: Any = Depends(_get_note_service),
) -> dict[str, Any]:
    """Delete a note.  By default the note is moved to trash; use ``permanent=true`` to bypass trash."""
    import time

    start = time.monotonic()

    existing = await note_service.get(document_id=document_id)
    if not existing:
        raise DocumentNotFoundError(document_id=document_id)

    await note_service.delete(document_id=document_id, permanent=permanent)

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": {"document_id": document_id, "deleted": True, "permanent": permanent},
        "meta": {"execution_time_ms": round(elapsed_ms, 2)},
    }


@router.get(
    "/notes",
    response_model=APIResponse[list[NoteListItem]],
    summary="List notes in the vault",
)
async def list_notes(
    request: Request,
    folder: str | None = Query(default=None, description="Filter by folder path"),
    limit: int = Query(default=50, ge=1, le=500, description="Max notes to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    note_service: Any = Depends(_get_note_service),
) -> dict[str, Any]:
    """List notes with optional folder filter and pagination."""
    import time

    start = time.monotonic()

    notes = await note_service.list_notes(
        folder=folder,
        limit=limit,
        offset=offset,
    )

    items = [_serialize_note(n) | {"content": ""} for n in notes]  # strip body in list view

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": items,
        "meta": {
            "folder": folder,
            "limit": limit,
            "offset": offset,
            "total": len(notes),
            "execution_time_ms": round(elapsed_ms, 2),
        },
    }


@router.get(
    "/folders",
    response_model=APIResponse[list[FolderItem]],
    summary="List folders in the vault",
)
async def list_folders(
    request: Request,
    note_service: Any = Depends(_get_note_service),
) -> dict[str, Any]:
    """Return all folders that contain notes in the vault."""
    import time

    start = time.monotonic()

    folders = await note_service.list_folders()

    elapsed_ms = (time.monotonic() - start) * 1000.0

    return {
        "data": folders,
        "meta": {
            "total_folders": len(folders),
            "execution_time_ms": round(elapsed_ms, 2),
        },
    }
