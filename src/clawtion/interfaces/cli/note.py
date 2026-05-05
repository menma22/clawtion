"""clawtion note commands -- CRUD for notes."""

from __future__ import annotations

import os
from typing import Any

import click

from clawtion.config.loader import get_config
from clawtion.i18n.translator import t
from clawtion.utils.async_helpers import async_cmd


async def _get_note_services() -> dict[str, Any]:
    """Create NoteService and related objects."""
    from clawtion.config.secrets import get_secret
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.gemini import GeminiEmbeddingClient
    from clawtion.core.indexing.queue import QueueManager
    from clawtion.core.indexing.service import IndexingService
    from clawtion.core.note.service import NoteService

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

    note_service = NoteService(db=db, vault_path=vault_path, indexing_service=indexing_service)

    return {"db": db, "note_service": note_service}


# ---------------------------------------------------------------------------
# Note group
# ---------------------------------------------------------------------------


@click.group(name="note")
def note() -> None:
    """Create, read, update, and delete notes."""
    pass


@note.command(name="add")
@click.argument("title")
@click.option("--content", "-c", default="", help="Note content")
@click.option("--folder", "-f", default=None, help="Folder path within vault")
@click.option("--tags", "-t", default=None, help="Comma-separated tags")
@async_cmd
async def add(title: str, content: str, folder: str | None, tags: str | None) -> None:
    """Create a new note."""
    services = await _get_note_services()
    try:
        note_service = services["note_service"]

        tag_list: list[str] = [t.strip() for t in tags.split(",")] if tags else []
        result = await note_service.create_note(
            title=title,
            content=content,
            folder=folder or "",
            tags=tag_list,
        )

        doc_id = result.get("document_id", "unknown")
        file_path = result.get("file_path", "")
        click.echo(click.style(
            f"  {t('cli.note.created', file_path=file_path)}",
            fg="green",
        ))
        click.echo(f"  ID: {doc_id}")
    finally:
        await services["db"].disconnect()


@note.command(name="get")
@click.argument("document_id")
@async_cmd
async def get(document_id: str) -> None:
    """Retrieve a note by its document ID."""
    services = await _get_note_services()
    try:
        note_service = services["note_service"]
        note_data = await note_service.get_note(document_id)

        if not note_data:
            click.echo(click.style(f"  {t('cli.note.not_found', id=document_id)}", fg="red"))
            return

        title = note_data.get("title", "Untitled")
        file_path = note_data.get("file_path", "")
        content = note_data.get("content", "")
        tags = note_data.get("tags", [])
        file_size = note_data.get("file_size", 0)
        last_indexed = note_data.get("last_indexed", "")

        click.echo()
        click.echo(click.style(f"  {t('cli.note.get_header', title=title)}", bold=True))
        click.echo(f"  {t('cli.note.get_meta', file_path=file_path, file_size=file_size, last_indexed=last_indexed)}")
        if tags:
            click.echo(f"  {t('cli.note.tags_label', tags=', '.join(tags))}")
        click.echo()
        if content:
            click.echo(f"  {content}")
        else:
            click.echo("  (no content)")
        click.echo()
    finally:
        await services["db"].disconnect()


@note.command(name="update")
@click.argument("document_id")
@click.option("--content", "-c", default=None, help="New note content")
@click.option("--title", "-t", default=None, help="New note title")
@async_cmd
async def update(document_id: str, content: str | None, title: str | None) -> None:
    """Update an existing note."""
    services = await _get_note_services()
    try:
        note_service = services["note_service"]

        update_fields: dict[str, Any] = {}
        if content is not None:
            update_fields["content"] = content
        if title is not None:
            update_fields["title"] = title

        if not update_fields:
            click.echo("  Nothing to update. Provide --content or --title.")
            return

        success = await note_service.update_note(document_id, **update_fields)
        if success:
            click.echo(click.style(f"  {t('cli.note.restored', id=document_id)}" if "restored" in str(update_fields) else f"  {t('cli.general.success')}", fg="green"))
        else:
            click.echo(click.style(f"  {t('cli.note.not_found', id=document_id)}", fg="red"))
    finally:
        await services["db"].disconnect()


@note.command(name="delete")
@click.argument("document_id")
@click.option("--permanent", is_flag=True, help="Permanently delete instead of moving to trash")
@async_cmd
async def delete(document_id: str, permanent: bool) -> None:
    """Delete a note. By default, moves to trash."""
    services = await _get_note_services()
    try:
        note_service = services["note_service"]

        success = await note_service.delete_note(document_id, permanent=permanent)
        if success:
            if permanent:
                click.echo(click.style(f"  {t('cli.note.permanently_deleted', file_path=document_id)}", fg="yellow"))
            else:
                click.echo(click.style(f"  {t('cli.note.deleted', file_path=document_id)}", fg="green"))
        else:
            click.echo(click.style(f"  {t('cli.note.not_found', id=document_id)}", fg="red"))
    finally:
        await services["db"].disconnect()


@note.command(name="list")
@click.option("--folder", "-f", default=None, help="Filter by folder")
@click.option("--limit", default=50, type=int, show_default=True, help="Max results")
@click.option("--offset", default=0, type=int, show_default=True, help="Result offset")
@async_cmd
async def list_cmd(folder: str | None, limit: int, offset: int) -> None:
    """List notes, optionally filtered by folder."""
    services = await _get_note_services()
    try:
        note_service = services["note_service"]
        notes = await note_service.list_notes(folder=folder, limit=limit, offset=offset)

        if not notes:
            click.echo(f"  {t('cli.note.list_empty')}")
            return

        if folder:
            click.echo(f"  {t('cli.note.folder_header', folder=folder)}")
        else:
            click.echo(f"  {t('cli.note.list_header', count=len(notes))}")

        click.echo()

        for n in notes:
            title = n.get("title", "Untitled")
            file_path = n.get("file_path", "")
            updated = n.get("updated_at", "")

            # Truncate to fit
            display_path = file_path if len(file_path) < 50 else "..." + file_path[-47:]
            click.echo(f"    {t('cli.note.list_item', title=title, file_path=display_path, updated=updated)}")

        click.echo()
    finally:
        await services["db"].disconnect()
