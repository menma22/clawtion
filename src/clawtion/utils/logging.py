"""Structured logging setup for clawtion.

Implements a three-layer logging architecture:
1. User-facing:   Console output in plain text (i18n-ready).
2. Developer:     JSON-structured log file in ~/.clawtion/logs/.
3. Claude-context: Diagnostic info returned via MCP tool results.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import structlog

_LOG_DIR_DEFAULT = Path.home() / ".clawtion" / "logs"


def _get_log_level() -> str:
    return os.environ.get("CLAWTION_LOG_LEVEL", "INFO").upper()


def _ensure_log_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _create_file_handler(log_dir: Path, level: str) -> logging.Handler:
    """Create a rotating file handler for JSON-structured logs."""
    handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_dir / "clawtion.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    handler.setLevel(level)
    return handler


def setup_logging(log_dir: str | Path | None = None, level: str | None = None) -> None:
    """Configure the three-layer logging system.

    Must be called once at application startup.

    Args:
        log_dir: Directory for log files. Defaults to ~/.clawtion/logs/.
        level:   Minimum log level. Defaults to CLAWTION_LOG_LEVEL env or INFO.
    """
    resolved_level = (level or _get_log_level()).upper()
    resolved_log_dir = _ensure_log_dir(Path(log_dir) if log_dir else _LOG_DIR_DEFAULT)

    # ------------------------------------------------------------------
    # Timestamper shared processor
    # ------------------------------------------------------------------
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    # ------------------------------------------------------------------
    # Pre-chain: processors that run on every event regardless of output
    # ------------------------------------------------------------------
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # ------------------------------------------------------------------
    # Standard library logging configuration
    # ------------------------------------------------------------------
    file_handler = _create_file_handler(resolved_log_dir, resolved_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(resolved_level)

    # Configure root logger to accept everything; handlers filter per-level
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG,
        handlers=[console_handler, file_handler],
    )

    # Quiet noisy third-party loggers
    logging.getLogger("alembic").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # ------------------------------------------------------------------
    # structlog configuration
    # ------------------------------------------------------------------
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True, pad_event=25),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Separate processor chain for the JSON file handler
    json_processor = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )

    file_handler.setFormatter(json_processor)

    # Make the console logger also use structlog's rendering
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=True, pad_event=25),
        ],
        foreign_pre_chain=shared_processors,
    )

    console_handler.setFormatter(console_formatter)

    # Add console handler to root logger
    logging.getLogger().addHandler(console_handler)

    # Suppress duplicate log output from structlog
    logging.getLogger("structlog").setLevel(logging.WARNING)


def get_logger(name: str = "clawtion") -> structlog.stdlib.BoundLogger:
    """Return a structlog logger for the given name.

    This is the main entry point for all application logging.
    """
    return structlog.get_logger(name)
