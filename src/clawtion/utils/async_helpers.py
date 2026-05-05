"""Async helpers for synchronous CLI entry points.

Provides ``async_cmd``, a decorator that wraps async click command
callbacks so they can be used with Click's synchronous API.
"""

from __future__ import annotations

import asyncio
import functools
import sys
from typing import Any

import click

from clawtion.i18n.translator import t

# ---------------------------------------------------------------------------
# Global verbose flag
# ---------------------------------------------------------------------------

_VERBOSE = False


def set_verbose(val: bool) -> None:
    """Set global verbose flag."""
    global _VERBOSE
    _VERBOSE = val


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _VERBOSE


# ---------------------------------------------------------------------------
# Async click helper
# ---------------------------------------------------------------------------


def async_cmd(
    async_func: Any,
) -> Any:
    """Decorator that wraps an async click command callback.

    Usage::

        @cli.command()
        @click.pass_context
        @async_cmd
        async def my_command(ctx, ...):
            ...
    """

    def wrapper(*args: Any, **kwargs: Any) -> None:
        try:
            asyncio.run(async_func(*args, **kwargs))
        except KeyboardInterrupt:
            click.echo()
            click.echo(t("cli.general.cancel"))
            sys.exit(130)
        except Exception as exc:
            if is_verbose():
                import traceback

                click.echo(
                    click.style(t("cli.general.error", message=str(exc)), fg="red", bold=True),
                    err=True,
                )
                click.echo(traceback.format_exc(), err=True)
            else:
                click.echo(
                    click.style(t("cli.general.error", message=str(exc)), fg="red", bold=True),
                    err=True,
                )
                click.echo(
                    click.style("Use --verbose for details.", fg="yellow"),
                    err=True,
                )
            sys.exit(1)

    return functools.wraps(async_func)(wrapper)
