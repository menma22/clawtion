"""clawtion git commands -- clone, update, and manage Git repositories."""

from __future__ import annotations

import os
from typing import Any

import click

from clawtion.config.loader import get_config
from clawtion.i18n.translator import t
from clawtion.utils.async_helpers import async_cmd


async def _get_services() -> dict[str, Any]:
    """Create core service instances."""
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.gemini import GeminiEmbeddingClient
    from clawtion.core.indexing.git_loader import GitLoader
    from clawtion.core.indexing.queue import QueueManager
    from clawtion.core.indexing.service import IndexingService

    cfg = get_config()
    db_url = os.environ.get(
        "CLAWTION_DB_URL",
        "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion",
    )
    vault_path = os.path.expandvars(os.path.expanduser(cfg.get("vault", {}).get("path", "~/Documents/clawtion-vault")))
    from clawtion.config.secrets import get_secret

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

    git_loader = GitLoader(
        vault_path=vault_path,
        indexing_service=indexing_service,
    )

    return {
        "db": db,
        "indexing_service": indexing_service,
        "git_loader": git_loader,
        "vault_path": vault_path,
        "cfg": cfg,
    }


# ---------------------------------------------------------------------------
# Git group
# ---------------------------------------------------------------------------


@click.group(name="git")
def git() -> None:
    """Clone and index Git repositories."""
    pass


@git.command(name="add")
@click.argument("repo_url")
@click.option("--branch", default="main", show_default=True, help="Branch to clone")
@click.option(
    "--path",
    "target_path",
    default=None,
    help="Target subdirectory inside vault/git/ (auto-derived from URL by default)",
)
@click.option(
    "--pattern",
    "patterns",
    multiple=True,
    default=None,
    help="File glob patterns to index (repeatable, e.g. --pattern *.py --pattern *.md)",
)
@async_cmd
async def git_add(
    repo_url: str,
    branch: str,
    target_path: str | None,
    patterns: tuple[str, ...] | None,
) -> None:
    """Clone a Git repository and index its files.

    REPO_URL is the Git remote URL (HTTPS or SSH).

    Examples:

        clawtion git add https://github.com/user/repo.git

        clawtion git add git@github.com:user/repo.git --branch develop

        clawtion git add https://github.com/user/repo.git --pattern *.md --pattern *.py
    """
    services = await _get_services()
    try:
        git_loader = services["git_loader"]

        click.echo(f"  {t('cli.git.cloning', repo=repo_url)}")

        patterns_list: list[str] | None = list(patterns) if patterns else None
        result = await git_loader.clone_and_index(
            repo_url=repo_url,
            branch=branch,
            target_path=target_path,
            file_patterns=patterns_list,
        )

        click.echo(
            click.style(
                t(
                    "cli.git.add_complete",
                    indexed=result["indexed"],
                    skipped=result["skipped"],
                    path=result["local_path"],
                ),
                fg="green",
            )
        )

        if result["errors"]:
            click.echo(click.style(t("cli.git.errors_header"), fg="yellow"))
            for err in result["errors"]:
                click.echo(click.style(f"  - {err}", fg="red"))

    except Exception as e:
        click.echo(
            click.style(t("cli.general.error", message=str(e)), fg="red", bold=True),
            err=True,
        )
    finally:
        await services["db"].disconnect()


@git.command(name="update")
@click.argument("repo_path", required=False, default=None)
@click.option("--branch", default=None, help="Branch to pull (detects current by default)")
@click.option("--all", "update_all", is_flag=True, help="Update all indexed repos")
@async_cmd
async def git_update(
    repo_path: str | None,
    branch: str | None,
    update_all: bool,
) -> None:
    """Pull latest changes and re-index a Git repository.

    REPO_PATH is the local path or name of the cloned repository.
    If omitted and --all is set, updates every indexed repository.
    """
    services = await _get_services()
    try:
        git_loader = services["git_loader"]

        if update_all:
            repos = git_loader.get_indexed_repos()
            if not repos:
                click.echo(f"  {t('cli.git.no_repos')}")
                return

            click.echo(f"  {t('cli.git.updating_all', count=len(repos))}")
            for repo in repos:
                click.echo(f"    {t('cli.git.updating', name=repo['name'])}")
                try:
                    result = await git_loader.update_indexed_repo(
                        repo["path"],
                        branch=branch,
                    )
                    click.echo(
                        click.style(
                            f"      {t('cli.git.update_ok', indexed=result['indexed'], skipped=result['skipped'])}",
                            fg="green",
                        )
                    )
                except Exception as e:
                    click.echo(click.style(f"      {t('cli.general.error', message=str(e))}", fg="red"))
        elif repo_path:
            click.echo(f"  {t('cli.git.updating', name=repo_path)}")
            result = await git_loader.update_indexed_repo(repo_path, branch=branch)
            click.echo(
                click.style(
                    t(
                        "cli.git.update_ok",
                        indexed=result["indexed"],
                        skipped=result["skipped"],
                    ),
                    fg="green",
                )
            )
        else:
            click.echo(
                click.style(
                    "  Specify a repository path/name or use --all to update all repos.",
                    fg="yellow",
                )
            )
    except Exception as e:
        click.echo(
            click.style(t("cli.general.error", message=str(e)), fg="red", bold=True),
            err=True,
        )
    finally:
        await services["db"].disconnect()


@git.command(name="list")
@async_cmd
async def git_list() -> None:
    """List all cloned Git repositories."""
    services = await _get_services()
    try:
        git_loader = services["git_loader"]

        repos = git_loader.get_indexed_repos()
        if not repos:
            click.echo(f"  {t('cli.git.no_repos')}")
            return

        click.echo()
        click.echo(click.style(f"  {t('cli.git.list_header', count=len(repos))}", bold=True))
        click.echo()
        for repo in repos:
            click.echo(f"    {click.style(repo['name'], bold=True)}")
            if repo["remote"]:
                click.echo(f"      {t('cli.git.remote_label')}: {repo['remote']}")
            if repo["branch"]:
                click.echo(f"      {t('cli.git.branch_label')}: {repo['branch']}")
            click.echo(f"      {t('cli.git.path_label')}: {repo['path']}")
            click.echo()
    except Exception as e:
        click.echo(
            click.style(t("cli.general.error", message=str(e)), fg="red", bold=True),
            err=True,
        )
    finally:
        await services["db"].disconnect()


@git.command(name="remove")
@click.argument("repo_name")
@click.confirmation_option(prompt="This will remove the repository and its indexed files. Continue?")
@async_cmd
async def git_remove(repo_name: str) -> None:
    """Remove a cloned repository and its indexed documents.

    REPO_NAME is the short name shown in ``clawtion git list``.
    """
    services = await _get_services()
    try:
        git_loader = services["git_loader"]

        click.echo(f"  {t('cli.git.removing', name=repo_name)}")
        await git_loader.remove_repo(repo_name)
        click.echo(click.style(t("cli.git.remove_ok"), fg="green"))
    except Exception as e:
        click.echo(
            click.style(t("cli.general.error", message=str(e)), fg="red", bold=True),
            err=True,
        )
    finally:
        await services["db"].disconnect()
