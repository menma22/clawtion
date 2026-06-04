"""Token counting utilities for clawtion.

Provides token estimation for various embedding models, with a
character-based fallback for local-only operations.
"""

from __future__ import annotations

import re

# Gemini models typically use approximately 4 characters per token for
# English text and 2 characters per token for Japanese / CJK text.
_CHARS_PER_TOKEN_EN = 4.0
_CHARS_PER_TOKEN_JA = 2.0

# Regex to detect CJK characters (Chinese, Japanese, Korean)
_CJK_RE = re.compile(r"[　-鿿豈-﫿＀-￯]")


def _estimate_token_count(text: str) -> int:
    """Estimate token count using a character-based heuristic.

    Uses a ratio of CJK vs non-CJK characters to weight the token estimate.
    """
    if not text:
        return 0

    cjk_count = len(_CJK_RE.findall(text))
    non_cjk_count = len(text) - cjk_count

    estimated = (non_cjk_count / _CHARS_PER_TOKEN_EN) + (cjk_count / _CHARS_PER_TOKEN_JA)

    return max(1, round(estimated))


def count_tokens(text: str, model: str = "gemini-embedding-2") -> int:
    """Count tokens in the given text.

    Args:
        text:  The input string to count tokens for.
        model: Model identifier. Currently supports:
               - "gemini-embedding-2" / "gemini-embedding-2-preview"
               - Any other value triggers the character-based fallback.

    Returns:
        Estimated token count (always >= 1 for non-empty text).

    Note:
        For Gemini models, we currently use a character-based heuristic.
        A future enhancement can integrate the actual
        ``google-genai`` SDK tokenizer when available for the
        ``gemini-embedding-2`` model family.
    """
    if not text:
        return 0

    # For Gemini embedding models, try the SDK token counting API.
    if model.startswith("gemini"):
        try:
            return _gemini_count_tokens(text)
        except Exception:
            pass

    # Fallback: character-based estimation
    return _estimate_token_count(text)


def _gemini_count_tokens(text: str) -> int:
    """Count tokens using the Gemini SDK, if available.

    Raises:
        ImportError:  if google.genai is not installed.
        RuntimeError: if the SDK call fails.
    """

    # google-genai SDK does not expose a standalone tokenizer for
    # embedding models as of the current version. We fall back to
    # the heuristic and document this limitation.
    raise RuntimeError("Gemini SDK token count not available for embedding models")
