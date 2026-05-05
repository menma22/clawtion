"""OpenAI embedding client implementation for clawtion.

Wraps the ``openai`` Python package (``AsyncOpenAI`` client) to produce
embeddings via OpenAI's embedding models, supporting:

* Single document/query embedding.
* Batch embedding via the API's built-in multi-input support.
* Automatic retry with exponential back-off on transient errors.
* Configurable model selection and output dimensionality.

Supported models:
* ``text-embedding-3-small``  (default, max 1536 dimensions)
* ``text-embedding-3-large``  (max 3072 dimensions)
* ``text-embedding-ada-002``  (fixed 1536 dimensions)
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

_T = TypeVar("_T")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default dimensions per model
# ---------------------------------------------------------------------------

_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

# ---------------------------------------------------------------------------
# Rate-limit / transient-error retry helper
# ---------------------------------------------------------------------------

_BASE_DELAY_S = 1.0
_MAX_RETRIES = 5
_MAX_DELAY_S = 60.0


def _is_transient_openai_error(exc: Exception) -> bool:
    """Return ``True`` if *exc* is a transient OpenAI API error.

    Checks by type first (when ``openai`` is importable), then falls back
    to matching on the error-message string for robustness.
    """
    # Type-based check (preferred)
    try:
        from openai import (
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        )

        if isinstance(
            exc,
            (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError),
        ):
            return True
    except ImportError:
        pass

    # Fallback: message-based check
    msg = str(exc).lower()
    for token in (
        "rate_limit",
        "rate limit",
        "timeout",
        "internal_server_error",
        "service_unavailable",
        "bad_gateway",
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
    """Await *coro_factory* and retry on transient OpenAI errors.

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
            if not _is_transient_openai_error(exc):
                raise
            if attempt < _MAX_RETRIES:
                delay = min(
                    _BASE_DELAY_S * (2**attempt) + (time.monotonic() % 1),
                    _MAX_DELAY_S,
                )
                logger.warning(
                    "OpenAI embedding %s retry %d/%d after %.1fs: %s",
                    label,
                    attempt + 1,
                    _MAX_RETRIES,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "OpenAI embedding %s exhausted after %d retries: %s",
                    label,
                    _MAX_RETRIES,
                    exc,
                )
    raise EmbeddingRateLimitError(
        f"OpenAI embedding {label} failed after {_MAX_RETRIES} retries: {last_exc}",
    ) from last_exc


# ---------------------------------------------------------------------------
# OpenAI Embedding Client
# ---------------------------------------------------------------------------


class OpenAIEmbeddingClient:
    """Embedding client backed by OpenAI's embedding API.

    Supports ``text-embedding-3-small`` (default), ``text-embedding-3-large``,
    and ``text-embedding-ada-002`` with automatic retry and configurable
    output dimensionality.

    Usage::

        client = OpenAIEmbeddingClient(api_key="sk-...")
        result = await client.embed_document("Some chunk text")
        query_vec = await client.embed_query("search phrase")
        batch = await client.embed_batch(["text1", "text2", "text3"])
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int | None = None,
    ) -> None:
        """Initialise the client.

        Args:
            api_key:    OpenAI API key.
            model:      Embedding model name.
            dimensions: Desired output dimensionality.  If ``None``, uses
                        the model's default (1536 for ``text-embedding-3-small``,
                        3072 for ``text-embedding-3-large``, 1536 for
                        ``text-embedding-ada-002``).  Values exceeding the
                        model's maximum are silently capped.
        """
        self._api_key: str = api_key
        self._model: str = model

        if dimensions is not None:
            self._dimensions = dimensions
        else:
            self._dimensions = _MODEL_DIMENSIONS.get(model, 1536)

        # Cap dimensions to model maximum
        model_max = _MODEL_DIMENSIONS.get(model)
        if model_max is not None and self._dimensions > model_max:
            self._dimensions = model_max

        self._client: Any = None  # Lazy-initialised AsyncOpenAI

    # -- Properties ----------------------------------------------------------

    @property
    def model_name(self) -> str:
        """Return the model identifier (e.g. ``"text-embedding-3-small"``)."""
        return self._model

    @property
    def dimensions(self) -> int:
        """Return the configured output dimensionality."""
        return self._dimensions

    @property
    def api_key(self) -> str:
        """Return the configured API key.

        Exposed so that other components (e.g. ``BatchEmbeddingClient``)
        can access it without requiring a separate copy.
        """
        return self._api_key

    # -- Internal helpers ----------------------------------------------------

    def _lazy_init(self) -> None:
        """Import and initialise the ``AsyncOpenAI`` client on first use."""
        if self._client is not None:
            return
        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
        except ImportError:
            raise EmbeddingError(
                "openai package is not installed. "
                "Run: pip install openai>=1.0.0",
            ) from None

    def _is_dimensions_supported(self) -> bool:
        """Return ``True`` if the model supports the ``dimensions`` parameter."""
        return self._model.startswith("text-embedding-3")

    async def _do_embed(self, inputs: list[str]) -> list[EmbeddingResult]:
        """Execute one embedding API call.

        Args:
            inputs: Text strings to embed.

        Returns:
            A list of :class:`EmbeddingResult` objects, one per input, in the
            same order.

        Raises:
            openai.RateLimitError / APITimeoutError / APIConnectionError
                / InternalServerError: let the retry wrapper handle these.
            EmbeddingError: On non-retryable API errors.
        """
        import openai

        kwargs: dict[str, Any] = {
            "model": self._model,
            "input": inputs,
        }
        if self._is_dimensions_supported():
            kwargs["dimensions"] = self._dimensions

        try:
            response = await self._client.embeddings.create(**kwargs)  # type: ignore[union-attr]
        except (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
        ):
            raise  # Let the retry wrapper handle these
        except openai.APIError as exc:
            raise EmbeddingError(
                f"OpenAI API error: {exc}",
                details={
                    "model": self._model,
                    "input_count": len(inputs),
                    "status_code": getattr(exc, "status_code", None),
                },
            ) from exc

        # Parse response
        results: list[EmbeddingResult] = []
        for data in response.data:
            results.append(
                EmbeddingResult(
                    embedding=list(data.embedding),
                    model=self._model,
                    dimensions=len(data.embedding),
                    token_count=response.usage.total_tokens if response.usage else 0,
                ),
            )

        if len(results) != len(inputs):
            raise EmbeddingError(
                f"Expected {len(inputs)} embeddings but got {len(results)}",
            )

        return results

    # -- Public API ----------------------------------------------------------

    async def embed_document(
        self,
        content: str,
        title: str | None = None,
    ) -> EmbeddingResult:
        """Embed a single document chunk.

        .. note::
            OpenAI embedding models do **not** distinguish between documents
            and queries, so *title* is ignored.

        Args:
            content: Document text to embed.
            title:   Ignored (OpenAI compatibility shim).

        Returns:
            An :class:`EmbeddingResult` with the vector.

        Raises:
            EmbeddingRateLimitError: If the API rate-limits and retries are exhausted.
            EmbeddingError:          On non-retryable errors.
        """
        _ = title  # Unused — OpenAI models don't use task prefixes.
        self._lazy_init()
        results = await _retry_with_backoff(
            lambda: self._do_embed([content]),
            label="embed_document",
        )
        return results[0]

    async def embed_query(self, query: str) -> EmbeddingResult:
        """Embed a search query.

        .. note::
            OpenAI embedding models do **not** distinguish between queries
            and documents; this is behaviourally identical to
            :meth:`embed_document`.

        Args:
            query: User query string.

        Returns:
            An :class:`EmbeddingResult` with the query vector.

        Raises:
            EmbeddingRateLimitError: If the API rate-limits and retries are exhausted.
            EmbeddingError:          On non-retryable errors.
        """
        self._lazy_init()
        results = await _retry_with_backoff(
            lambda: self._do_embed([query]),
            label="embed_query",
        )
        return results[0]

    async def embed_batch(
        self,
        contents: list[str],
    ) -> list[EmbeddingResult]:
        """Embed multiple texts in a single API call.

        Args:
            contents: List of text strings to embed.

        Returns:
            A list of :class:`EmbeddingResult` objects in the same order as
            *contents*.

        Raises:
            EmbeddingBatchError: If the batch operation fails.
            EmbeddingRateLimitError: If the API rate-limits and retries are exhausted.
        """
        if not contents:
            return []

        self._lazy_init()
        results = await _retry_with_backoff(
            lambda: self._do_embed(contents),
            label="embed_batch",
        )

        if len(results) != len(contents):
            raise EmbeddingError(
                f"Batch embedding returned {len(results)} results for "
                f"{len(contents)} inputs.",
            )
        return results
