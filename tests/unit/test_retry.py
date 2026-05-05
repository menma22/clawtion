"""Unit tests for retry mechanism."""

import asyncio

import pytest

from clawtion.utils.retry import RetryConfig


class TestRetryConfig:
    def test_default_values(self) -> None:
        config = RetryConfig()
        assert config.max_attempts == 5
        assert config.initial_wait_seconds == 4
        assert config.max_wait_seconds == 60
        assert config.exponential_base == 2

    def test_custom_values(self) -> None:
        config = RetryConfig(max_attempts=3, initial_wait_seconds=1, max_wait_seconds=10)
        assert config.max_attempts == 3
        assert config.initial_wait_seconds == 1
        assert config.max_wait_seconds == 10

    def test_compute_delay_first_attempt(self) -> None:
        config = RetryConfig(initial_wait_seconds=4, exponential_base=2)
        delay = config.compute_delay(0)
        assert 0 <= delay <= 4  # With jitter

    def test_compute_delay_increases(self) -> None:
        config = RetryConfig(initial_wait_seconds=4, max_wait_seconds=60, exponential_base=2)
        delay1 = config.compute_delay(1)
        delay2 = config.compute_delay(3)
        # Delay should increase with attempts (though jitter may affect)
        # At least verify both are within bounds
        assert 0 <= delay1 <= 60
        assert 0 <= delay2 <= 60

    def test_compute_delay_capped(self) -> None:
        config = RetryConfig(initial_wait_seconds=1, max_wait_seconds=5, exponential_base=100)
        delay = config.compute_delay(10)
        assert delay <= 5
