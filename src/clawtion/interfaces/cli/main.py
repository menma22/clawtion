"""clawtion CLI entry point.

All subcommand groups are registered here.
Usage::

    clawtion [OPTIONS] COMMAND [ARGS]...

"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import click

from clawtion.i18n.translator import t
from clawtion.interfaces.cli.config import config_cmd
from clawtion.interfaces.cli.doctor import doctor
from clawtion.interfaces.cli.index import index

# ---------------------------------------------------------------------------
# Import subcommand groups (lazy when possible to avoid circular deps)
# ---------------------------------------------------------------------------
from clawtion.interfaces.cli.init import init
from clawtion.interfaces.cli.note import note
from clawtion.interfaces.cli.search import search
from clawtion.interfaces.cli.service import service
from clawtion.interfaces.cli.trash import trash

# ---------------------------------------------------------------------------
# Global options
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
# Async click helpers
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

    import functools
    return functools.wraps(async_func)(wrapper)


# ---------------------------------------------------------------------------
# Main CLI group
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="clawtion")
@click.option("--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """clawtion - AI knowledge base + note application.

    Manage your local knowledge base with AI-powered search, indexing,
    and note-taking capabilities.
    """
    set_verbose(verbose)

    if ctx.invoked_subcommand is None:
        click.echo(
            click.style(
                r"""
   ___ _    ___    _   _ ___ _   _  ___
  / __| |  / _ \  | | | |_ _| \ | |/ _ \
 | (__| | | (_) | | |_| || ||  \| | (_) |
  \___|_|  \___/   \___/|___|_|\_|\___/
                                                """,
                fg="cyan",
            )
        )
        click.echo(click.style(t("cli.general.help_header"), bold=True))
        click.echo()
        click.echo(ctx.get_help())
        click.echo()
        click.echo(
            click.style(t("cli.general.version", version="0.1.0"), fg="bright_black")
        )


# ---------------------------------------------------------------------------
# Register all subcommand groups
# ---------------------------------------------------------------------------

main.add_command(init)
main.add_command(service)
main.add_command(index)
main.add_command(search)
main.add_command(note)
main.add_command(trash)
main.add_command(doctor)
main.add_command(config_cmd)


# ---------------------------------------------------------------------------
# mcp-serve and api-serve are registered here but defined in their
# respective interface modules
# ---------------------------------------------------------------------------


@main.command(name="mcp-serve")
@click.option("--port", default=None, type=int, help="MCP server port (stdio only)")
@async_cmd
async def mcp_serve(port: int | None) -> None:
    """Start the MCP server for Claude Code integration."""
    from clawtion.interfaces.mcp.server import run_mcp_server
    await run_mcp_server()


@main.command(name="api-serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind address")
@click.option("--port", default=8000, type=int, show_default=True, help="Port")
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for development",
)
@async_cmd
async def api_serve(host: str, port: int, reload: bool) -> None:
    """Start the REST API server."""
    try:
        import uvicorn
        await uvicorn.run(
            "clawtion.interfaces.api.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )
    except ImportError:
        click.echo(
            click.style(
                "uvicorn is required. Install with: pip install clawtion[dev]",
                fg="red",
            ),
            err=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
