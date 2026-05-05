"""clawtion config commands -- view, edit, and manage configuration."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click
import yaml

from clawtion.config.loader import get_config, reload_config
from clawtion.config.secrets import set_secret
from clawtion.i18n.translator import t
from clawtion.utils.async_helpers import async_cmd

_GLOBAL_CONFIG_DIR = Path.home() / ".clawtion"
_GLOBAL_CONFIG_PATH = _GLOBAL_CONFIG_DIR / "config.yaml"


def _ensure_config_dir() -> None:
    """Create global config directory if it does not exist."""
    _GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _get_editor() -> str:
    """Get the user's preferred editor from environment."""
    editor = (
        os.environ.get("CLAWTION_EDITOR")
        or os.environ.get("EDITOR")
        or os.environ.get("VISUAL")
    )
    if editor:
        return editor
    if sys.platform == "win32":
        return "notepad"
    return "nano"


# ---------------------------------------------------------------------------
# Config group
# ---------------------------------------------------------------------------


@click.group(name="config")
def config_cmd() -> None:
    """View and manage clawtion configuration."""
    pass


@config_cmd.command(name="show")
@async_cmd
async def show() -> None:
    """Display the current merged configuration."""
    cfg = get_config()

    click.echo()
    click.echo(click.style(f"  {t('cli.config.current')}", bold=True))
    click.echo()

    _print_config(cfg, indent=2)
    click.echo()


def _print_config(cfg: dict[str, Any], indent: int = 0) -> None:
    """Recursively print config dictionary with indentation."""
    prefix = " " * indent
    for key, value in cfg.items():
        if isinstance(value, dict):
            click.echo(f"{prefix}{click.style(key + ':', bold=True)}")
            _print_config(value, indent + 4)
        elif isinstance(value, bool):
            click.echo(
                f"{prefix}{key}: {click.style(str(value).lower(), fg='cyan')}"
            )
        elif isinstance(value, (int, float)):
            click.echo(
                f"{prefix}{key}: {click.style(str(value), fg='yellow')}"
            )
        elif value is None:
            click.echo(f"{prefix}{key}: null")
        else:
            click.echo(f"{prefix}{key}: {click.style(str(value), fg='green')}")


@config_cmd.command(name="edit")
@async_cmd
async def edit() -> None:
    """Open the global config file in the system editor."""
    _ensure_config_dir()

    # Create default config if not exists
    if not _GLOBAL_CONFIG_PATH.exists():
        from clawtion.config.defaults import DEFAULT_CONFIG
        with _GLOBAL_CONFIG_PATH.open("w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True)

    click.echo(f"  {t('cli.config.editing')}")

    editor = _get_editor()
    try:
        subprocess.run([editor, str(_GLOBAL_CONFIG_PATH)], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        click.echo(click.style(f"  Failed to open editor: {exc}", fg="red"))
        click.echo(f"  Manual edit: {_GLOBAL_CONFIG_PATH}")
        return

    # Reload config after edit
    reload_config()
    click.echo(click.style("  Configuration reloaded.", fg="green"))


@config_cmd.command(name="get")
@click.argument("key")
@async_cmd
async def get(key: str) -> None:
    """Get a specific configuration value by dot-separated key.

    Example: clawtion config get vault.path
    """
    cfg = get_config()
    keys = key.split(".")
    target: Any = cfg
    for k in keys:
        if isinstance(target, dict) and k in target:
            target = target[k]
        else:
            click.echo(click.style(f"  {t('cli.config.key_not_found', key=key)}", fg="red"))
            return

    click.echo(f"  {t('cli.config.getting', key=key, value=str(target))}")


@config_cmd.command(name="set")
@click.argument("key")
@click.argument("value")
@async_cmd
async def set_cmd(key: str, value: str) -> None:
    """Set a configuration value.

    Example: clawtion config set service.mode background

    Only supports simple string values. For complex edits, use
    'clawtion config edit'.
    """
    _ensure_config_dir()

    # Load existing config or start fresh
    existing: dict[str, Any] = {}
    if _GLOBAL_CONFIG_PATH.exists():
        with _GLOBAL_CONFIG_PATH.open(encoding="utf-8") as f:
            existing = dict(yaml.safe_load(f) or {})

    # Update the nested key
    keys = key.split(".")
    target = existing
    for k in keys[:-1]:
        if k not in target:
            target[k] = {}
        target = target[k]
    target[keys[-1]] = value

    # Write back
    with _GLOBAL_CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)

    reload_config()
    click.echo(click.style(f"  {t('cli.config.setting', key=key, value=value)}", fg="green"))


@config_cmd.command(name="set-key")
@click.argument("key_name", type=click.Choice(["gemini", "claude", "openai"]))
@click.option("--value", "-v", default=None, help="API key value (prompts if not given)")
@async_cmd
async def set_key(key_name: str, value: str | None) -> None:
    """Set an API key securely (gemini, claude, or openai)."""
    secret_map = {
        "gemini": "gemini_api_key",
        "claude": "claude_api_key",
        "openai": "openai_api_key",
    }
    secret_key = secret_map[key_name]

    resolved_value = value
    if not resolved_value:
        resolved_value = click.prompt(
            t("cli.config.set_key_prompt", key_name=key_name),
            hide_input=True,
        )

    if resolved_value.strip():
        set_secret(secret_key, resolved_value.strip())
        click.echo(click.style(f"  {t('cli.config.set_key_saved')}", fg="green"))
    else:
        click.echo(click.style("  Invalid key value.", fg="red"))
