"""clawtion search commands -- semantic, keyword, and hybrid search."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import click

from clawtion.config.loader import get_config
from clawtion.config.secrets import get_secret
from clawtion.i18n.translator import t
from clawtion.utils.async_helpers import async_cmd


async def _get_search_service() -> dict[str, Any]:
    """Create SearchService and related objects."""
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.gemini import GeminiEmbeddingClient
    from clawtion.core.search.service import SearchService

    cfg = get_config()
    db_url = os.environ.get("CLAWTION_DB_URL", "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion")
    api_key = get_secret("gemini_api_key") or ""

    db = DatabaseManager(db_url)
    await db.connect()

    embedder = GeminiEmbeddingClient(
        api_key=api_key,
        output_dimensionality=cfg.get("embedding", {}).get("output_dimensionality", 768),
        use_manual_prefix=cfg.get("embedding", {}).get("use_manual_prefix_fallback", True),
    )

    search_service = SearchService(db=db, embedder=embedder)

    return {"db": db, "search_service": search_service}


def _format_results(
    results: list[dict[str, Any]],
    query: str,
    search_type: str,
) -> None:
    """Format and display search results."""
    if not results:
        click.echo(f"  {t('cli.search.no_results')}")
        return

    click.echo()
    click.echo(click.style(f"  {t('cli.search.results_summary', count=len(results), duration=0)}", bold=True))
    click.echo()

    for i, result in enumerate(results, 1):
        score = result.get("score", 0.0)
        file_path = result.get("file_path", "unknown")
        heading = result.get("heading", "")
        content_preview = result.get("content_preview", "") or result.get("snippet", "")

        if heading:
            click.echo(f"  {i}. {click.style(heading, bold=True)}")
        else:
            click.echo(f"  {i}. {click.style(Path(file_path).name, bold=True)}")

        click.echo(f"     {t('cli.search.result_item', score=score, file_path=file_path, heading='')}")
        if content_preview:
            preview = content_preview[:200] + "..." if len(content_preview) > 200 else content_preview
            click.echo(f"     {t('cli.search.result_detail', content_preview=preview)}")
        click.echo()


# ---------------------------------------------------------------------------
# Search group
# ---------------------------------------------------------------------------


@click.group(name="search")
def search() -> None:
    """Search your knowledge base."""
    pass


@search.command(name="search")
@click.argument("query", required=True)
@click.option("--semantic", "mode", flag_value="semantic", help="Use semantic vector search")
@click.option("--keyword", "mode", flag_value="keyword", help="Use keyword full-text search")
@click.option("--hybrid", "mode", flag_value="hybrid", default=True, help="Use hybrid search (default)")
@click.option("--granularity", "granularity", default="all", show_default=True, type=click.Choice(["file", "coarse", "fine", "all"]), help="Chunk granularity level")
@click.option("--top-k", "top_k", default=10, type=int, show_default=True, help="Number of results")
@click.option("--folder", default=None, help="Filter by folder path")
@click.option("--tags", default=None, help="Filter by tags (comma-separated)")
@click.option("--extension", default=None, help="Filter by file extension")
@click.option("--namespace", default=None, help="Filter by namespace UUID")
@async_cmd
async def search_cmd(
    query: str,
    mode: str,
    granularity: str,
    top_k: int,
    folder: str | None,
    tags: str | None,
    extension: str | None,
    namespace: str | None,
) -> None:
    """Search the knowledge base using semantic, keyword, or hybrid search."""
    services = await _get_search_service()
    try:
        search_service = services["search_service"]

        # Build filter dict
        filter_dict: dict[str, Any] = {}
        if folder:
            filter_dict["folder"] = folder
        if tags:
            filter_dict["tags"] = [t.strip() for t in tags.split(",")]
        if extension:
            filter_dict["extension"] = extension

        click.echo(f"  {t('cli.search.query_label', query=query)}")
        if folder:
            click.echo(f"  {t('cli.search.folder_filter', folder=folder)}")
        if namespace:
            click.echo(f"  Namespace: {namespace}")

        if mode == "semantic":
            click.echo(f"  {t('cli.search.semantic', query=query)}")
            results = await search_service.semantic_search(
                query=query,
                granularity=granularity,
                top_k=top_k,
                filter=filter_dict or None,
                namespace=namespace,
            )
        elif mode == "keyword":
            click.echo(f"  {t('cli.search.keyword', query=query)}")
            results = await search_service.keyword_search(
                query=query,
                granularity=granularity,
                top_k=top_k,
                filter=filter_dict or None,
                namespace=namespace,
            )
        else:
            click.echo(f"  {t('cli.search.hybrid', query=query)}")
            results = await search_service.hybrid_search(
                query=query,
                granularity=granularity,
                top_k=top_k,
                semantic_weight=0.5,
                filter=filter_dict or None,
                namespace=namespace,
            )

        _format_results(results, query, mode or "hybrid")
    finally:
        await services["db"].disconnect()
