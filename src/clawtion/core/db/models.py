"""SQLAlchemy ORM models for the clawtion database.

Defines all database tables using async-compatible SQLAlchemy 2.0 patterns.
Uses DeclarativeBase for model definitions and PGVector for embeddings.
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003 — SQLAlchemy ORM evaluates annotations at runtime
from typing import Any

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Declarative base for all ORM models in the clawtion database."""


class Document(Base):
    """A document ingested into the knowledge base.

    Each row represents a single file tracked by clawtion.  Documents can be
    chunked at multiple granularities (file-level, coarse, fine) and their
    chunks stored in the ``document_chunks`` table.  Soft-delete is supported
    via the ``is_deleted`` / ``deleted_at`` columns.
    """

    __tablename__ = "documents"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    file_path: Mapped[str] = mapped_column(
        Text, unique=True, nullable=False, index=True,
    )
    folder_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_extension: Mapped[str | None] = mapped_column(String(10), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tags: Mapped[list[Any]] = mapped_column(
        JSON, default=list, nullable=False,
        server_default=text("'[]'::json"),
    )
    wikilinks: Mapped[list[Any]] = mapped_column(
        JSON, default=list, nullable=False,
        server_default=text("'[]'::json"),
    )
    # Database column name is "metadata"; Python attribute avoids shadowing Base.metadata.
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False,
        server_default=text("'{}'::json"),
    )
    total_chunks: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0",
    )
    has_file_level: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false"),
    )
    has_coarse_level: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false"),
    )
    has_fine_level: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false"),
    )
    last_indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("false"),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # -- Relationships -------------------------------------------------------
    chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    queue_items: Mapped[list[IndexingQueue]] = relationship(
        "IndexingQueue",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Document id={self.document_id} path={self.file_path!r}>"


class DocumentChunk(Base):
    """A single chunk of text extracted from a document at a specific level.

    Chunks can reference each other via ``parent_chunk_id`` to form a
    hierarchical tree (e.g. fine → coarse → file-level).  The ``embedding``
    column stores the vector produced by the embedding model.
    """

    __tablename__ = "document_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_level: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_total: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.chunk_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_with_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    embedding: Mapped[Any] = mapped_column(Vector(None), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Database column name is "metadata"; Python attribute avoids shadowing Base.metadata.
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False,
        server_default=text("'{}'::json"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -- Relationships -------------------------------------------------------
    document: Mapped[Document] = relationship(
        "Document", back_populates="chunks",
    )
    parent_chunk: Mapped[DocumentChunk | None] = relationship(
        "DocumentChunk",
        back_populates="child_chunks",
        remote_side="DocumentChunk.chunk_id",
    )
    child_chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk",
        back_populates="parent_chunk",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk id={self.chunk_id} doc={self.document_id} "
            f"level={self.chunk_level!r} index={self.chunk_index}>"
        )


class IndexingQueue(Base):
    """A job in the indexing pipeline.

    Each row tracks the lifecycle of a single indexing operation (index,
    re-index, delete) against a document.  The ``status`` column drives the
    worker loop; failed jobs are retried up to ``max_retries`` times.
    """

    __tablename__ = "indexing_queue"

    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        server_default="pending", index=True,
    )
    progress: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False,
        server_default=text("'{}'::json"),
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        server_default="0", index=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False, server_default="3",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_history: Mapped[list[Any]] = mapped_column(
        JSON, default=list, nullable=False,
        server_default=text("'[]'::json"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # -- Relationships -------------------------------------------------------
    document: Mapped[Document] = relationship(
        "Document", back_populates="queue_items",
    )

    def __repr__(self) -> str:
        return (
            f"<IndexingQueue id={self.queue_id} doc={self.document_id} "
            f"op={self.operation!r} status={self.status!r}>"
        )


class Trash(Base):
    """A soft-deleted document preserved for potential recovery.

    When a document is "deleted" its metadata is moved here so it can be
    restored before the automatic purge date (``auto_purge_at``) elapses.
    """

    __tablename__ = "trash"

    trash_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    original_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
    )
    original_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False,
        server_default=text("'{}'::json"),
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    auto_purge_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Trash id={self.trash_id} path={self.original_file_path!r}>"


class VaultSettings(Base):
    """Key-value settings store for the vault/application.

    Arbitrary JSON values are keyed by a short string.  This replaces a
    traditional config file for runtime-settable preferences.
    """

    __tablename__ = "vault_settings"

    key: Mapped[str] = mapped_column(
        String(100), primary_key=True,
    )
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<VaultSettings key={self.key!r}>"
