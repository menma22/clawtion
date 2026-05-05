"""Batch embedding support for clawtion.

Provides the ``BatchEmbeddingClient`` that delegates to a regular
``EmbeddingClient`` for small batches and can be extended to use
Gemini's asynchronous Batch API for large-scale jobs.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from clawtion.core.embedding.client import (
    EmbeddingBatchError,
    EmbeddingError,
    EmbeddingRateLimitError,
    EmbeddingResult,
)

if TYPE_CHECKING:
    from clawtion.core.embedding.gemini import GeminiEmbeddingClient

logger = logging.getLogger(__name__)

# Maximum number of texts that can be embedded in a single API call.
# Gemini's embed_content supports multiple contents, but very large
# lists may exceed payload limits.  We conservatively split at this size.
_DEFAULT_BATCH_SIZE = 100


@dataclass
class BatchConfig:
    """Configuration for the batch embedding client.

    Attributes:
        threshold:      Number of chunks above which the client triggers
                        batch-mode processing (rather than single-shot).
                        Default: 100.
        max_wait_hours: Maximum time to wait for a large batch to complete.
                        Currently reserved for future Batch API integration.
                        Default: 24.
        batch_size:     Maximum number of texts to embed per API call.
                        Larger lists are split into sub-batches.
                        Default: 100.
        max_concurrency: Maximum number of concurrent API calls when
                         processing sub-batches.
                         Default: 5.
    """
    threshold: int = 100
    max_wait_hours: int = 24
    batch_size: int = _DEFAULT_BATCH_SIZE
    max_concurrency: int = 5


class BatchEmbeddingClient:
    """Embedding client that splits large workloads into manageable batches.

    For inputs smaller than ``config.threshold``, the batch client simply
    delegates to the wrapped ``GeminiEmbeddingClient.embed_batch``.

    For larger inputs, it splits the texts into sub-batches, processes
    them concurrently (subject to ``config.max_concurrency``), and collects
    the results in order.

    Future enhancement: Switch to Gemini's asynchronous Batch API for very
    large workloads (``config.threshold`` ≥ 1000+).  The current
    implementation always uses the synchronous single-shot API.

    Usage::

        gemini = GeminiEmbeddingClient(api_key="...")
        batching = BatchEmbeddingClient(gemini, BatchConfig(threshold=50))
        results = await batching.embed_batch_if_needed(texts)
    """

    def __init__(
        self,
        gemini_client: GeminiEmbeddingClient,
        config: BatchConfig | None = None,
    ) -> None:
        """Initialise the batch embedding client.

        Args:
            gemini_client: An initialised :class:`GeminiEmbeddingClient`
                           instance.
            config:        Optional :class:`BatchConfig`.  Defaults to a
                           standard configuration.
        """
        self._client: GeminiEmbeddingClient = gemini_client
        self._config: BatchConfig = config or BatchConfig()

    # -- Properties ----------------------------------------------------------

    @property
    def client(self) -> GeminiEmbeddingClient:
        """Return the wrapped :class:`GeminiEmbeddingClient`."""
        return self._client

    @property
    def config(self) -> BatchConfig:
        """Return the current batch configuration."""
        return self._config

    # -- Public API ----------------------------------------------------------

    async def embed_batch_if_needed(
        self,
        contents: list[str],
    ) -> list[EmbeddingResult]:
        """Embed *contents*, using batch splitting for large lists.

        The strategy is:

        * Empty list → empty list.
        * ``len(contents) <= config.threshold`` → delegate directly to
          the wrapped client's ``embed_batch``.
        * ``len(contents) > config.threshold`` → split into sub-batches of
          ``config.batch_size`` and run them concurrently (up to
          ``config.max_concurrency``).

        Args:
            contents: Text strings to embed.

        Returns:
            A list of :class:`EmbeddingResult` in the same order as
            *contents*.

        Raises:
            EmbeddingBatchError: If the overall operation cannot complete.
            EmbeddingRateLimitError: If the API rate-limits and retries are
                exhausted.
        """
        if not contents:
            return []

        if len(contents) <= self._config.threshold:
            # Small batch — delegate directly.
            return await self._client.embed_batch(contents)

        # Large batch — split and run concurrently.
        logger.info(
            "Large batch requested: %d texts (threshold=%d). "
            "Splitting into sub-batches of %d.",
            len(contents),
            self._config.threshold,
            self._config.batch_size,
        )

        batches: list[list[str]] = self._split_batches(contents)
        return await self._process_batches_concurrently(batches)

    async def embed_single(self, content: str, title: str | None = None) -> EmbeddingResult:
        """Convenience method to embed a single text through the batch client.

        Delegates to the wrapped client's ``embed_document``.

        Args:
            content: Text to embed.
            title:   Optional document title.

        Returns:
            An :class:`EmbeddingResult`.
        """
        return await self._client.embed_document(content, title=title)

    # -- Internal helpers ----------------------------------------------------

    def _split_batches(self, contents: list[str]) -> list[list[str]]:
        """Split *contents* into sub-batches of ``config.batch_size``."""
        batch_size = self._config.batch_size
        return [contents[i:i + batch_size] for i in range(0, len(contents), batch_size)]

    async def _process_batches_concurrently(
        self,
        batches: list[list[str]],
    ) -> list[EmbeddingResult]:
        """Process sub-batches concurrently with a semaphore.

        Args:
            batches: List of text sub-batches.

        Returns:
            Flattened list of :class:`EmbeddingResult` objects, preserving
            the original order.

        Raises:
            EmbeddingBatchError: If any sub-batch fails and cannot be retried.
        """
        semaphore = asyncio.Semaphore(self._config.max_concurrency)

        async def _process_one(batch: list[str]) -> list[EmbeddingResult]:
            async with semaphore:
                try:
                    return await self._client.embed_batch(batch)
                except (EmbeddingError, EmbeddingRateLimitError) as exc:
                    raise EmbeddingBatchError(
                        f"Sub-batch of {len(batch)} texts failed: {exc}",
                    ) from exc

        tasks = [_process_one(batch) for batch in batches]
        results: list[list[EmbeddingResult]] = await asyncio.gather(*tasks)

        # Flatten, preserving sub-batch order.
        flat: list[EmbeddingResult] = []
        for sub in results:
            flat.extend(sub)

        return flat

    # -- Statistics ----------------------------------------------------------

    def estimate_batch_plan(self, total_count: int) -> dict[str, int]:
        """Return a plan summary without actually embedding anything.

        Useful for logging or progress estimation before starting the work.

        Args:
            total_count: Number of texts that would be embedded.

        Returns:
            A dict with keys ``total``, ``sub_batches``, ``batch_size``,
            and ``would_use_batch_api``.
        """
        would_batch = total_count > self._config.threshold
        if would_batch:
            batches = self._split_batches([""] * total_count)
            num_batches = len(batches)
        else:
            num_batches = 1

        return {
            "total": total_count,
            "sub_batches": num_batches,
            "batch_size": self._config.batch_size,
            "would_use_batch_api": would_batch and total_count >= 1000,
        }
