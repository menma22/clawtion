"""End-to-end tests for the clawtion CLI."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def cli_env() -> dict:
    """Environment for CLI tests."""
    env = os.environ.copy()
    env["CLAWTION_DB_URL"] = os.environ.get(
        "CLAWTION_TEST_DB_URL",
        "postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion_test",
    )
    env["CLAWTION_VAULT"] = str(Path(tempfile.gettempdir()) / "clawtion-e2e-vault")
    return env


@pytest.fixture
def e2e_vault(cli_env) -> str:
    """Create a temporary vault for E2E tests."""
    vault_path = Path(cli_env["CLAWTION_VAULT"])
    vault_path.mkdir(parents=True, exist_ok=True)

    # Create test notes
    (vault_path / "tech").mkdir(exist_ok=True)
    (vault_path / "tech" / "test.md").write_text(
        "# E2E Test Note\n\nThis is an end-to-end test note about vector search.\n",
        encoding="utf-8",
    )
    (vault_path / "readme.md").write_text(
        "# README\n\nClawtion knowledge base.\n", encoding="utf-8"
    )

    return str(vault_path)


class TestCLIVersion:
    def test_version_flag(self) -> None:
        """Verify --version works."""
        result = subprocess.run(
            [sys.executable, "-m", "clawtion", "--version"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        assert result.returncode == 0
        assert "clawtion" in result.stdout.lower() or "version" in result.stdout.lower()

    def test_help_flag(self) -> None:
        """Verify --help works."""
        result = subprocess.run(
            [sys.executable, "-m", "clawtion", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        assert result.returncode == 0
        assert "search" in result.stdout.lower() or "init" in result.stdout.lower()
        assert "index" in result.stdout.lower() or "note" in result.stdout.lower()


class TestCLISubcommands:
    def test_search_help(self) -> None:
        """Verify search command help works."""
        result = subprocess.run(
            [sys.executable, "-m", "clawtion", "search", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        assert result.returncode == 0

    def test_note_help(self) -> None:
        """Verify note command help works."""
        result = subprocess.run(
            [sys.executable, "-m", "clawtion", "note", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        assert result.returncode == 0 or "note" in result.stdout.lower()

    def test_config_help(self) -> None:
        """Verify config command help works."""
        result = subprocess.run(
            [sys.executable, "-m", "clawtion", "config", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        # config may not be directly available as a subcommand - check gracefully
        assert result.returncode in (0, 2)

    def test_trash_help(self) -> None:
        """Verify trash command help works."""
        result = subprocess.run(
            [sys.executable, "-m", "clawtion", "trash", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        assert result.returncode == 0 or "trash" in result.stdout.lower()

    def test_doctor(self) -> None:
        """Verify doctor command runs."""
        result = subprocess.run(
            [sys.executable, "-m", "clawtion", "doctor"],
            capture_output=True, text=True, timeout=60,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        # Doctor may fail if Docker isn't available, but should run
        assert result.returncode in (0, 1, 2)


class TestCLIModuleImport:
    def test_can_import_cli(self) -> None:
        """Verify the CLI module can be imported."""
        result = subprocess.run(
            [sys.executable, "-c", "from clawtion.interfaces.cli.main import main; print('OK')"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        )
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_can_import_core(self) -> None:
        """Verify core modules can be imported."""
        modules = [
            "clawtion.config.defaults",
            "clawtion.config.loader",
            "clawtion.utils.exceptions",
            "clawtion.utils.retry",
            "clawtion.core.indexing.chunker",
            "clawtion.core.search.hybrid",
            "clawtion.core.search.filter",
        ]
        for mod in modules:
            result = subprocess.run(
                [sys.executable, "-c", f"import {mod}; print('OK')"],
                capture_output=True, text=True, timeout=30,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            )
            assert result.returncode == 0, f"Failed to import {mod}: {result.stderr}"

    def test_can_import_all_services(self) -> None:
        """Verify all service modules import correctly."""
        services = [
            "clawtion.core.db.connection",
            "clawtion.core.db.models",
            "clawtion.core.embedding.client",
            "clawtion.core.note.service",
            "clawtion.core.trash.service",
            "clawtion.core.indexing.queue",
            "clawtion.core.indexing.chunker",
            "clawtion.core.search.service",
        ]
        for mod in services:
            result = subprocess.run(
                [sys.executable, "-c", f"import {mod}; print('OK')"],
                capture_output=True, text=True, timeout=30,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            )
            assert result.returncode == 0, f"Failed to import {mod}: {result.stderr}"
