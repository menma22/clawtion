"""clawtion service commands -- start, stop, status, install, uninstall."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from clawtion.config.loader import get_config
from clawtion.i18n.translator import t
from clawtion.utils.async_helpers import async_cmd

_SERVICE_NAME = "clawtion"
_DB_URL_DEFAULT = "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion"


def _get_project_dir() -> Path:
    """Return the project root directory containing docker-compose.yml."""
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def _check_docker_running() -> bool:
    """Check if Docker Desktop (engine) is running."""
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


def _check_db_connection() -> bool:
    """Check if the database is reachable."""
    try:
        result = subprocess.run(
            [
                sys.executable, "-c",
                "import asyncio; "
                "from clawtion.core.db.connection import DatabaseManager; "
                "import os; "
                "async def c(): "
                "  db = DatabaseManager(os.environ.get('CLAWTION_DB_URL', "
                "    'postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion')); "
                "  await db.connect(); "
                "  await db.close()"
                "asyncio.run(c())",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# start / stop / status
# ---------------------------------------------------------------------------


@click.group(name="service")
def service() -> None:
    """Manage clawtion background services (start, stop, status, install)."""
    pass


@service.command(name="start")
@async_cmd
async def start() -> None:
    """Start clawtion services (Docker, DB, worker)."""
    click.echo(f"  {t('cli.service.starting')}")

    project_dir = _get_project_dir()

    # 1. Start Docker containers
    if not _check_docker_running():
        click.echo(click.style(f"  {t('cli.doctor.docker', status=t('cli.doctor.status_error'))}", fg="red"))
        click.echo("  Please start Docker Desktop first.")
        return

    click.echo("  Starting PostgreSQL container...")
    try:
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            click.echo(click.style(f"  docker compose failed: {result.stderr}", fg="red"))
            return
        click.echo(click.style("  PostgreSQL started.", fg="green"))
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        click.echo(click.style(f"  Failed: {exc}", fg="red"))
        return

    # 2. Check DB connection
    await asyncio.sleep(2)
    db_url = os.environ.get("CLAWTION_DB_URL", _DB_URL_DEFAULT)
    if _check_db_connection():
        click.echo(click.style(f"  {t('cli.service.started', db_url=db_url)}", fg="green"))
    else:
        click.echo(click.style("  Database connection pending...", fg="yellow"))


@service.command(name="stop")
@async_cmd
async def stop() -> None:
    """Stop clawtion services (Docker containers)."""
    click.echo(f"  {t('cli.service.stopping')}")

    project_dir = _get_project_dir()
    try:
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            click.echo(click.style(f"  docker compose down failed: {result.stderr}", fg="red"))
            return
        click.echo(click.style(f"  {t('cli.service.stopped')}", fg="green"))
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        click.echo(click.style(f"  Failed: {exc}", fg="red"))


@service.command(name="status")
@async_cmd
async def status() -> None:
    """Show status of all clawtion services."""
    click.echo()
    click.echo(click.style(f"  {t('cli.service.status_header')}", bold=True))
    click.echo()

    # Docker
    docker_ok = _check_docker_running()
    docker_status = (
        click.style(t("cli.service.status_running"), fg="green")
        if docker_ok
        else click.style(t("cli.service.status_stopped"), fg="red")
    )
    click.echo(f"    Docker:    {docker_status}")

    # DB
    db_ok = _check_db_connection()
    db_status = (
        click.style(t("cli.service.status_running"), fg="green")
        if db_ok
        else click.style(t("cli.service.status_stopped"), fg="red")
    )
    click.echo(f"    Database:  {db_status}")

    # Config
    cfg = get_config()
    service_mode = cfg.get("service", {}).get("mode", "manual")
    mode_labels = {
        "manual": t("cli.service.mode_manual"),
        "scheduled": t("cli.service.mode_scheduled"),
        "background": t("cli.service.mode_background"),
    }
    click.echo(f"    Mode:      {mode_labels.get(service_mode, service_mode)}")

    # Vault
    vault_path = cfg.get("vault", {}).get("path", "not configured")
    click.echo(f"    Vault:     {os.path.expandvars(os.path.expanduser(vault_path))}")

    click.echo()


# ---------------------------------------------------------------------------
# service install / uninstall
# ---------------------------------------------------------------------------


@service.command(name="install")
@click.option(
    "--mode",
    default="manual",
    type=click.Choice(["manual", "scheduled", "background"]),
    help="Service mode",
)
@async_cmd
async def install(mode: str) -> None:
    """Register clawtion as an OS service (Task Scheduler / launchd)."""
    click.echo(f"  {t('cli.service.installing', mode=mode)}")

    if sys.platform == "win32":
        _install_windows(mode)
    elif sys.platform == "darwin":
        _install_macos(mode)
    else:
        _install_linux(mode)

    click.echo(click.style(f"  {t('cli.service.installed', mode=mode)}", fg="green"))


@service.command(name="uninstall")
@async_cmd
async def uninstall() -> None:
    """Remove clawtion from OS service registry."""
    click.echo(f"  {t('cli.service.uninstalling')}")

    if sys.platform == "win32":
        _uninstall_windows()
    elif sys.platform == "darwin":
        _uninstall_macos()
    else:
        _uninstall_linux()

    click.echo(click.style(f"  {t('cli.service.uninstalled')}", fg="green"))


# ---------------------------------------------------------------------------
# Platform-specific helpers
# ---------------------------------------------------------------------------


def _install_windows(mode: str) -> None:
    """Install as a Windows Scheduled Task."""
    python_exe = sys.executable
    clawtion_exe = os.path.join(os.path.dirname(python_exe), "clawtion.exe")
    if not os.path.exists(clawtion_exe):
        clawtion_exe = python_exe
        clawtion_args = "-m clawtion"
    else:
        clawtion_args = ""

    if mode == "background":
        # Continuous task
        cmd = (
            f'SCHTASKS /Create /TN "{_SERVICE_NAME}" /TR "{clawtion_exe} {clawtion_args} service start" '
            f"/SC ONLOGON /DELAY 0000:30 /F"
        )
    elif mode == "scheduled":
        # Hourly task
        cmd = (
            f'SCHTASKS /Create /TN "{_SERVICE_NAME}" /TR "{clawtion_exe} {clawtion_args} index now" '
            f"/SC HOURLY /F"
        )
    else:
        click.echo("  Manual mode: no OS service registered.")
        return

    subprocess.run(cmd, shell=True, capture_output=True, timeout=30)


def _uninstall_windows() -> None:
    """Remove Windows Scheduled Task."""
    cmd = f'SCHTASKS /Delete /TN "{_SERVICE_NAME}" /F'
    subprocess.run(cmd, shell=True, capture_output=True, timeout=30)


def _install_macos(mode: str) -> None:
    """Install as a macOS launchd agent."""
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)

    plist_path = plist_dir / f"com.clawtion.{_SERVICE_NAME}.plist"
    python_exe = sys.executable

    label = f"com.clawtion.{_SERVICE_NAME}"
    program_args = [python_exe, "-m", "clawtion"]

    if mode == "background":
        program_args.extend(["service", "start"])
        keep_alive = True
    elif mode == "scheduled":
        program_args.extend(["index", "now"])
        keep_alive = False
    else:
        click.echo("  Manual mode: no OS service registered.")
        return

    import plistlib
    plist: dict[str, Any] = {
        "Label": label,
        "ProgramArguments": program_args,
        "RunAtLoad": True,
        "KeepAlive": keep_alive,
        "StandardOutPath": str(Path.home() / ".clawtion" / "logs" / "service.log"),
        "StandardErrorPath": str(Path.home() / ".clawtion" / "logs" / "service.err"),
    }

    if mode == "scheduled":
        plist["StartInterval"] = 3600

    with plist_path.open("wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True, timeout=15)


def _uninstall_macos() -> None:
    """Remove macOS launchd agent."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"com.clawtion.{_SERVICE_NAME}.plist"
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, timeout=15)
        plist_path.unlink()


def _install_linux(mode: str) -> None:
    """Install as a Linux systemd user service."""
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    service_path = systemd_dir / f"{_SERVICE_NAME}.service"
    python_exe = sys.executable

    if mode == "background":
        service_content = (
            f"[Unit]\n"
            f"Description=clawtion background service\n\n"
            f"[Service]\n"
            f"ExecStart={python_exe} -m clawtion service start\n"
            f"Restart=always\n"
            f"RestartSec=10\n\n"
            f"[Install]\n"
            f"WantedBy=default.target\n"
        )
    elif mode == "scheduled":
        timer_dir = systemd_dir
        service_content = (
            f"[Unit]\n"
            f"Description=clawtion hourly indexing\n\n"
            f"[Service]\n"
            f"ExecStart={python_exe} -m clawtion index now\n"
            f"Type=oneshot\n"
        )
        timer_content = (
            "[Unit]\n"
            "Description=clawtion hourly indexing timer\n\n"
            "[Timer]\n"
            "OnCalendar=hourly\n"
            "Persistent=true\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
        (timer_dir / f"{_SERVICE_NAME}.timer").write_text(timer_content)
    else:
        click.echo("  Manual mode: no OS service registered.")
        return

    service_path.write_text(service_content)
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=15)
    subprocess.run(["systemctl", "--user", "enable", f"{_SERVICE_NAME}.service"], capture_output=True, timeout=15)


def _uninstall_linux() -> None:
    """Remove Linux systemd user service."""
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    for f in [f"{_SERVICE_NAME}.service", f"{_SERVICE_NAME}.timer"]:
        p = systemd_dir / f
        if p.exists():
            subprocess.run(
                ["systemctl", "--user", "disable", f],
                capture_output=True, timeout=15,
            )
            p.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=15)
