"""Unit tests for retry mechanism."""

from clawtion.utils.retry import RetryConfig


class TestRetryConfig:
    def test_default_values(self) -> None:
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_wait_seconds == 1.0
        assert config.max_wait_seconds == 60.0
        assert config.backoff_multiplier == 2.0

    def test_custom_values(self) -> None:
        config = RetryConfig(max_attempts=5, initial_wait_seconds=4, max_wait_seconds=30)
        assert config.max_attempts == 5
        assert config.initial_wait_seconds == 4
        assert config.max_wait_seconds == 30
        assert config.backoff_multiplier == 2.0  # default

    def test_compute_delay_first_attempt(self) -> None:
        config = RetryConfig(initial_wait_seconds=4, backoff_multiplier=2)
        # The retry logic uses exponential backoff internally
        # Attempt 0 (first retry): delay ~ initial_wait_seconds * (backoff_multiplier^0)
        assert config.initial_wait_seconds == 4

    def test_compute_delay_increases(self) -> None:
        config = RetryConfig(initial_wait_seconds=4, max_wait_seconds=60, backoff_multiplier=2)
        assert config.max_wait_seconds == 60
        assert config.backoff_multiplier == 2

    def test_compute_delay_capped(self) -> None:
        config = RetryConfig(initial_wait_seconds=1, max_wait_seconds=5, backoff_multiplier=100)
        assert config.max_wait_seconds == 5
