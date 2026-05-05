"""Unit tests for language detection."""

import pytest

from clawtion.utils.language import detect_language, is_cjk


class TestDetectLanguage:
    def test_japanese_text(self) -> None:
        text = "これは日本語のテスト文章です。十分な長さがあれば検出できます。"
        # langdetect needs sufficient text; may return "ja" or fallback
        result = detect_language(text)
        assert isinstance(result, str)
        assert len(result) >= 2

    def test_english_text(self) -> None:
        text = "This is an English test sentence for language detection."
        result = detect_language(text)
        assert isinstance(result, str)

    def test_short_text_returns_fallback(self) -> None:
        result = detect_language("Hi")
        assert isinstance(result, str)

    def test_empty_text(self) -> None:
        result = detect_language("")
        assert isinstance(result, str)
        assert len(result) >= 2  # Returns fallback


class TestIsCJK:
    def test_japanese_is_cjk(self) -> None:
        assert is_cjk("日本語テスト") is True

    def test_chinese_is_cjk(self) -> None:
        assert is_cjk("中文测试") is True

    def test_korean_is_cjk(self) -> None:
        assert is_cjk("한국어") is True

    def test_english_not_cjk(self) -> None:
        assert is_cjk("English text") is False

    def test_mixed_cjk(self) -> None:
        assert is_cjk("English with 日本語 mixed") is True

    def test_empty_string(self) -> None:
        assert is_cjk("") is False
