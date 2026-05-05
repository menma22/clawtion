"""Language detection utilities for clawtion.

Uses the *langdetect* library to identify the language of text content,
which drives sentence-boundary detection (pysbd) and token estimation.
"""

from __future__ import annotations

from langdetect import DetectorFactory, LangDetectException, detect

# Make langdetect results deterministic
DetectorFactory.seed = 0

FALLBACK_LANGUAGE = "ja"

# Languages that pysbd supports natively
_SUPPORTED_LANGUAGES = frozenset({
    "ja", "en", "zh", "ko", "fr", "de", "es", "pt", "it", "nl",
    "ru", "ar", "hi", "th", "vi", "tr",
})


def detect_language(text: str, fallback: str | None = None) -> str:
    """Detect the language of the provided text.

    Args:
        text:     The input text to analyse.
        fallback: Language code returned when detection fails or the
                  detected language is not supported. Defaults to the
                  module-level FALLBACK_LANGUAGE ("ja").

    Returns:
        An ISO 639-1 two-letter language code (e.g. "en", "ja").

    Note:
        The detection is most reliable on text longer than 50 characters.
        Very short text will likely fall back to the default language.
    """
    resolved_fallback = fallback or FALLBACK_LANGUAGE

    if not text or len(text.strip()) < 10:
        return resolved_fallback

    try:
        detected = detect(text)
        if detected in _SUPPORTED_LANGUAGES:
            return detected
        # If the detected language is not supported by pysbd, fall back.
        return resolved_fallback
    except LangDetectException:
        return resolved_fallback


def is_cjk(text: str) -> bool:
    """Check whether the text is predominantly CJK (Chinese / Japanese / Korean).

    Args:
        text: Input text to evaluate.

    Returns:
        True if the majority of characters are in CJK Unicode blocks.
    """
    import unicodedata

    if not text:
        return False

    cjk_count = sum(
        1 for ch in text if "CJK" in unicodedata.name(ch, "")
    )
    return cjk_count / max(len(text), 1) > 0.5
