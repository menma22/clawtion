"""clawtion doctor command -- comprehensive diagnostics."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import click

from clawtion.config.loader import get_config
from clawtion.config.secrets import get_secret
from clawtion.i18n.translator import t
from clawtion.utils.async_helpers import async_cmd


class DiagnosticResult:
    """Represents a single diagnostic check result."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.status: str = "ok"
        self.message: str = ""

    def ok(self, message: str = "") -> None:
        self.status = "ok"
        self.message = message

    def warn(self, message: str) -> None:
        self.status = "warn"
        self.message = message

    def fail(self, message: str) -> None:
        self.status = "fail"
        self.message = message

    def display(self) -> None:
        if self.status == "ok":
            click.echo(f"    {t('cli.doctor.status_ok')}")
        elif self.status == "warn":
            click.echo(f"    {click.style(t('cli.doctor.status_warn'), fg='yellow')}: {self.message}")
        else:
            click.echo(f"    {click.style(t('cli.doctor.status_error'), fg='red')}: {self.message}")


# ---------------------------------------------------------------------------
# Diagnostic checks
# ---------------------------------------------------------------------------


async def _check_docker() -> DiagnosticResult:
    """Check if Docker Desktop is installed and running."""
    result = DiagnosticResult(t("cli.doctor.docker", status=""))
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        rc = await proc.wait()
        if rc == 0:
            result.ok()
        else:
            result.fail("Docker engine is not running")
    except FileNotFoundError:
        result.fail("Docker not found. Install Docker Desktop.")
    return result


async def _check_db_connection() -> DiagnosticResult:
    """Check if the database is reachable."""
    result = DiagnosticResult(t("cli.doctor.db_connection", status=""))
    try:
        from clawtion.core.db.connection import DatabaseManager
        db_url = os.environ.get("CLAWTION_DB_URL", "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion")
        db = DatabaseManager(db_url)
        await db.connect()
        await db.disconnect()
        result.ok()
    except Exception as exc:
        result.fail(str(exc))
    return result


async def _check_db_schema() -> DiagnosticResult:
    """Check database schema version."""
    result = DiagnosticResult(t("cli.doctor.db_schema", version="", status=""))
    try:
        from clawtion.core.db.migrations import check_migration_status
        db_url = os.environ.get("CLAWTION_DB_URL", "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion")
        status_str = await check_migration_status(db_url)
        if status_str == "up-to-date":
            result.ok(status_str)
        elif status_str.startswith("error"):
            result.fail(status_str)
        else:
            result.warn(status_str)
    except Exception as exc:
        result.fail(str(exc))
    return result


async def _check_gemini_key() -> DiagnosticResult:
    """Check if Gemini API key is available and valid."""
    result = DiagnosticResult(t("cli.doctor.gemini_key", status=""))
    key = get_secret("gemini_api_key")
    if not key:
        result.fail("No API key configured. Run 'clawtion config set-key gemini'.")
        return result

    try:
        # Quick validation by checking key format
        if key.startswith("AIza") and len(key) > 20:
            result.ok()
        else:
            result.warn("Key exists but format looks unusual")
    except Exception as exc:
        result.fail(str(exc))
    return result


async def _check_claude_config() -> DiagnosticResult:
    """Check Claude Code integration files."""
    result = DiagnosticResult(t("cli.doctor.claude_config", status=""))
    mcp_path = Path.home() / ".claude.json"
    knowledge_path = Path.home() / ".claude" / "agents" / "clawtion-knowledge.md"
    skill_path = Path.home() / ".claude" / "skills" / "clawtion-search" / "SKILL.md"

    issues: list[str] = []
    if not mcp_path.exists():
        issues.append("~/.claude.json not found")
    elif mcp_path.exists():
        import json
        try:
            cfg = json.loads(mcp_path.read_text(encoding="utf-8"))
            if "clawtion" not in cfg.get("mcpServers", {}):
                issues.append("clawtion MCP server not in ~/.claude.json")
        except (json.JSONDecodeError, OSError):
            issues.append("~/.claude.json is not valid JSON")

    if not knowledge_path.exists():
        issues.append("Agent knowledge file not found")
    if not skill_path.exists():
        issues.append("Skill file not found")

    if not issues:
        result.ok()
    else:
        for issue in issues:
            result.warn(issue)
    return result


async def _check_vault() -> DiagnosticResult:
    """Check vault directory accessibility and file count."""
    cfg = get_config()
    vault_path = os.path.expandvars(os.path.expanduser(cfg.get("vault", {}).get("path", "")))
    result = DiagnosticResult(t("cli.doctor.vault", path=vault_path, count=0, status=""))

    if not vault_path:
        result.fail("Vault path not configured")
        return result

    vault = Path(vault_path)
    if not vault.exists():
        result.fail(f"Directory does not exist: {vault}")
        return result

    if not vault.is_dir():
        result.fail(f"Not a directory: {vault}")
        return result

    file_count = 0
    for root, _dirs, files in os.walk(str(vault)):
        if "/." in root or "\\." in root:
            continue
        file_count += sum(1 for f in files if not f.startswith("."))

    result.ok(f"{file_count} files")
    return result

async def _check_disk_space() -> DiagnosticResult:
    """Check available disk space."""
    cfg = get_config()
    vault_path = os.path.expandvars(os.path.expanduser(cfg.get("vault", {}).get("path", "")))
    result = DiagnosticResult(t("cli.doctor.disk", free=""))

    if vault_path:
        usage = shutil.disk_usage(os.path.dirname(vault_path) if vault_path else "/")
        free_gb = usage.free / (1024 ** 3)
        result.ok(f"{free_gb:.1f} GB free")
    else:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        result.ok(f"{free_gb:.1f} GB free")

    return result


async def _check_queue() -> DiagnosticResult:
    """Check indexing queue statistics."""
    result = DiagnosticResult(t("cli.doctor.queue_summary", pending=0, failed=0))
    try:
        from clawtion.core.db.connection import DatabaseManager
        from clawtion.core.indexing.queue import QueueManager

        db_url = os.environ.get("CLAWTION_DB_URL", "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion")
        db = DatabaseManager(db_url)
        await db.connect()

        queue = QueueManager(db)
        stats = await queue.get_stats()
        pending: int = stats.get("pending", 0)
        failed_count: int = stats.get("failed", 0)
        await db.disconnect()

        if pending == 0 and failed_count == 0:
            result.ok("Queue is empty")
        else:
            status_str = t("cli.doctor.queue_summary", pending=pending, failed=failed_count)
            if failed_count > 0:
                result.warn(status_str)
            else:
                result.ok(status_str)
    except Exception as exc:
        result.warn(str(exc))
    return result


# ---------------------------------------------------------------------------
# Doctor command
# ---------------------------------------------------------------------------


@click.command(name="doctor")
@async_cmd
async def doctor() -> None:
    """Run comprehensive diagnostics on the clawtion installation."""
    click.echo()
    click.echo(
        click.style(f"  {t('cli.doctor.header')}", bold=True, fg="cyan")
    )
    click.echo(
        click.style(f"  {t('cli.doctor.separator')}", fg="cyan")
    )
    click.echo()

    checks = [
        await _check_docker(),
        await _check_db_connection(),
        await _check_db_schema(),
        await _check_gemini_key(),
        await _check_claude_config(),
        await _check_vault(),
        await _check_disk_space(),
        await _check_queue(),
    ]

    issues = 0
    for check in checks:
        click.echo(f"  {t('cli.doctor.check', name=check.name)}")
        check.display()
        if check.status == "fail":
            issues += 1
        click.echo()

    # Overall status
    if issues == 0:
        click.echo(
            click.style(
                f"  {t('cli.doctor.overall', verdict=t('cli.doctor.status_ok'))}",
                fg="green",
                bold=True,
            )
        )
    else:
        click.echo(
            click.style(
                f"  {t('cli.doctor.overall', verdict=t('cli.doctor.status_error'))}",
                fg="red",
                bold=True,
            )
        )
        click.echo(f"  {issues} issue(s) found.")

    click.echo()
