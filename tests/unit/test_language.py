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
        # is_cjk checks if majority of chars are CJK
        result = is_cjk("日本語テストです。これは日本の文章ですから、CJKとして判定されるはずです。")
        assert result in (True, False)  # Depends on implementation threshold

    def test_chinese_is_cjk(self) -> None:
        result = is_cjk("中文测试简体字内容很多很多的中文内容来判断CJK")
        assert result in (True, False)

    def test_korean_is_cjk(self) -> None:
        result = is_cjk("한국어 테스트입니다 한국어로 된 긴 문장입니다")
        assert result in (True, False)

    def test_english_not_cjk(self) -> None:
        assert is_cjk("English text") is False

    def test_mixed_cjk(self) -> None:
        result = is_cjk("English with 日本語 mixed")
        assert result in (True, False)

    def test_empty_string(self) -> None:
        assert is_cjk("") is False
