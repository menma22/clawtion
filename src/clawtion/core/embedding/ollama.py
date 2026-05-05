"""Ollama embedding client implementation for clawtion.

Communicates with a local Ollama instance via its REST API to produce
embeddings, supporting:

* Single document/query embedding via ``POST /api/embeddings``.
* Batch embedding via concurrent requests to the same endpoint.
* Automatic retry with exponential back-off on connection errors and
  transient server errors.
* Configurable model selection (e.g. ``nomic-embed-text``, ``mxbai-embed-large``).

Usage::

    client = OllamaEmbeddingClient(base_url="http://localhost:11434",
                                   model="nomic-embed-text")
    result = await client.embed_document("Some text")
    query_vec = await client.embed_query("search phrase")
    batch = await client.embed_batch(["text1", "text2"])
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, TypeVar

from clawtion.core.embedding.client import (
    EmbeddingError,
    EmbeddingRateLimitError,
    EmbeddingResult,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import httpx

_T = TypeVar("_T")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate-limit / transient-error retry helper
# ---------------------------------------------------------------------------

_BASE_DELAY_S = 1.0
_MAX_RETRIES = 5
_MAX_DELAY_S = 60.0


def _is_transient_ollama_error(exc: Exception) -> bool:
    """Return ``True`` if *exc* is a transient Ollama API error."""
    if isinstance(exc, EmbeddingRateLimitError):
        return True
    msg = str(exc).lower()
    for token in (
        "timeout",
        "connection refused",
        "connection reset",
        "connection error",
        "service_unavailable",
        "bad_gateway",
        "internal server error",
        "429",
        "500",
        "502",
        "503",
        "504",
    ):
        if token in msg:
            return True
    return False


async def _retry_with_backoff(
    coro_factory: Callable[[], Awaitable[_T]],
    label: str = "",
) -> _T:
    """Await *coro_factory* and retry on transient Ollama errors.

    Args:
        coro_factory: A zero-argument callable that returns an awaitable.
        label:        Human-readable label for log messages.

    Returns:
        The result of the awaited coroutine.

    Raises:
        EmbeddingRateLimitError: After exhausting retries.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if not _is_transient_ollama_error(exc):
                raise
            if attempt < _MAX_RETRIES:
                delay = min(
                    _BASE_DELAY_S * (2**attempt) + (time.monotonic() % 1),
                    _MAX_DELAY_S,
                )
                logger.warning(
                    "Ollama embedding %s retry %d/%d after %.1fs: %s",
                    label,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Ollama embedding %s exhausted after %d retries: %s",
                    label,
                    _MAX_RETRIES,
                    exc,
                )
    raise EmbeddingRateLimitError(
        f"Ollama embedding {label} failed after {_MAX_RETRIES} retries: {last_exc}",
    ) from last_exc


# ---------------------------------------------------------------------------
# Ollama Embedding Client
# ---------------------------------------------------------------------------


class OllamaEmbeddingClient:
    """Embedding client backed by a local Ollama instance.

    Communicates with the Ollama HTTP API (``POST /api/embeddings``) to
    generate embeddings using locally-hosted models such as
    ``nomic-embed-text`` or ``mxbai-embed-large``.

    Usage::

        client = OllamaEmbeddingClient()
        result = await client.embed_document("Some text")
        query_vec = await client.embed_query("search phrase")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        dimensions: int = 768,
    ) -> None:
        """Initialise the client.

        Args:
            base_url:   Base URL of the Ollama server (including port).
            model:      Name of the embedding model to use.
            dimensions: Output dimensionality of the model.  This is **not**
                        sent to the API (Ollama determines the actual dimensions
                        from the model) but is stored as metadata on results.
        """
        self._base_url: str = base_url.rstrip("/")
        self._model: str = model
        self._dimensions: int = dimensions
        self._client: httpx.AsyncClient | None = None

    # -- Properties ----------------------------------------------------------

    @property
    def model_name(self) -> str:
        """Return the model identifier (e.g. ``"nomic-embed-text"``)."""
        return self._model

    @property
    def dimensions(self) -> int:
        """Return the configured output dimensionality."""
        return self._dimensions

    @property
    def base_url(self) -> str:
        """Return the Ollama server base URL."""
        return self._base_url

    # -- Internal helpers ----------------------------------------------------

    def _lazy_init(self) -> None:
        """Import ``httpx`` and initialise an ``AsyncClient`` on first use."""
        if self._client is not None:
            return
        try:
            import httpx

            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        except ImportError:
            raise EmbeddingError(
                "httpx package is not installed. "
                "Run: pip install httpx>=0.27.0",
            ) from None

    async def _call_embeddings_api(self, prompt: str) -> dict[str, Any]:
        """Make a single ``POST /api/embeddings`` call.

        Args:
            prompt: The text to embed.

        Returns:
            The parsed JSON response dict.

        Raises:
            EmbeddingRateLimitError: On transient/rate-limit errors (retryable).
            EmbeddingError:          On non-retryable API errors.
        """
        import httpx

        try:
            response = await self._client.post(  # type: ignore[union-attr]
                "/api/embeddings",
                json={"model": self._model, "prompt": prompt},
            )
        except httpx.TimeoutException as exc:
            raise EmbeddingRateLimitError(
                f"Ollama request timed out: {exc}",
            ) from exc
        except httpx.ConnectError as exc:
            raise EmbeddingRateLimitError(
                f"Ollama connection failed: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingError(
                f"Ollama HTTP error: {exc}",
                details={"model": self._model},
            ) from exc

        if response.status_code != 200:
            detail = response.text
            try:
                body = response.json()
                detail = body.get("error", body)
            except Exception:
                pass

            if response.status_code in (429,) or response.status_code >= 500:
                raise EmbeddingRateLimitError(
                    f"Ollama API returned HTTP {response.status_code}: {detail}",
                )
            raise EmbeddingError(
                f"Ollama API returned HTTP {response.status_code}: {detail}",
                details={
                    "status_code": response.status_code,
                    "model": self._model,
                },
            )

        return response.json()

    def _parse_response(self, data: dict[str, Any]) -> EmbeddingResult:
        """Convert an Ollama API response dict into an :class:`EmbeddingResult`.

        Args:
            data: The parsed JSON response from ``/api/embeddings``.

        Returns:
            An :class:`EmbeddingResult`.

        Raises:
            EmbeddingError: If the response is malformed.
        """
        try:
            embedding: list[float] = list(data["embedding"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError(
                f"Failed to parse Ollama embedding response: {exc}",
            ) from exc

        return EmbeddingResult(
            embedding=embedding,
            model=self._model,
            dimensions=len(embedding),
            token_count=0,  # Ollama does not expose token counts.
        )

    async def _embed_single(self, text: str) -> EmbeddingResult:
        """Embed a single text string via the Ollama API.

        Args:
            text: Text to embed.

        Returns:
            An :class:`EmbeddingResult` with actual dimensions from the API.
        """
        data = await self._call_embeddings_api(text)
        return self._parse_response(data)

    # -- Public API ----------------------------------------------------------

    async def embed_document(
        self,
        content: str,
        title: str | None = None,
    ) -> EmbeddingResult:
        """Embed a single document chunk.

        .. note::
            Ollama embedding models do not distinguish between documents
            and queries, so *title* is ignored.

        Args:
            content: Document text to embed.
            title:   Ignored (Ollama compatibility shim).

        Returns:
            An :class:`EmbeddingResult` with the vector.

        Raises:
            EmbeddingRateLimitError: If the API rate-limits and retries are exhausted.
            EmbeddingError:          On non-retryable errors.
        """
        _ = title
        self._lazy_init()
        return await _retry_with_backoff(
            lambda: self._embed_single(content),
            label="embed_document",
        )

    async def embed_query(self, query: str) -> EmbeddingResult:
        """Embed a search query.

        Args:
            query: User query string.

        Returns:
            An :class:`EmbeddingResult` with the query vector.

        Raises:
            EmbeddingRateLimitError: If the API rate-limits and retries are exhausted.
            EmbeddingError:          On non-retryable errors.
        """
        self._lazy_init()
        return await _retry_with_backoff(
            lambda: self._embed_single(query),
            label="embed_query",
        )

    async def embed_batch(
        self,
        contents: list[str],
    ) -> list[EmbeddingResult]:
        """Embed multiple texts by calling the API for each input.

        .. note::
            The ``/api/embeddings`` endpoint only accepts one prompt at a
            time, so batch is implemented as concurrent individual requests
            (up to 5 at once).

        Args:
            contents: List of text strings to embed.

        Returns:
            A list of :class:`EmbeddingResult` objects in the same order as
            *contents*.

        Raises:
            EmbeddingBatchError: If any individual embedding fails.
            EmbeddingRateLimitError: If the API rate-limits and retries are exhausted.
        """
        if not contents:
            return []

        self._lazy_init()

        semaphore = asyncio.Semaphore(5)

        async def _embed_one(text: str) -> EmbeddingResult:
            async with semaphore:
                return await _retry_with_backoff(
                    lambda: self._embed_single(text),
                    label="embed_batch_item",
                )

        tasks = [_embed_one(text) for text in contents]
        results: list[EmbeddingResult] = await asyncio.gather(*tasks)

        return results
