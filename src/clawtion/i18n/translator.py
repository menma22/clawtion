"""Translation engine for clawtion.

Provides a ``t()`` function that resolves dot-separated keys against
JSON translation files. Supports ``{variable}`` interpolation and
automatic language detection from the environment.
"""

from __future__ import annotations

import json
import locale
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_translations: dict[str, dict[str, Any]] = {}
_current_lang: str = "en"

_LOCALE_DIR = Path(__file__).resolve().parent / "locales"

# Override path for user-customised locale files
_USER_LOCALE_DIR = Path.home() / ".clawtion" / "i18n"

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def _detect_language() -> str:
    """Detect the user's preferred language.

    Priority:
    1. ``CLAWTION_LANG`` or ``LANG`` / ``LC_ALL`` environment variable
    2. OS locale setting (via Python's ``locale`` module)
    3. Default to ``"en"``
    """
    env_lang = (
        os.environ.get("CLAWTION_LANG")
        or os.environ.get("LANG")
        or os.environ.get("LC_ALL")
    )
    if env_lang:
        code = env_lang.split(".")[0].split("_")[0].lower()
        if code:
            return code
    try:
        sys_lang, _ = locale.getdefaultlocale()
        if sys_lang:
            code = sys_lang.split("_")[0].lower()
            if code:
                return code
    except Exception:
        pass
    return "en"


# ---------------------------------------------------------------------------
# Translation data loader
# ---------------------------------------------------------------------------


def _load_locale(lang: str) -> dict[str, Any]:
    """Load translation data for the given language code.

    Checks user-customised directories first, then the bundled locales.
    """
    # 1. User-customised locale
    user_file = _USER_LOCALE_DIR / f"{lang}.json"
    if user_file.exists():
        try:
            with user_file.open(encoding="utf-8") as f:
                return dict(json.load(f))
        except Exception:
            pass

    # 2. Bundled locale
    bundled_file = _LOCALE_DIR / f"{lang}.json"
    if bundled_file.exists():
        try:
            with bundled_file.open(encoding="utf-8") as f:
                return dict(json.load(f))
        except Exception:
            pass

    return {}


def _ensure_locales_loaded(lang: str | None = None) -> None:
    """Load translation data if not already cached."""
    global _translations, _current_lang

    if lang is None:
        lang = _detect_language()

    if lang in _translations:
        return

    data = _load_locale(lang)
    if not data and lang != "en":
        # Fall back to English if requested locale is unavailable
        data = _load_locale("en")
        lang = "en"

    _translations[lang] = data
    _current_lang = lang


# ---------------------------------------------------------------------------
# Key resolution
# ---------------------------------------------------------------------------


def _resolve_key(data: dict[str, Any], key: str) -> str | None:
    """Walk a dot-separated key through a nested dict.

    Example: ``_resolve_key(data, "cli.init.welcome")`` returns the string
    at ``data["cli"]["init"]["welcome"]`` or ``None``.
    """
    parts = key.split(".")
    target: Any = data
    for part in parts:
        if isinstance(target, dict) and part in target:
            target = target[part]
        else:
            return None
    if isinstance(target, str):
        return target
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def set_language(lang: str) -> None:
    """Override the current language for the session.

    Args:
        lang: ISO 639-1 language code (e.g. ``"ja"``, ``"en"``).
    """
    global _translations
    _translations.pop(lang, None)  # Force reload on next access
    _ensure_locales_loaded(lang)


def get_current_language() -> str:
    """Return the active language code."""
    _ensure_locales_loaded()
    return _current_lang


def t(key: str, **kwargs: Any) -> str:
    """Translate a key using the current locale.

    Args:
        key:  Dot-separated translation key (e.g. ``"cli.init.welcome"``).
        **kwargs: Variables to interpolate into the translated string
                  using ``{variable}`` placeholders.

    Returns:
        The translated string with variables substituted. If the key is
        not found, returns the key itself as a fallback.

    Examples::

        t("cli.init.welcome")                          # "Welcome to clawtion!"
        t("cli.init.vault_default", path="~/Docs")     # "Default: ~/Docs"
    """
    _ensure_locales_loaded()

    # Try current language
    template = _resolve_key(_translations.get(_current_lang, {}), key)

    # Fall back to English
    if template is None and _current_lang != "en":
        en_data = _translations.get("en", _load_locale("en"))
        template = _resolve_key(en_data, key)

    if template is None:
        return key

    # Variable interpolation
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            pass

    return template


def reload_locales() -> None:
    """Clear the locale cache, forcing a reload on the next ``t()`` call."""
    global _translations
    _translations = {}
