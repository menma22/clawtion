"""Protocols and data classes for the embedding and file-processing layer.

Defines the structural interfaces that concrete implementations
(e.g. :class:`~clawtion.core.embedding.gemini.GeminiEmbeddingClient`) must
satisfy, together with immutable data transfer objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# -- Data objects ------------------------------------------------------------

@dataclass(frozen=True)
class EmbeddingResult:
    """The result of a single embedding operation.

    Attributes:
        embedding: Dense vector as a list of floats.
        model:     Name of the model that produced the embedding.
        dimensions: Number of dimensions in the vector.
        token_count: Estimated number of tokens consumed.
    """
    embedding: list[float] = field(repr=False)
    model: str
    dimensions: int
    token_count: int


@dataclass(frozen=True)
class ExtractedContent:
    """Content extracted from a file by a :class:`FileProcessor`.

    Attributes:
        text:     Extracted plain-text content.
        file_path: Absolute path to the source file.
        metadata: Arbitrary metadata dict (encoding, page count, …).
    """
    text: str
    file_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


# -- Exceptions --------------------------------------------------------------

class EmbeddingError(Exception):
    """Generic error raised when an embedding operation fails."""

    def __init__(self, message: str = "", details: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class EmbeddingRateLimitError(EmbeddingError):
    """Raised when the embedding API rate-limits the request."""


class EmbeddingBatchError(EmbeddingError):
    """Raised when a batch embedding operation partially or fully fails."""


# -- Protocols ---------------------------------------------------------------

@runtime_checkable
class EmbeddingClient(Protocol):
    """Interface for embedding providers (Gemini, OpenAI, …).

    Every implementation must satisfy the methods below so that callers can
    embed documents, queries, and batches interchangeably.
    """

    @property
    def model_name(self) -> str:
        """Return the model identifier (e.g. ``"gemini-embedding-2-preview"``)."""
        ...

    @property
    def dimensions(self) -> int:
        """Return the output dimensionality of the embedding model."""
        ...

    async def embed_document(
        self,
        content: str,
        title: str | None = None,
    ) -> EmbeddingResult:
        """Embed a single document chunk.

        Args:
            content: The raw text to embed.
            title:   Optional document title (used for prefix-based
                     task specification if the client supports it).

        Returns:
            An :class:`EmbeddingResult` with the vector.
        """
        ...

    async def embed_query(self, query: str) -> EmbeddingResult:
        """Embed a search query.

        Args:
            query: The user's search text.

        Returns:
            An :class:`EmbeddingResult` with the query vector.
        """
        ...

    async def embed_batch(
        self,
        contents: list[str],
    ) -> list[EmbeddingResult]:
        """Embed multiple texts in a single API call.

        Args:
            contents: List of text strings to embed.

        Returns:
            A list of :class:`EmbeddingResult` objects in the same order.
        """
        ...


@runtime_checkable
class FileProcessor(Protocol):
    """Interface for file-type-specific content extractors.

    Each implementation handles one or more file extensions and knows how to
    convert them to plain text for chunking and embedding.
    """

    def can_process(self, file_path: str) -> bool:
        """Return True if this processor can handle *file_path*.

        Typically checks the extension, but may also inspect magic bytes.
        """
        ...

    def extract_content(self, file_path: str) -> dict[str, Any]:
        """Extract text and metadata from *file_path*.

        Returns:
            A dict with at least the key ``"text"``.  Additional keys are
            stored as metadata on the resulting :class:`ExtractedContent`.
        """
        ...

    def get_supported_extensions(self) -> list[str]:
        """Return the list of file extensions this processor supports.

        Extensions should include the leading dot (e.g. ``[".md", ".txt"]``).
        """
        ...
