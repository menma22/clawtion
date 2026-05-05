"""Namespace service implementation.

Namespaces provide logical partitioning within a single vault, enabling
multi-project or multi-tenant use cases.  Each namespace groups chunks
under a named, isolated partition.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from clawtion.utils.exceptions import ClawtionError
from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager

logger = get_logger(__name__)


@dataclass(frozen=True)
class NamespaceInfo:
    """Frozen dataclass representing a namespace record."""

    namespace_id: str
    name: str
    description: str
    created_at: str
    chunk_count: int = 0


class NamespaceService:
    """Service for CRUD operations on namespaces.

    Constructor DI::

        service = NamespaceService(db=db_instance)
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ---- CRUD ------------------------------------------------------------------

    async def create(self, name: str, description: str = "") -> NamespaceInfo:
        """Create a new namespace.

        Args:
            name: Unique name for the namespace (max 100 chars).
            description: Optional human-readable description.

        Returns:
            A ``NamespaceInfo`` frozen dataclass for the created namespace.

        Raises:
            ClawtionError: If a namespace with the same name already exists.
        """
        if not name or len(name) > 100:
            raise ClawtionError(
                code="VALIDATION_ERROR",
                message="Namespace name must be 1-100 characters.",
            )

        namespace_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        try:
            await self._db.execute(
                """
                INSERT INTO namespaces (namespace_id, name, description, created_at)
                VALUES (:namespace_id, :name, :description, :created_at)
                """,
                {
                    "namespace_id": namespace_id,
                    "name": name,
                    "description": description,
                    "created_at": now,
                },
            )
        except Exception as exc:
            err_str = str(exc)
            if "unique" in err_str.lower() or "duplicate" in err_str.lower():
                raise ClawtionError(
                    code="NAMESPACE_EXISTS",
                    message=f"Namespace '{name}' already exists.",
                ) from exc
            raise ClawtionError(
                code="NAMESPACE_CREATE_FAILED",
                message=f"Failed to create namespace: {exc}",
            ) from exc

        logger.info("Namespace created", namespace_id=namespace_id, name=name)
        return NamespaceInfo(
            namespace_id=namespace_id,
            name=name,
            description=description,
            created_at=now.isoformat(),
        )

    async def list_all(self) -> list[NamespaceInfo]:
        """Return all namespaces ordered by creation time (newest first).

        Returns:
            A list of ``NamespaceInfo`` frozen dataclass instances.
        """
        rows = await self._db.execute(
            """
            SELECT
                n.namespace_id,
                n.name,
                n.description,
                n.created_at,
                COUNT(dc.chunk_id)::int AS chunk_count
            FROM namespaces n
            LEFT JOIN document_chunks dc ON dc.namespace_id = n.namespace_id
            GROUP BY n.namespace_id, n.name, n.description, n.created_at
            ORDER BY n.created_at DESC
            """,
            {},
        )
        return [
            NamespaceInfo(
                namespace_id=row["namespace_id"],
                name=row["name"],
                description=row["description"],
                created_at=_fmt_dt(row["created_at"]),
                chunk_count=row["chunk_count"],
            )
            for row in rows
        ]

    async def get(self, namespace_id: str) -> NamespaceInfo:
        """Retrieve a single namespace by its ID.

        Args:
            namespace_id: The namespace UUID (hyphens optional).

        Returns:
            A ``NamespaceInfo`` frozen dataclass.

        Raises:
            ClawtionError: If the namespace does not exist.
        """
        row = await self._db.execute_one(
            """
            SELECT
                n.namespace_id,
                n.name,
                n.description,
                n.created_at,
                COUNT(dc.chunk_id)::int AS chunk_count
            FROM namespaces n
            LEFT JOIN document_chunks dc ON dc.namespace_id = n.namespace_id
            WHERE n.namespace_id = :namespace_id
            GROUP BY n.namespace_id, n.name, n.description, n.created_at
            """,
            {"namespace_id": namespace_id},
        )
        if row is None:
            raise ClawtionError(
                code="NAMESPACE_NOT_FOUND",
                message=f"Namespace not found: {namespace_id}",
            )
        return NamespaceInfo(
            namespace_id=row["namespace_id"],
            name=row["name"],
            description=row["description"],
            created_at=_fmt_dt(row["created_at"]),
            chunk_count=row["chunk_count"],
        )

    async def delete(self, namespace_id: str) -> None:
        """Delete a namespace.

        Chunks assigned to this namespace will have their ``namespace_id``
        set to NULL (``ON DELETE SET NULL``).

        Args:
            namespace_id: The namespace UUID to delete.

        Raises:
            ClawtionError: If the namespace does not exist.
        """
        await self._db.execute(
            "DELETE FROM namespaces WHERE namespace_id = :namespace_id",
            {"namespace_id": namespace_id},
        )
        # Some DB wrappers return row count — we check existence with a pre-check.
        existing = await self._db.execute_one(
            "SELECT 1 FROM namespaces WHERE namespace_id = :namespace_id",
            {"namespace_id": namespace_id},
        )
        # If the DELETE affected no rows, the namespace didn't exist before either.
        # The `existing` check is a safety net for drivers that don't report row counts.
        if existing is not None:
            # Namespace still exists (foreign key prevented deletion)
            raise ClawtionError(
                code="NAMESPACE_DELETE_FAILED",
                message="Could not delete namespace (foreign key constraint violated unexpectedly).",
            )

        logger.info("Namespace deleted", namespace_id=namespace_id)

    # ---- Assignment -----------------------------------------------------------

    async def assign_chunk(self, chunk_id: str, namespace_id: str) -> None:
        """Assign a single chunk to a namespace.

        Args:
            chunk_id: The chunk UUID.
            namespace_id: The target namespace UUID.

        Raises:
            ClawtionError: If the chunk or namespace does not exist.
        """
        await self._resolve_namespace(namespace_id)

        result = await self._db.execute(
            """
            UPDATE document_chunks
            SET namespace_id = :namespace_id
            WHERE chunk_id = :chunk_id
            """,
            {"namespace_id": namespace_id, "chunk_id": chunk_id},
        )
        if result is None or len(result) == 0:
            # Verify by query
            row = await self._db.execute_one(
                "SELECT 1 FROM document_chunks WHERE chunk_id = :chunk_id",
                {"chunk_id": chunk_id},
            )
            if row is None:
                raise ClawtionError(
                    code="CHUNK_NOT_FOUND",
                    message=f"Chunk not found: {chunk_id}",
                )

        logger.debug("Chunk assigned to namespace", chunk_id=chunk_id, namespace_id=namespace_id)

    async def assign_document(self, document_id: str, namespace_id: str) -> int:
        """Assign all chunks of a document to a namespace.

        Args:
            document_id: The document UUID.
            namespace_id: The target namespace UUID.

        Returns:
            Number of chunks updated.

        Raises:
            ClawtionError: If the document or namespace does not exist.
        """
        await self._resolve_namespace(namespace_id)

        # Verify document exists
        doc = await self._db.execute_one(
            "SELECT 1 FROM documents WHERE document_id = :document_id AND is_deleted = false",
            {"document_id": document_id},
        )
        if doc is None:
            raise ClawtionError(
                code="DOCUMENT_NOT_FOUND",
                message=f"Document not found: {document_id}",
            )

        await self._db.execute(
            """
            UPDATE document_chunks
            SET namespace_id = :namespace_id
            WHERE document_id = :document_id
            """,
            {"namespace_id": namespace_id, "document_id": document_id},
        )

        # Count affected chunks
        count_row = await self._db.execute_one(
            """
            SELECT COUNT(*)::int AS cnt FROM document_chunks
            WHERE document_id = :document_id AND namespace_id = :namespace_id
            """,
            {"document_id": document_id, "namespace_id": namespace_id},
        )
        updated = count_row["cnt"] if count_row else 0

        logger.info(
            "Document assigned to namespace",
            document_id=document_id,
            namespace_id=namespace_id,
            chunks_updated=updated,
        )
        return updated

    async def get_chunks(self, namespace_id: str) -> list[dict[str, Any]]:
        """Retrieve all chunks belonging to a namespace.

        Args:
            namespace_id: The namespace UUID.

        Returns:
            List of chunk dictionaries (without embeddings).
        """
        rows = await self._db.execute(
            """
            SELECT
                dc.chunk_id,
                dc.document_id,
                dc.chunk_level,
                dc.chunk_index,
                dc.chunk_total,
                dc.content,
                dc.content_with_context,
                dc.heading_path,
                dc.token_count,
                dc.char_count,
                d.file_path,
                d.title
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE dc.namespace_id = :namespace_id
            ORDER BY d.file_path, dc.chunk_index
            """,
            {"namespace_id": namespace_id},
        )
        return [dict(row) for row in rows]

    # ---- Internal helpers ------------------------------------------------------

    async def _resolve_namespace(self, namespace_id: str) -> None:
        """Verify that a namespace exists; raise if not."""
        row = await self._db.execute_one(
            "SELECT 1 FROM namespaces WHERE namespace_id = :namespace_id",
            {"namespace_id": namespace_id},
        )
        if row is None:
            raise ClawtionError(
                code="NAMESPACE_NOT_FOUND",
                message=f"Namespace not found: {namespace_id}",
            )


def _fmt_dt(dt: Any) -> str:
    """Format a datetime value as ISO 8601 string, or return empty string."""
    if not dt:
        return ""
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)
