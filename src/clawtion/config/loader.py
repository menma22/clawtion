"""Configuration loader for clawtion.

Implements the configuration priority chain:
1. Environment variables (CLAWTION_*) -- highest priority
2. Vault-specific config  (<vault>/.clawtion/config.yaml)
3. Global user config      (~/.clawtion/config.yaml)
4. Built-in defaults       (defaults.py)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from clawtion.config.defaults import DEFAULT_CONFIG

_config: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Environment variable mapping
# ---------------------------------------------------------------------------
# Flattened env vars override nested config keys.
# CLAWTION_VAULT           -> config["vault"]["path"]
# CLAWTION_DB_URL          -> config["database"]["url"] (not in defaults, used by connection)
# CLAWTION_GEMINI_API_KEY  -> handled by secrets, not config
# CLAWTION_LOG_LEVEL       -> config["logging"]["level"]
# CLAWTION_CONFIG          -> custom config file path

_ENV_OVERRIDES: dict[str, list[str]] = {
    "CLAWTION_VAULT": ["vault", "path"],
    "CLAWTION_LOG_LEVEL": ["logging", "level"],
}


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty dict on any error."""
    try:
        if path.exists():
            with path.open(encoding="utf-8") as f:
                return dict(yaml.safe_load(f) or {})
    except Exception:
        pass
    return {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    """Override config values from CLAWTION_* environment variables."""
    for env_var, keys in _ENV_OVERRIDES.items():
        value = os.environ.get(env_var)
        if value is not None:
            target = cfg
            for key in keys[:-1]:
                target = target.setdefault(key, {})
            target[keys[-1]] = value
    return cfg


def _resolve_paths(cfg: dict[str, Any]) -> dict[str, Any]:
    """Expand ~ and environment variables in string values that look like paths."""
    resolved = {}
    for key, value in cfg.items():
        if isinstance(value, dict):
            resolved[key] = _resolve_paths(value)
        elif isinstance(value, str) and ("~" in value or "$" in value):
            resolved[key] = os.path.expandvars(os.path.expanduser(value))  # type: ignore[assignment]
        else:
            resolved[key] = value
    return resolved


def get_config() -> dict[str, Any]:
    """Return the merged configuration dictionary.

    The result is cached after the first call unless the CLAWTION_CONFIG
    environment variable has changed.
    """
    global _config
    if _config is not None:
        return _config

    # Start with built-in defaults
    cfg: dict[str, Any] = DEFAULT_CONFIG.copy()

    # Overlay global user config
    global_config_path = Path.home() / ".clawtion" / "config.yaml"
    global_overrides = _load_yaml(global_config_path)
    if global_overrides:
        cfg = _deep_merge(cfg, global_overrides)

    # Overlay vault-specific config if vault path is known
    vault_path_str = os.environ.get("CLAWTION_VAULT") or cfg.get("vault", {}).get("path", "")
    if vault_path_str:
        vault_config_path = (
            Path(os.path.expandvars(os.path.expanduser(vault_path_str)))
            / ".clawtion"
            / "config.yaml"
        )
        vault_overrides = _load_yaml(vault_config_path)
        if vault_overrides:
            cfg = _deep_merge(cfg, vault_overrides)

    # Overlay custom config file if specified
    custom_config = os.environ.get("CLAWTION_CONFIG")
    if custom_config:
        custom_overrides = _load_yaml(Path(custom_config))
        if custom_overrides:
            cfg = _deep_merge(cfg, custom_overrides)

    # Apply environment variable overrides
    cfg = _apply_env_overrides(cfg)

    # Resolve ~ and $VAR in string values
    cfg = _resolve_paths(cfg)

    _config = cfg
    return cfg


def get(key_path: str, default: Any = None) -> Any:
    """Retrieve a config value using a dot-separated key path.

    Args:
        key_path: Dot-separated path, e.g. "vault.path" or "chunking.levels.file.max_tokens".
        default: Default value returned when the key does not exist.

    Returns:
        The config value at the specified path, or *default* if not found.
    """
    cfg = get_config()
    keys = key_path.split(".")
    target: Any = cfg
    for key in keys:
        if isinstance(target, dict) and key in target:
            target = target[key]
        else:
            return default
    return target


def reload_config() -> None:
    """Force config reload on the next call to get_config()."""
    global _config
    _config = None
