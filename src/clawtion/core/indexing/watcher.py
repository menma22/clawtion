"""ファイルシステム監視モジュール。

watchdog ライブラリを使用して Vault フォルダの変更を監視し、
作成・変更・削除イベントを indexing キューに追加する。
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from clawtion.utils.exceptions import ClawtionError
from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from .queue import QueueManager

logger = get_logger(__name__)

# watchdog の遅延インポート（インストールされていない場合のフォールバック）
try:
    from watchdog.events import (
        FileCreatedEvent,
        FileDeletedEvent,
        FileModifiedEvent,
        FileMovedEvent,
        FileSystemEventHandler,
    )
    from watchdog.observers import Observer

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    logger.warning("watchdog is not installed. FileWatcher will use polling fallback.")


# ---- サポートされるファイル拡張子 ----

_SUPPORTED_EXTENSIONS: set[str] = {
    ".md",
    ".txt",
    ".rst",
    ".html",
    ".htm",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".xml",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".rs",
    ".go",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    ".sql",
    ".r",
    ".tex",
    ".org",
    ".adoc",
    ".asciidoc",
    ".log",
}


def _is_supported_file(file_path: str) -> bool:
    """サポートされているファイル拡張子かどうかを判定する。"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in _SUPPORTED_EXTENSIONS


def _should_exclude(file_path: str, exclude_folders: list[str]) -> bool:
    """除外フォルダに含まれているかどうかを判定する。"""
    path = Path(file_path)
    for exclude in exclude_folders:
        exclude_path = Path(exclude)
        try:
            path.relative_to(exclude_path)
            return True
        except ValueError:
            continue
    return False


# ---- Watchdog Event Handler ----


class _ClawtionEventHandler(FileSystemEventHandler):
    """Watchdog イベントハンドラ。

    ファイルの作成・変更・削除・移動を監視し、キューに追加する。
    """

    def __init__(
        self,
        queue_manager: QueueManager,
        vault_path: str,
        exclude_folders: list[str] | None = None,
    ) -> None:
        self._queue = queue_manager
        self._vault_path = vault_path
        self._exclude = exclude_folders or []
        self._debounce: dict[str, float] = {}
        self._debounce_seconds: float = 2.0

    def _get_relative_path(self, file_path: str) -> str:
        """絶対パスを Vault 相対パスに変換する。"""
        try:
            return str(Path(file_path).relative_to(Path(self._vault_path)))
        except ValueError:
            return file_path

    def _is_debounced(self, file_path: str) -> bool:
        """デバウンスチェック。同一パスの連続イベントを間引く。"""
        now = time.time()
        last = self._debounce.get(file_path, 0.0)
        if now - last < self._debounce_seconds:
            return True
        self._debounce[file_path] = now
        return False

    def on_created(self, event: FileCreatedEvent) -> None:
        """ファイル作成時。"""
        if event.is_directory:
            return
        if not _is_supported_file(event.src_path):
            return
        if _should_exclude(event.src_path, self._exclude):
            return
        if self._is_debounced(event.src_path):
            return

        rel_path = self._get_relative_path(event.src_path)
        logger.info("File created, enqueuing for indexing", file_path=rel_path)
        # document_id はサービス層で解決するため、ここでは空文字
        import asyncio

        asyncio.ensure_future(self._queue.enqueue("", rel_path, operation="index"))

    def on_modified(self, event: FileModifiedEvent) -> None:
        """ファイル変更時。"""
        if event.is_directory:
            return
        if not _is_supported_file(event.src_path):
            return
        if _should_exclude(event.src_path, self._exclude):
            return
        if self._is_debounced(event.src_path):
            return

        rel_path = self._get_relative_path(event.src_path)
        logger.info("File modified, enqueuing for reindex", file_path=rel_path)
        import asyncio

        asyncio.ensure_future(self._queue.enqueue("", rel_path, operation="index"))

    def on_deleted(self, event: FileDeletedEvent) -> None:
        """ファイル削除時。"""
        if event.is_directory:
            return
        if not _is_supported_file(event.src_path):
            return

        rel_path = self._get_relative_path(event.src_path)
        logger.info("File deleted, enqueuing for removal", file_path=rel_path)
        import asyncio

        asyncio.ensure_future(self._queue.enqueue("", rel_path, operation="delete"))

    def on_moved(self, event: FileMovedEvent) -> None:
        """ファイル移動/リネーム時。"""
        if event.is_directory:
            return
        if not _is_supported_file(event.dest_path):
            return

        src_rel = self._get_relative_path(event.src_path)
        dest_rel = self._get_relative_path(event.dest_path)
        logger.info("File moved, enqueuing for update", src=src_rel, dest=dest_rel)
        import asyncio

        asyncio.ensure_future(self._queue.enqueue("", src_rel, operation="delete"))
        asyncio.ensure_future(self._queue.enqueue("", dest_rel, operation="index"))


# ---- FileWatcher ----


class FileWatcher:
    """Vault フォルダのファイル変更を監視する。

    使用方法::

        watcher = FileWatcher("/path/to/vault", queue_manager)
        watcher.start()
        # ...
        watcher.stop()
    """

    def __init__(
        self,
        vault_path: str,
        queue_manager: QueueManager,
        exclude_folders: list[str] | None = None,
    ) -> None:
        self._vault_path = vault_path
        self._queue = queue_manager
        self._exclude = exclude_folders or []
        self._observer: Observer | None = None

    def start(self) -> None:
        """ファイル監視を開始する。"""
        if not _WATCHDOG_AVAILABLE:
            logger.warning(
                "watchdog not available. Install with: pip install watchdog"
            )
            return

        if self._observer is not None and self._observer.is_alive():
            logger.warning("FileWatcher is already running")
            return

        if not os.path.isdir(self._vault_path):
            logger.error(
                "Vault path does not exist, cannot start watcher",
                path=self._vault_path,
            )
            raise ClawtionError(
    code="VAULT_NOT_FOUND",
    message=f"Vault path not found: {self._vault_path}",
)

        event_handler = _ClawtionEventHandler(
            self._queue, self._vault_path, self._exclude
        )
        self._observer = Observer()
        self._observer.schedule(event_handler, self._vault_path, recursive=True)
        self._observer.start()
        logger.info("FileWatcher started", vault_path=self._vault_path)

    def stop(self) -> None:
        """ファイル監視を停止する。"""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("FileWatcher stopped")

    def is_running(self) -> bool:
        """ファイル監視が動作中かどうかを返す。"""
        return self._observer is not None and self._observer.is_alive()
