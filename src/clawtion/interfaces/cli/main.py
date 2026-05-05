"""clawtion CLI entry point.

All subcommand groups are registered here.
Usage::

    clawtion [OPTIONS] COMMAND [ARGS]...

"""

from __future__ import annotations

import sys

import click

from clawtion.i18n.translator import t
from clawtion.interfaces.cli.config import config_cmd
from clawtion.interfaces.cli.doctor import doctor
from clawtion.interfaces.cli.git_cmd import git as git_group
from clawtion.interfaces.cli.index import index

# ---------------------------------------------------------------------------
# Import subcommand groups (lazy when possible to avoid circular deps)
# ---------------------------------------------------------------------------
from clawtion.interfaces.cli.init import init
from clawtion.interfaces.cli.namespace import namespace as namespace_group
from clawtion.interfaces.cli.note import note
from clawtion.interfaces.cli.search import search
from clawtion.interfaces.cli.service import service
from clawtion.interfaces.cli.trash import trash
from clawtion.utils.async_helpers import async_cmd, set_verbose

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
main.add_command(namespace_group)
main.add_command(git_group)


# ---------------------------------------------------------------------------
# logs command (simple log viewer)
# ---------------------------------------------------------------------------


@main.command(name="logs")
@click.option("--tail", default=50, type=int, help="Number of lines to show")
@click.option("--level", default=None, help="Filter by level (DEBUG, INFO, WARN, ERROR)")
@click.option("--file", default=None, help="Log file path (default: ~/.clawtion/logs/clawtion.log)")
def logs_cmd(tail: int, level: str | None, file: str | None) -> None:
    """View clawtion logs."""
    from pathlib import Path

    log_path = Path(file) if file else Path.home() / ".clawtion" / "logs" / "clawtion.log"

    if not log_path.exists():
        click.echo(click.style(f"  Log file not found: {log_path}", fg="yellow"))
        click.echo("  Run 'clawtion start' to begin logging.")
        return

    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    if level:
        level_upper = level.upper()
        lines = [ln for ln in lines if level_upper in ln]

    for line in lines[-tail:]:
        # Color-code by level
        if "ERROR" in line or "error" in line:
            click.echo(click.style(line, fg="red"))
        elif "WARN" in line or "warn" in line:
            click.echo(click.style(line, fg="yellow"))
        else:
            click.echo(line)


# ---------------------------------------------------------------------------
# mcp-serve and api-serve
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
