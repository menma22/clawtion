"""Retry utilities for clawtion.

Provides configurable retry logic with exponential backoff for async operations
such as embedding API calls, database queries, and file operations.
"""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = get_logger("clawtion.utils.retry")

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behaviour.

    Attributes:
        max_attempts:       Maximum number of attempts (including the first).
        initial_wait_seconds: Base delay for the first retry, in seconds.
        max_wait_seconds:   Cap for the exponential backoff delay.
        backoff_multiplier: Multiplier applied to the delay after each attempt.
        jitter:             If True, adds random jitter 0-25% to each delay.
    """

    max_attempts: int = 3
    initial_wait_seconds: float = 1.0
    max_wait_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True


_DEFAULT_CONFIG = RetryConfig()


def _compute_delay(attempt: int, config: RetryConfig) -> float:
    """Compute the backoff delay for a given attempt number (0-based)."""
    import random

    delay = config.initial_wait_seconds * (config.backoff_multiplier**attempt)
    delay = min(delay, config.max_wait_seconds)

    if config.jitter:
        delay *= 1.0 + random.random() * 0.25  # 0-25% additional jitter

    return delay


async def with_retry(
    func: Callable[..., Coroutine[Any, Any, T]],
    config: RetryConfig | None = None,
    error_types: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """Execute an async callable with exponential-backoff retry.

    Args:
        func:        Async callable to invoke.
        config:      Retry configuration (defaults to 3 attempts, 1s base wait).
        error_types: Tuple of exception types that should trigger a retry.
        **kwargs:    Arguments forwarded to *func*.

    Returns:
        The return value of *func*.

    Raises:
        The last exception raised by *func* once all retries are exhausted.
    """
    cfg = config or _DEFAULT_CONFIG

    for attempt in range(cfg.max_attempts):
        try:
            return await func(**kwargs)
        except error_types as exc:
            is_last = attempt >= cfg.max_attempts - 1

            if is_last:
                logger.error(
                    "retry_exhausted",
                    func=func.__name__,
                    attempt=attempt + 1,
                    max_attempts=cfg.max_attempts,
                    error=str(exc),
                )
                raise

            delay = _compute_delay(attempt, cfg)
            logger.warning(
                "retry_attempt",
                func=func.__name__,
                attempt=attempt + 1,
                max_attempts=cfg.max_attempts,
                delay_seconds=round(delay, 2),
                error=str(exc),
            )
            await asyncio.sleep(delay)

    # Should not reach here, but satisfy the return type
    raise RuntimeError("Unexpected exit from retry loop")  # pragma: no cover


def retryable(
    config: RetryConfig | None = None,
    error_types: tuple[type[Exception], ...] = (Exception,),
) -> Callable[..., Coroutine[Any, Any, T]]:
    """Decorator that wraps an async function with retry logic.

    Usage::

        @retryable(error_types=(ConnectionError, TimeoutError))
        async def embed_content(text: str) -> list[float]:
            ...
    """
    cfg = config or _DEFAULT_CONFIG

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await with_retry(
                lambda: func(*args, **kwargs),  # type: ignore[return-value]
                config=cfg,
                error_types=error_types,
            )

        return wrapper

    return decorator
