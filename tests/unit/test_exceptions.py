"""Unit tests for clawtion exception hierarchy."""

import pytest
from clawtion.utils.exceptions import (
    ClawtionError,
    DocumentNotFoundError,
    EmbeddingError,
    IndexingError,
    VaultError,
    ValidationError,
    QueueError,
)


class TestClawtionError:
    def test_default_values(self) -> None:
        exc = ClawtionError()
        assert exc.code == "INTERNAL_ERROR"
        assert exc.message == "An unexpected error occurred"
        assert exc.details == {}

    def test_custom_values(self) -> None:
        exc = ClawtionError(
            code="CUSTOM_ERROR",
            message="Custom message",
            details={"key": "value"},
        )
        assert exc.code == "CUSTOM_ERROR"
        assert exc.message == "Custom message"
        assert exc.details == {"key": "value"}

    def test_str_representation(self) -> None:
        exc = ClawtionError(code="TEST", message="Test message")
        assert str(exc) == "[TEST] Test message"

    def test_to_dict(self) -> None:
        exc = ClawtionError(code="TEST", message="Test", details={"x": 1})
        result = exc.to_dict()
        assert result == {"code": "TEST", "message": "Test", "details": {"x": 1}}

    def test_is_exception(self) -> None:
        exc = ClawtionError()
        assert isinstance(exc, Exception)


class TestDocumentNotFoundError:
    def test_with_document_id(self) -> None:
        exc = DocumentNotFoundError(document_id="abc-123")
        assert exc.code == "DOCUMENT_NOT_FOUND"
        assert "abc-123" in exc.message
        assert exc.details["document_id"] == "abc-123"

    def test_with_file_path(self) -> None:
        exc = DocumentNotFoundError(file_path="notes/test.md")
        assert exc.details["file_path"] == "notes/test.md"

    def test_without_identifier(self) -> None:
        exc = DocumentNotFoundError()
        assert "unknown" in exc.message

    def test_inherits_clawtion_error(self) -> None:
        exc = DocumentNotFoundError(document_id="test")
        assert isinstance(exc, ClawtionError)


class TestEmbeddingError:
    def test_default(self) -> None:
        exc = EmbeddingError()
        assert exc.code == "EMBEDDING_ERROR"

    def test_with_details(self) -> None:
        exc = EmbeddingError(message="API timeout", details={"retry": 3})
        assert exc.message == "API timeout"
        assert exc.details == {"retry": 3}


class TestIndexingError:
    def test_default(self) -> None:
        exc = IndexingError()
        assert exc.code == "INDEXING_ERROR"

    def test_with_details(self) -> None:
        exc = IndexingError(message="Chunking failed", details={"file": "test.md"})
        assert exc.message == "Chunking failed"


class TestVaultError:
    def test_default(self) -> None:
        exc = VaultError()
        assert exc.code == "VAULT_ERROR"


class TestValidationError:
    def test_default(self) -> None:
        exc = ValidationError()
        assert exc.code == "VALIDATION_ERROR"


class TestQueueError:
    def test_default(self) -> None:
        exc = QueueError()
        assert exc.code == "QUEUE_ERROR"

    def test_with_details(self) -> None:
        exc = QueueError(message="Queue full", details={"pending": 100})
        assert exc.message == "Queue full"
        assert exc.details == {"pending": 100}
