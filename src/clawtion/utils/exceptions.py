"""Exception hierarchy for clawtion.

All custom exceptions inherit from ``ClawtionError``, providing a
consistent ``code``, ``message``, and ``details`` structure that
can be surfaced through any interface (CLI, MCP, REST API).
"""

from __future__ import annotations

from typing import Any


class ClawtionError(Exception):
    """Base exception for all clawtion errors.

    Attributes:
        code:    Machine-readable error code (e.g. "DOCUMENT_NOT_FOUND").
        message: Human-readable description of the error.
        details: Optional structured context (e.g. offending document ID).
    """

    def __init__(
        self,
        code: str = "INTERNAL_ERROR",
        message: str = "An unexpected error occurred",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception to a JSON-compatible dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class DocumentNotFoundError(ClawtionError):
    """Raised when a requested document does not exist."""

    def __init__(
        self,
        document_id: str | None = None,
        file_path: str | None = None,
    ) -> None:
        identifier = document_id or file_path or "unknown"
        super().__init__(
            code="DOCUMENT_NOT_FOUND",
            message=f"Document not found: {identifier}",
            details={
                "document_id": document_id,
                "file_path": file_path,
            },
        )


class EmbeddingError(ClawtionError):
    """Raised when an embedding API call fails."""

    def __init__(
        self,
        message: str = "Embedding generation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="EMBEDDING_ERROR",
            message=message,
            details=details,
        )


class IndexingError(ClawtionError):
    """Raised when the indexing pipeline encounters a non-recoverable error."""

    def __init__(
        self,
        message: str = "Indexing operation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="INDEXING_ERROR",
            message=message,
            details=details,
        )


class VaultError(ClawtionError):
    """Raised for vault-related failures (file access, permissions, etc.)."""

    def __init__(
        self,
        message: str = "Vault operation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="VAULT_ERROR",
            message=message,
            details=details,
        )


class ValidationError(ClawtionError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class QueueError(ClawtionError):
    """Raised for indexing queue errors (full queue, invalid state, etc.)."""

    def __init__(
        self,
        message: str = "Queue operation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code="QUEUE_ERROR",
            message=message,
            details=details,
        )
