"""Unit tests for token counting."""

import pytest

from clawtion.utils.tokens import count_tokens


class TestCountTokens:
    def test_empty_string(self) -> None:
        result = count_tokens("")
        assert result == 0

    def test_english_text(self) -> None:
        text = "This is a test sentence for token counting."
        result = count_tokens(text)
        assert result > 0
        assert result < 50  # Should be reasonable

    def test_japanese_text(self) -> None:
        text = "これは日本語のテストです。トークン数をカウントします。"
        result = count_tokens(text)
        assert result > 0

    def test_very_long_text(self) -> None:
        text = "word " * 1000
        result = count_tokens(text)
        assert result >= 500  # Approximate

    def test_single_word(self) -> None:
        result = count_tokens("Hello")
        assert 1 <= result <= 3  # ~1-2 tokens typically

    def test_code_text(self) -> None:
        text = "def function():\n    return True"
        result = count_tokens(text)
        assert result > 0


class TestTokenCountComparison:
    def test_longer_text_has_more_tokens(self) -> None:
        short = "Short."
        long = "This is a much longer piece of text with many more tokens."
        assert count_tokens(long) > count_tokens(short)

    def test_similar_length_similar_tokens(self) -> None:
        text1 = "Hello world, this is a test."
        text2 = "Token counting for similar texts."
        t1 = count_tokens(text1)
        t2 = count_tokens(text2)
        ratio = max(t1, t2) / max(min(t1, t2), 1)
        assert ratio < 5  # Should not be wildly different
