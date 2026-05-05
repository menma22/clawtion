"""Gemini Embedding 2 client implementation for clawtion.

Wraps the ``google-genai`` SDK to produce embeddings via the
``text-embedding-004`` model, supporting:

* Single document/query embedding with manual prefix.
* Batch embedding via the SDK's built-in multi-content API.
* Automatic retry with exponential back-off on rate-limit errors.
* Approximate token counting for observability.
"""

from __future__ import annotations

import asyncio
import logging
import math
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


# -- Approximate token counter ----------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Return a rough token count for *text*.

    Uses a simple ratio of 4 characters per token (common for English and
    code-like content).  This is *not* model-precise but is good enough for
    logging and cost estimation.
    """
    return max(1, math.ceil(len(text) / 4))


# -- Rate-limit retry helper -------------------------------------------------

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_BASE_DELAY_S = 1.0
_MAX_RETRIES = 5
_MAX_DELAY_S = 60.0


def _is_retryable(exc: Exception) -> bool:
    """Return True if *exc* looks like a transient API error."""
    msg = str(exc).lower()
    # google-genai SDK may raise google.api_core exceptions or plain
    # exceptions with similar wording.
    for token in ("rate_limit", "resource_exhausted", "internal", "unavailable",
                  "deadline_exceeded", "service_unavailable", "429", "500", "502", "503", "504"):
        if token in msg:
            return True
    return False


async def _retry_with_backoff(
    coro_factory: Callable[[], Awaitable[_T]],
    label: str = "",
) -> _T:
    """Await *coro_factory* and retry on transient errors.

    Args:
        coro_factory: A zero-argument callable that returns an awaitable.
        label:       Human-readable label for log messages.

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
            if not _is_retryable(exc):
                raise
            if attempt < _MAX_RETRIES:
                delay = min(_BASE_DELAY_S * (2 ** attempt) + (time.monotonic() % 1), _MAX_DELAY_S)
                logger.warning(
                    "Embedding API %s retry %d/%d after %.1fs: %s",
                    label, attempt + 1, _MAX_RETRIES, delay, exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Embedding API %s exhausted after %d retries: %s",
                    label, _MAX_RETRIES, exc,
                )
    # Unreachable if loop always raises, but satisfy the type checker.
    raise EmbeddingRateLimitError(
        f"Embedding API {label} failed after {_MAX_RETRIES} retries: {last_exc}",
    ) from last_exc


# -- Gemini Embedding Client -------------------------------------------------

_DOCUMENT_PREFIX_TEMPLATE = "title: {title} | text: {content}"
_QUERY_PREFIX_TEMPLATE = "task: search result | query: {query}"
_TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"
_TASK_TYPE_QUERY = "RETRIEVAL_QUERY"

_DEFAULT_MODEL = "models/text-embedding-004"


class GeminiEmbeddingClient:
    """Embedding client backed by Google Gemini Embedding 2 (``text-embedding-004``).

    Features:

    * Manual prefix mode: Prepends a task description so the same model
      can distinguish documents from queries without a separate task_type
      parameter (useful for models that don't support the ``task_type``
      field).
    * Configurable output dimensionality (default 768).
    * Built-in retry for rate limits and transient server errors.
    * Lazy initialisation of the ``google.genai.Client`` — no network
      I/O until the first embed call.

    Usage::

        client = GeminiEmbeddingClient(api_key="...")
        result = await client.embed_document("Some chunk text", title="My Doc")
        query_vec = await client.embed_query("search phrase")
    """

    def __init__(
        self,
        api_key: str,
        *,
        output_dimensionality: int = 768,
        use_manual_prefix: bool = True,
        model_name: str = _DEFAULT_MODEL,
    ) -> None:
        """Initialise the client.

        Args:
            api_key:                Google AI Studio API key.
            output_dimensionality:  Desired embedding dimension (≤ model max).
            use_manual_prefix:      If True, prepend task-type text to the
                                    content instead of relying on the API's
                                    ``task_type`` parameter.
            model_name:             The Gemini embedding model to use.
        """
        self._api_key: str = api_key
        self._dimensions: int = output_dimensionality
        self._use_manual_prefix: bool = use_manual_prefix
        self._model_name: str = model_name
        self._client: Any = None  # Lazy-initialised genai.Client

    # -- Properties ----------------------------------------------------------

    @property
    def model_name(self) -> str:
        """Return the model identifier (e.g. ``"models/text-embedding-004"``)."""
        return self._model_name

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
        """Import and initialise the Google GenAI client on first use."""
        if self._client is not None:
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        except ImportError:
            raise EmbeddingError(
                "google-genai package is not installed. "
                "Run: pip install google-genai>=1.0.0",
            ) from None

    def _prepare_content(self, content: str, task_type: str, title: str | None = None) -> str:
        """Apply manual prefix if enabled.

        Args:
            content:   Raw text to embed.
            task_type: ``"RETRIEVAL_DOCUMENT"`` or ``"RETRIEVAL_QUERY"``.
            title:     Optional document title (only used with document task).

        Returns:
            The (possibly prefixed) content string.
        """
        if not self._use_manual_prefix:
            return content
        if task_type == _TASK_TYPE_QUERY:
            return _QUERY_PREFIX_TEMPLATE.format(query=content)
        # Document task
        title_part = title or "Untitled"
        return _DOCUMENT_PREFIX_TEMPLATE.format(title=title_part, content=content)

    def _build_config(self, task_type: str) -> dict[str, Any]:
        """Build the ``config`` dict passed to ``embed_content``."""
        config: dict[str, Any] = {
            "output_dimensionality": self._dimensions,
        }
        if not self._use_manual_prefix:
            config["task_type"] = task_type
        return config

    def _parse_response(self, response: Any, model: str) -> list[EmbeddingResult]:
        """Convert an SDK response into :class:`EmbeddingResult` objects.

        Args:
            response: The raw response from ``client.models.embed_content``.
            model:    Model name string for the result.

        Returns:
            A list of :class:`EmbeddingResult` objects.
        """
        results: list[EmbeddingResult] = []
        try:
            for emb in response.embeddings:
                values: list[float] = list(emb.values)
                results.append(EmbeddingResult(
                    embedding=values,
                    model=model,
                    dimensions=len(values),
                    token_count=0,  # The genai SDK does not expose token counts yet.
                ))
        except (AttributeError, TypeError, IndexError) as exc:
            raise EmbeddingError(
                f"Failed to parse embedding response: {exc}",
            ) from exc
        return results

    def _do_embed(
        self,
        contents: str | list[str],
        task_type: str,
        title: str | None = None,
    ) -> list[EmbeddingResult]:
        """Synchronous wrapper around the GenAI API call.

        This method is wrapped by the async retry loop.

        Args:
            contents: Single string or list of strings to embed.
            task_type: ``"RETRIEVAL_DOCUMENT"`` or ``"RETRIEVAL_QUERY"``.
            title:     Optional title for document embedding.

        Returns:
            A list of :class:`EmbeddingResult` objects.
        """
        self._lazy_init()

        # Normalise to a list for uniform handling.
        items: list[str] = [contents] if isinstance(contents, str) else contents

        # Apply manual prefix if configured.
        if self._use_manual_prefix:
            if title is not None and task_type == _TASK_TYPE_DOCUMENT:
                items = [self._prepare_content(c, task_type, title) for c in items]
            else:
                items = [self._prepare_content(c, task_type) for c in items]

        config = self._build_config(task_type)

        # The genai SDK accepts a single string or a list.
        api_contents: str | list[str] = items[0] if len(items) == 1 else items

        response = self._client.models.embed_content(
            model=self._model_name,
            contents=api_contents,
            config=config,
        )

        return self._parse_response(response, self._model_name)

    # -- Public API ----------------------------------------------------------

    async def embed_document(
        self,
        content: str,
        title: str | None = None,
    ) -> EmbeddingResult:
        """Embed a single document chunk.

        Args:
            content: Document text to embed.
            title:   Optional document title (used for manual prefix).

        Returns:
            An :class:`EmbeddingResult` with the vector.

        Raises:
            EmbeddingRateLimitError: If the API rate-limits and retries are exhausted.
            EmbeddingError:          On non-retryable errors.
        """
        results = await _retry_with_backoff(
            lambda: asyncio.to_thread(
                self._do_embed, content, _TASK_TYPE_DOCUMENT, title,
            ),
            label="embed_document",
        )
        return results[0]

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
        results = await _retry_with_backoff(
            lambda: asyncio.to_thread(
                self._do_embed, query, _TASK_TYPE_QUERY,
            ),
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
            A list of :class:`EmbeddingResult` in the same order as *contents*.

        Raises:
            EmbeddingBatchError: If the batch operation fails.
            EmbeddingRateLimitError: If the API rate-limits and retries are exhausted.
        """
        if not contents:
            return []

        results = await _retry_with_backoff(
            lambda: asyncio.to_thread(
                self._do_embed, contents, _TASK_TYPE_DOCUMENT,
            ),
            label="embed_batch",
        )

        if len(results) != len(contents):
            raise EmbeddingError(
                f"Batch embedding returned {len(results)} results for "
                f"{len(contents)} inputs.",
            )
        return results
