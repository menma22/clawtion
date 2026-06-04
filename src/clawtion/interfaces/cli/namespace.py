"""clawtion namespace commands -- create, list, assign."""

from __future__ import annotations

import os
from typing import Any

import click

from clawtion.config.loader import get_config
from clawtion.i18n.translator import t
from clawtion.utils.async_helpers import async_cmd


async def _get_namespace_service() -> dict[str, Any]:
    """Create NamespaceService and return it with the db manager."""
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.namespace.service import NamespaceService

    get_config()
    db_url = os.environ.get(
        "CLAWTION_DB_URL",
        "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion",
    )

    db = DatabaseManager(db_url)
    await db.connect()

    service = NamespaceService(db=db)

    return {"db": db, "service": service}


# ---------------------------------------------------------------------------
# Namespace group
# ---------------------------------------------------------------------------


@click.group(name="namespace")
def namespace() -> None:
    """Manage namespaces for logical partitioning."""
    pass


@namespace.command(name="create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Namespace description")
@async_cmd
async def create_cmd(name: str, description: str) -> None:
    """Create a new namespace.

    NAME is the unique name for the namespace (max 100 characters).
    """
    services = await _get_namespace_service()
    try:
        ns = await services["service"].create(name=name, description=description)
        click.echo()
        click.echo(
            click.style(
                t("cli.namespace.created", name=ns.name, namespace_id=ns.namespace_id),
                fg="green",
            )
        )
        if ns.description:
            click.echo(f"  {t('cli.namespace.description')}: {ns.description}")
        click.echo(f"  {t('cli.namespace.namespace_id')}: {ns.namespace_id}")
    except Exception as exc:
        click.echo(
            click.style(t("cli.general.error", message=str(exc)), fg="red", bold=True),
            err=True,
        )
    finally:
        await services["db"].disconnect()


@namespace.command(name="list")
@async_cmd
async def list_cmd() -> None:
    """List all namespaces."""
    services = await _get_namespace_service()
    try:
        namespaces = await services["service"].list_all()
        if not namespaces:
            click.echo()
            click.echo(f"  {t('cli.namespace.no_namespaces')}")
            return

        click.echo()
        click.echo(click.style(t("cli.namespace.list_header", count=len(namespaces)), bold=True))
        click.echo()

        for ns in namespaces:
            click.echo(f"  {click.style(ns.name, bold=True)} ({ns.chunk_count} chunks)")
            click.echo(f"    {t('cli.namespace.namespace_id')}: {ns.namespace_id}")
            if ns.description:
                click.echo(f"    {t('cli.namespace.description')}: {ns.description}")
            click.echo()
    except Exception as exc:
        click.echo(
            click.style(t("cli.general.error", message=str(exc)), fg="red", bold=True),
            err=True,
        )
    finally:
        await services["db"].disconnect()


@namespace.command(name="assign")
@click.argument("document_id")
@click.argument("namespace_id")
@async_cmd
async def assign_cmd(document_id: str, namespace_id: str) -> None:
    """Assign all chunks of a document to a namespace.

    DOCUMENT_ID is the UUID of the document.
    NAMESPACE_ID is the UUID of the target namespace.
    """
    services = await _get_namespace_service()
    try:
        chunks_updated = await services["service"].assign_document(
            document_id=document_id,
            namespace_id=namespace_id,
        )
        click.echo()
        click.echo(
            click.style(
                t(
                    "cli.namespace.assigned",
                    document_id=document_id,
                    namespace_id=namespace_id,
                    chunks_updated=chunks_updated,
                ),
                fg="green",
            )
        )
    except Exception as exc:
        click.echo(
            click.style(t("cli.general.error", message=str(exc)), fg="red", bold=True),
            err=True,
        )
    finally:
        await services["db"].disconnect()
