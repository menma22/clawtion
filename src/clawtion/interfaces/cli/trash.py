"""clawtion trash commands -- list, restore, and empty the trash."""

from __future__ import annotations

import os
from typing import Any

import click

from clawtion.config.loader import get_config
from clawtion.i18n.translator import t

from clawtion.interfaces.cli.main import async_cmd


async def _get_trash_service() -> dict[str, Any]:
    """Create TrashService and related objects."""
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.trash.service import TrashService

    cfg = get_config()
    db_url = os.environ.get("CLAWTION_DB_URL", "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion")
    vault_path = os.path.expandvars(os.path.expanduser(cfg.get("vault", {}).get("path", "~/Documents/clawtion-vault")))

    db = DatabaseManager(db_url)
    await db.connect()

    trash_service = TrashService(db=db, vault_path=vault_path)

    return {"db": db, "trash_service": trash_service}


# ---------------------------------------------------------------------------
# Trash group
# ---------------------------------------------------------------------------


@click.group(name="trash")
def trash() -> None:
    """Manage trashed notes and documents."""
    pass


@trash.command(name="list")
@async_cmd
async def list_cmd() -> None:
    """List items in the trash."""
    services = await _get_trash_service()
    try:
        trash_service = services["trash_service"]
        items = await trash_service.list_trash()

        if not items:
            click.echo(f"  {t('cli.trash.list_empty')}")
            return

        click.echo(f"  {t('cli.trash.list_header', count=len(items))}")
        click.echo()

        for item in items:
            item_id = item.get("id", "unknown")
            file_path = item.get("file_path", "unknown")
            deleted_at = item.get("deleted_at", "")
            purge_at = item.get("purge_at", "")

            click.echo(
                f"    {t('cli.trash.list_item', id=item_id, file_path=file_path, deleted_at=deleted_at, purge_at=purge_at)}"
            )

        # Show purge info
        cfg = get_config()
        days = cfg.get("trash", {}).get("auto_purge_after_days", 7)
        click.echo(f"  {t('cli.trash.purge_info', days=days)}")
        click.echo()
    finally:
        await services["db"].close()


@trash.command(name="restore")
@click.argument("item_id")
@async_cmd
async def restore(item_id: str) -> None:
    """Restore a trashed item by its ID."""
    services = await _get_trash_service()
    try:
        trash_service = services["trash_service"]
        success = await trash_service.restore(item_id)

        if success:
            click.echo(click.style(f"  {t('cli.trash.restored', id=item_id)}", fg="green"))
        else:
            click.echo(click.style(f"  {t('cli.trash.not_found', id=item_id)}", fg="red"))
    finally:
        await services["db"].close()


@trash.command(name="empty")
@click.confirmation_option(prompt=t("cli.trash.confirm_empty"))
@async_cmd
async def empty() -> None:
    """Permanently empty the trash."""
    services = await _get_trash_service()
    try:
        trash_service = services["trash_service"]
        count = await trash_service.empty_trash()

        click.echo(click.style(f"  {t('cli.trash.emptied', count=count)}", fg="yellow"))
    finally:
        await services["db"].close()
