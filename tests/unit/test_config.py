"""Unit tests for configuration loader."""

from clawtion.config.defaults import DEFAULT_CONFIG
from clawtion.config.loader import _deep_merge, get_config, reload_config


class TestDefaults:
    def test_vault_section(self) -> None:
        assert "vault" in DEFAULT_CONFIG
        assert "path" in DEFAULT_CONFIG["vault"]

    def test_embedding_section(self) -> None:
        assert "embedding" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["embedding"]["provider"] == "gemini"
        assert DEFAULT_CONFIG["embedding"]["output_dimensionality"] == 768

    def test_chunking_section(self) -> None:
        assert "chunking" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["chunking"]["multi_resolution"]["enabled"] is True  # Phase 2 default

    def test_indexing_section(self) -> None:
        assert "indexing" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["indexing"]["worker"]["max_concurrent_jobs"] == 4

    def test_trash_section(self) -> None:
        assert "trash" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["trash"]["auto_purge_after_days"] == 7

    def test_logging_section(self) -> None:
        assert "logging" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["logging"]["level"] == "INFO"

    def test_service_section(self) -> None:
        assert "service" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["service"]["mode"] == "manual"


class TestDeepMerge:
    def test_shallow_merge(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}}
        result = _deep_merge(base, override)
        assert result["a"] == {"x": 1, "y": 20, "z": 30}
        assert result["b"] == 3

    def test_override_not_dict_does_not_merge(self) -> None:
        base = {"a": {"x": 1}}
        override = {"a": "string_value"}
        result = _deep_merge(base, override)
        assert result["a"] == "string_value"

    def test_empty_override(self) -> None:
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}


class TestConfigLoader:
    def setup_method(self) -> None:
        reload_config()

    def test_get_config_returns_dict(self) -> None:
        config = get_config()
        assert isinstance(config, dict)

    def test_default_values_present(self) -> None:
        config = get_config()
        assert config["vault"]["path"] is not None
        assert config["embedding"]["provider"] == "gemini"

    def test_reload_config(self) -> None:
        config1 = get_config()
        reload_config()
        config2 = get_config()
        assert config1 is not config2  # Different object, same values
