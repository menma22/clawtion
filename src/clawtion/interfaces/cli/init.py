"""clawtion init command -- first-time setup wizard."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from clawtion.config.secrets import get_secret, set_secret
from clawtion.i18n.translator import t
from clawtion.interfaces.cli.main import async_cmd

DEFAULT_VAULT = os.path.expanduser("~/Documents/clawtion-vault")
CLAUDE_CONFIG_DIR = Path.home() / ".claude"
MCP_CONFIG_PATH = Path.home() / ".claude.json"


def _check_docker() -> bool:
    """Check if Docker Desktop is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _start_docker_compose(project_dir: str | Path) -> bool:
    """Start PostgreSQL via docker compose."""
    click.echo(f"  {t('cli.init.starting_db')}")
    try:
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            click.echo(click.style(f"  {result.stderr}", fg="red"))
            return False

        click.echo("  Waiting for database to become healthy...")
        for _ in range(30):
            health = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format={{.State.Health.Status}}",
                    "clawtion-db",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if health.stdout.strip() == "healthy":
                click.echo(click.style(f"  {t('cli.init.db_started')}", fg="green"))
                return True
            import time
            time.sleep(2)

        click.echo(click.style("  Database health check timed out.", fg="yellow"))
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        click.echo(click.style(f"  Failed to start: {exc}", fg="red"))
        return False


def _run_migrations() -> bool:
    """Run Alembic database migrations."""
    click.echo(f"  {t('cli.init.migrating')}")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            click.echo(
                click.style(
                    t("cli.init.migrations_failed", error=result.stderr.strip()),
                    fg="red",
                )
            )
            return False
        click.echo(click.style(f"  {t('cli.init.migration_ok')}", fg="green"))
        return True
    except FileNotFoundError:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                click.echo(
                    click.style(
                        t("cli.init.migrations_failed", error=result.stderr.strip()),
                        fg="red",
                    )
                )
                return False
            click.echo(click.style(f"  {t('cli.init.migration_ok')}", fg="green"))
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            click.echo(
                click.style(
                    t("cli.init.migrations_failed", error=str(exc)),
                    fg="red",
                )
            )
            return False
    except (subprocess.TimeoutExpired, OSError) as exc:
        click.echo(
            click.style(
                t("cli.init.migrations_failed", error=str(exc)),
                fg="red",
            )
        )
        return False


def _ensure_vault(vault_path: str) -> Path:
    """Create vault directory structure if it does not exist."""
    path = Path(os.path.expandvars(os.path.expanduser(vault_path)))
    path.mkdir(parents=True, exist_ok=True)

    vault_config_dir = path / ".clawtion"
    vault_config_dir.mkdir(parents=True, exist_ok=True)

    for subdir in ["notes", "docs", "images", "attachments"]:
        (path / subdir).mkdir(exist_ok=True)

    return path


def _scan_vault(vault_path: str) -> int:
    """Count files in the vault directory."""
    path = Path(os.path.expandvars(os.path.expanduser(vault_path)))
    count = 0
    for root, _dirs, files in os.walk(str(path)):
        if "/." in root or "\\." in root:
            continue
        for f in files:
            if f.startswith(".") or f == ".gitkeep":
                continue
            count += 1
    return count


def _create_claude_integration(vault_path: str) -> None:
    """Create Claude Code integration files and update ~/.claude.json MCP config."""
    click.echo(f"  {t('cli.init.creating_claude_config')}")

    agents_dir = CLAUDE_CONFIG_DIR / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    skills_dir = CLAUDE_CONFIG_DIR / "skills" / "clawtion-search"
    skills_dir.mkdir(parents=True, exist_ok=True)

    vault_resolved = str(Path(vault_path).resolve())

    knowledge_content = (
        f"# clawtion Knowledge Base\n\n"
        f"This Claude Code agent has access to the clawtion knowledge base vault at:\n"
        f"{vault_resolved}\n\n"
        f"## Available MCP Tools\n\n"
        f"### Search\n"
        f"- `semantic_search(query, top_k, granularity, filter)` -- Semantic vector search\n"
        f"- `keyword_search(query, top_k, granularity, filter)` -- Keyword full-text search\n"
        f"- `hybrid_search(query, top_k, semantic_weight, granularity, filter)` -- Hybrid search\n"
        f"- `metadata_filter(folder, tags, date_from, date_to, extension)` -- Filter by metadata\n\n"
        f"### File Access\n"
        f"- `get_file_chunks(document_id, level)` -- Get chunks of a document\n"
        f"- `get_neighbor_chunks(chunk_id, before, after)` -- Get context around a chunk\n"
        f"- `get_parent_chunk(chunk_id)` -- Get the parent chunk\n\n"
        f"### Notes\n"
        f"- `add_note(title, content, folder, tags)` -- Create a new note\n"
        f"- `get_note(document_id)` -- Get a note\n"
        f"- `update_note(document_id, content)` -- Update a note\n"
        f"- `delete_note(document_id, permanent)` -- Delete a note\n"
        f"- `list_notes(folder, limit, offset)` -- List notes\n"
        f"- `list_folders()` -- List all folders\n\n"
        f"## Usage\n"
        f"When the user asks about their knowledge base, notes, or files:\n"
        f"1. Use `hybrid_search` for best results (combines semantic and keyword search)\n"
        f"2. Use `semantic_search` for conceptual queries\n"
        f"3. Use `keyword_search` for exact matches\n"
        f"4. Use `get_file_chunks` and `get_neighbor_chunks` to explore documents\n"
        f"5. Use note tools for note management\n"
    )
    (agents_dir / "clawtion-knowledge.md").write_text(knowledge_content)

    skill_content = (
        "---\n"
        "name: clawtion-search\n"
        "description: Search the clawtion knowledge base and manage notes\n"
        "triggers:\n"
        '  - "search my knowledge base"\n'
        '  - "find notes about"\n'
        '  - "look up in my vault"\n'
        '  - "clawtion"\n'
        "---\n"
        "\n"
        "# clawtion-search Skill\n\n"
        "Use this skill when the user asks to search their knowledge base, "
        "find notes, or manage their clawtion vault.\n\n"
        "## Search Strategy\n\n"
        "1. Start with `hybrid_search` for general queries\n"
        "2. For conceptual questions, use `semantic_search`\n"
        "3. For exact matches, use `keyword_search`\n"
        "4. Use `metadata_filter` to narrow results by folder, tags, or date\n\n"
        "## Note Management\n\n"
        "Use note tools (add_note, get_note, update_note, delete_note, list_notes) "
        "to manage your knowledge base notes.\n"
    )
    (skills_dir / "SKILL.md").write_text(skill_content)

    mcp_config: dict[str, Any] = {}
    if MCP_CONFIG_PATH.exists():
        try:
            raw = MCP_CONFIG_PATH.read_text(encoding="utf-8")
            mcp_config = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            pass

    if "mcpServers" not in mcp_config:
        mcp_config["mcpServers"] = {}

    mcp_config["mcpServers"]["clawtion"] = {
        "command": "clawtion",
        "args": ["mcp-serve"],
        "type": "cli",
    }

    MCP_CONFIG_PATH.write_text(json.dumps(mcp_config, indent=2, ensure_ascii=False), encoding="utf-8")

    click.echo(click.style(f"  {t('cli.init.claude_config_ok')}", fg="green"))


# ---------------------------------------------------------------------------
# Init command
# ---------------------------------------------------------------------------


@click.command(name="init")
@click.option("--vault-path", default=None, help="Vault directory path")
@click.option("--gemini-key", default=None, help="Gemini API key")
@click.option("--mode", default=None, type=click.Choice(["manual", "scheduled", "background"]), help="Service mode")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@async_cmd
async def init(
    vault_path: str | None,
    gemini_key: str | None,
    mode: str | None,
    yes: bool,
) -> None:
    """Initialize clawtion with first-time setup wizard."""
    click.echo()
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo(click.style(t("cli.init.welcome").center(60), bold=True))
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo()

    # 1. Vault path
    resolved_vault = vault_path
    if not resolved_vault:
        click.echo(
            click.style(f"  {t('cli.init.vault_default', path=DEFAULT_VAULT)}", fg="bright_black")
        )
        resolved_vault = click.prompt(
            click.style(f"  {t('cli.init.vault_prompt')}", bold=True),
            default=DEFAULT_VAULT,
            show_default=False,
        )

    resolved_vault = os.path.expandvars(os.path.expanduser(resolved_vault))
    vault = _ensure_vault(resolved_vault)

    # 2. Gemini API key
    api_key = gemini_key or get_secret("gemini_api_key")
    if not api_key:
        key_from_env = os.environ.get("CLAWTION_GEMINI_API_KEY", "")
        if key_from_env:
            api_key = key_from_env
            click.echo("  Using CLAWTION_GEMINI_API_KEY from environment.")
        elif not yes:
            api_key_input = click.prompt(
                click.style(f"  {t('cli.init.api_key_prompt')}", bold=True),
                default="",
                show_default=False,
            )
            if api_key_input.strip():
                api_key = api_key_input.strip()
                set_secret("gemini_api_key", api_key)

    if api_key:
        set_secret("gemini_api_key", api_key)
        click.echo(click.style(f"  {t('cli.init.api_key_saved')}", fg="green"))
    else:
        click.echo(click.style(f"  {t('cli.init.gemini_missing')}", fg="yellow"))

    # 3. Check Docker and start DB
    click.echo(f"  {t('cli.init.docker_check')}")
    if not _check_docker():
        click.echo(click.style(f"  {t('cli.init.docker_not_found')}", fg="red"))
        click.echo("  You can still use clawtion with an external PostgreSQL database.")
    else:
        click.echo(click.style(f"  {t('cli.init.docker_ok')}", fg="green"))
        project_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        if _start_docker_compose(project_dir):
            await asyncio.sleep(3)
            _run_migrations()
        else:
            click.echo(click.style("  Database setup skipped.", fg="yellow"))

    # 4. Claude Code integration
    _create_claude_integration(str(vault))

    # 5. Scan vault
    click.echo(f"  {t('cli.init.scanning')}")
    file_count = _scan_vault(str(vault))
    click.echo(click.style(f"  {t('cli.init.scan_complete', count=file_count)}", fg="green"))

    # 6. Service mode selection
    selected_mode = mode
    if not selected_mode and not yes:
        click.echo()
        click.echo(f"  {t('cli.init.service_prompt')}")
        click.echo(f"    1. {t('cli.init.mode_manual')}")
        click.echo(f"    2. {t('cli.init.mode_scheduled')}")
        click.echo(f"    3. {t('cli.init.mode_background')}")
        mode_choice = click.prompt("  Select (1/2/3)", default="1", show_default=False)
        mode_map = {"1": "manual", "2": "scheduled", "3": "background"}
        selected_mode = mode_map.get(mode_choice, "manual")

    selected_mode = selected_mode or "manual"

    vault_config_dir = vault / ".clawtion"
    vault_config = vault_config_dir / "config.yaml"
    vault_config.write_text(f"service:\n  mode: {selected_mode}\n", encoding="utf-8")

    # 7. Completion
    click.echo()
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo(click.style(t("cli.init.setup_complete").center(60), bold=True, fg="green"))
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo()
    click.echo(f"  Vault:      {vault}")
    click.echo(f"  Service:    {selected_mode}")
    click.echo(f"  Files:      {file_count}")
    click.echo()
    click.echo("  Next steps:")
    click.echo("    clawtion start")
    click.echo("    clawtion index")
    click.echo("    clawtion search <query>")
    click.echo()
