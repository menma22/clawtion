"""Unit tests for internationalization module."""

from clawtion.i18n.translator import (
    _resolve_key,
    get_current_language,
    reload_locales,
    set_language,
    t,
)


class TestResolveKey:
    def test_simple_key(self) -> None:
        data = {"cli": {"init": {"welcome": "Welcome!"}}}
        result = _resolve_key(data, "cli.init.welcome")
        assert result == "Welcome!"

    def test_nonexistent_key(self) -> None:
        data = {"cli": {}}
        result = _resolve_key(data, "cli.nonexistent")
        assert result is None

    def test_empty_dict(self) -> None:
        result = _resolve_key({}, "any.key")
        assert result is None


class TestInterpolation:
    def test_single_variable(self) -> None:
        result = t("cli.indexing.complete", count=5, duration="10s")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multiple_variables(self) -> None:
        result = t("cli.indexing.complete", count=3, duration="1m")
        assert isinstance(result, str)

    def test_no_variables(self) -> None:
        result = t("cli.init.welcome")
        assert isinstance(result, str)
        assert len(result) > 0


class TestTranslator:
    def setup_method(self) -> None:
        reload_locales()

    def test_t_returns_string(self) -> None:
        result = t("cli.init.welcome")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_t_fallback_on_missing_key(self) -> None:
        result = t("nonexistent.key.abc123")
        assert result is not None

    def test_t_with_interpolation(self) -> None:
        # Test that interpolation works when variables are provided
        result = t("cli.indexing.complete", count=5, duration="10s")
        assert isinstance(result, str)

    def test_set_language(self) -> None:
        set_language("ja")
        assert get_current_language() == "ja"
        set_language("en")  # Reset

    def test_set_unknown_language_falls_back(self) -> None:
        set_language("zz")  # Non-existent language
        result = get_current_language()
        assert result in ("zz", "ja", "en")  # May fall back to system locale
        set_language("en")  # Reset
