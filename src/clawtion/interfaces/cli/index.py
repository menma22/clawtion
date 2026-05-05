"""clawtion index commands -- indexing and queue management."""

from __future__ import annotations

import os
from typing import Any

import click

from clawtion.config.loader import get_config
from clawtion.config.secrets import get_secret
from clawtion.i18n.translator import t
from clawtion.utils.async_helpers import async_cmd


async def _get_services() -> dict[str, Any]:
    """Create core service instances."""
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.gemini import GeminiEmbeddingClient
    from clawtion.core.indexing.queue import QueueManager
    from clawtion.core.indexing.service import IndexingService

    cfg = get_config()
    db_url = os.environ.get("CLAWTION_DB_URL", "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion")
    vault_path = os.path.expandvars(os.path.expanduser(cfg.get("vault", {}).get("path", "~/Documents/clawtion-vault")))
    api_key = get_secret("gemini_api_key") or ""

    db = DatabaseManager(db_url)
    await db.connect()

    embedder = GeminiEmbeddingClient(
        api_key=api_key,
        output_dimensionality=cfg.get("embedding", {}).get("output_dimensionality", 768),
        use_manual_prefix=cfg.get("embedding", {}).get("use_manual_prefix_fallback", True),
    )

    queue = QueueManager(db)

    indexing_service = IndexingService(
        db=db,
        embedder=embedder,
        queue=queue,
        vault_path=vault_path,
        config=cfg,
    )

    return {
        "db": db,
        "embedder": embedder,
        "indexing_service": indexing_service,
        "queue": queue,
        "vault_path": vault_path,
        "cfg": cfg,
    }


# ---------------------------------------------------------------------------
# Index group
# ---------------------------------------------------------------------------


@click.group(name="index")
def index() -> None:
    """Index documents and manage the indexing queue."""
    pass


@index.command(name="index")
@click.argument("path", required=False, default=None)
@click.option("--batch", is_flag=True, help="Use batch API for embedding")
@click.option("--force", is_flag=True, help="Force re-index even if unchanged")
@async_cmd
async def index_cmd(path: str | None, batch: bool, force: bool) -> None:
    """Index a specific file or folder. If no path is given, indexes the entire vault."""
    services = await _get_services()
    try:
        indexing_service = services["indexing_service"]
        vault_path = services["vault_path"]

        target = path if path else vault_path
        resolved = os.path.expandvars(os.path.expanduser(target))

        if not os.path.exists(resolved):
            click.echo(click.style(t("cli.indexing.file_not_found", path=resolved), fg="red"))
            return

        if os.path.isfile(resolved):
            click.echo(f"  {t('cli.indexing.indexing_file', filename=resolved)}")
            with click.progressbar(length=1, label="Indexing") as bar:  # type: ignore[var-annotated]
                await indexing_service.index_file(resolved, force=force)
                bar.update(1)
            click.echo(click.style(t("cli.general.success"), fg="green"))
        else:
            click.echo(f"  {t('cli.indexing.scanning_folder', path=resolved)}")
            count = await indexing_service.index_folder(resolved, force=force)
            click.echo(click.style(f"  {t('cli.indexing.complete', count=count, duration='')}", fg="green"))
    finally:
        await services["db"].disconnect()


@index.command(name="now")
@async_cmd
async def index_now() -> None:
    """Process all items currently in the indexing queue."""
    services = await _get_services()
    try:
        queue = services["queue"]
        indexing_service = services["indexing_service"]

        stats = await queue.get_stats()
        pending = stats.get("pending", 0)
        if pending == 0:
            click.echo(f"  {t('cli.indexing.nothing_to_index')}")
            return

        click.echo(f"  Processing {pending} queued items...")
        with click.progressbar(length=pending, label="Queue") as bar:  # type: ignore[var-annotated]
            def progress_callback() -> None:
                bar.update(1)
            processed = await indexing_service.process_queue(callback=progress_callback)

        click.echo(click.style(f"  {t('cli.indexing.complete', count=processed, duration='')}", fg="green"))
    finally:
        await services["db"].disconnect()


@index.command(name="reindex")
@click.confirmation_option(prompt="This will re-index ALL documents. Continue?")
@async_cmd
async def reindex() -> None:
    """Re-index all documents in the vault from scratch."""
    services = await _get_services()
    try:
        indexing_service = services["indexing_service"]
        vault_path = services["vault_path"]

        click.echo(f"  {t('cli.indexing.reindex_confirm', count='all')}")
        await indexing_service.reindex_all(vault_path)

        click.echo(click.style(f"  {t('cli.indexing.reindex_started')}", fg="green"))
    finally:
        await services["db"].disconnect()


# ---------------------------------------------------------------------------
# Queue management
# ---------------------------------------------------------------------------


@index.group(name="queue")
def queue() -> None:
    """Manage the indexing queue."""
    pass


@queue.command(name="status")
@async_cmd
async def queue_status() -> None:
    """Show indexing queue status."""
    services = await _get_services()
    try:
        queue = services["queue"]

        stats = await queue.get_stats()
        pending = stats.get("pending", 0)
        processing = stats.get("processing", 0)
        completed = stats.get("completed", 0)
        failed = stats.get("failed", 0)

        click.echo()
        click.echo(click.style(f"  {t('cli.queue.status_header')}", bold=True))
        click.echo(f"    {t('cli.queue.pending', count=pending)}")
        click.echo(f"    {t('cli.queue.processing', count=processing)}")
        click.echo(f"    {t('cli.queue.completed', count=completed)}")
        click.echo(f"    {t('cli.queue.failed', count=failed)}")
        click.echo()
    finally:
        await services["db"].disconnect()


@queue.command(name="list")
@click.option("--status", default="pending", help="Filter by status: pending, processing, failed")
@async_cmd
async def queue_list(status: str) -> None:
    """List items in the indexing queue."""
    services = await _get_services()
    try:
        queue = services["queue"]
        if status == "failed":
            items = await queue.get_failed()
        else:
            items = await queue.get_pending()

        if not items:
            click.echo(f"  {t('cli.queue.list_empty')}")
            return

        click.echo()
        click.echo(click.style(f"  {t('cli.queue.list_header')}", bold=True))
        for item in items:
            click.echo(
                f"    [{item.get('queue_id', '?')[:8]}] {item.get('file_path', '?')}"
                f"  op={item.get('operation', '?')}  status={item.get('status', '?')}"
            )
        click.echo()
    finally:
        await services["db"].disconnect()


@queue.command(name="clear")
@click.option("--all", "clear_all", is_flag=True, help="Clear all items including completed")
@click.option("--failed", is_flag=True, help="Clear only failed items")
@async_cmd
async def queue_clear(clear_all: bool, failed: bool) -> None:
    """Clear items from the indexing queue."""
    services = await _get_services()
    try:
        queue = services["queue"]
        if failed:
            count = await queue.clear_failed()
        else:
            count = await queue.clear_failed()  # Default: clear failed items

        click.echo(click.style(
            f"  {t('cli.queue.cleared_failed', count=count)}",
            fg="green",
        ))
    finally:
        await services["db"].disconnect()


@queue.command(name="retry")
@click.option("--all", "retry_all", is_flag=True, help="Retry all failed items")
@async_cmd
async def queue_retry(retry_all: bool) -> None:
    """Retry failed indexing queue items."""
    services = await _get_services()
    try:
        queue = services["queue"]
        if retry_all:
            count = await queue.retry_all_failed()
            click.echo(click.style(f"  {t('cli.queue.cleared_failed', count=count)}", fg="green"))
        else:
            click.echo("  Specify --all to retry all failed items.")
    finally:
        await services["db"].disconnect()
