"""Indexing キュー管理モジュール。

``indexing_queue`` テーブルを操作し、ファイルの index / reindex / delete
操作を非同期キューで管理する。中断・再開に対応した進捗管理を提供する。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager

logger = get_logger(__name__)


class QueueManager:
    """Indexing キューの管理を行う。

    キューは ``indexing_queue`` テーブルを使用し、以下のステータス遷移を持つ::

        pending → processing → completed
                      ↓
                    partial
                      ↓
                  processing → completed

        failed (リトライ上限超過)
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def enqueue(
        self,
        document_id: str,
        file_path: str,
        operation: str = "index",
    ) -> str:
        """キューにジョブを追加する。

        Args:
            document_id: 対象ドキュメントの UUID（空文字の場合は自動解決）
            file_path: ファイルの Vault 相対パス
            operation: 操作種別（'index' / 'reindex' / 'delete'）

        Returns:
            作成されたキューアイテムの queue_id
        """
        # document_id が空の場合は既存ドキュメントから解決
        resolved_doc_id = document_id
        if not document_id:
            existing = await self._db.execute_one(
                """SELECT document_id FROM documents
                   WHERE file_path = :file_path AND is_deleted = false""",
                {"file_path": file_path},
            )
            resolved_doc_id = existing["document_id"] if existing else str(uuid.uuid4())

        queue_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        query = """
            INSERT INTO indexing_queue
                (queue_id, document_id, file_path, operation, status, progress,
                 created_at, started_at, completed_at)
            VALUES (:queue_id, :document_id, :file_path, :operation, 'pending',
                    '{}'::jsonb, :created_at, NULL, NULL)
        """
        await self._db.execute(
            query,
            {
                "queue_id": queue_id,
                "document_id": resolved_doc_id,
                "file_path": file_path,
                "operation": operation,
                "created_at": now,
            },
        )

        logger.info(
            "Enqueued indexing job",
            queue_id=queue_id,
            document_id=document_id,
            operation=operation,
        )
        return queue_id

    async def dequeue(self) -> dict[str, Any] | None:
        """最も優先度の高い pending ジョブを取得し、processing に更新する。

        Returns:
            ジョブ情報の dict、ない場合は None
        """
        now = datetime.now(UTC)

        # トランザクション内で SELECT ... FOR UPDATE SKIP LOCKED
        query = """
            WITH next_job AS (
                SELECT queue_id, document_id, file_path, operation, status,
                       progress, retry_count, max_retries
                FROM indexing_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE indexing_queue
            SET status = 'processing',
                started_at = :now
            WHERE queue_id = (SELECT queue_id FROM next_job)
            RETURNING queue_id, document_id, file_path, operation, status,
                      progress, retry_count, max_retries
        """
        row = await self._db.execute_one(query, {"now": now})
        if row is None:
            return None

        return {
            "queue_id": row["queue_id"],
            "document_id": row["document_id"],
            "file_path": row["file_path"],
            "operation": row["operation"],
            "status": row["status"],
            "progress": row["progress"] if isinstance(row["progress"], dict) else json.loads(row["progress"] or "{}"),
            "retry_count": row["retry_count"],
            "max_retries": row["max_retries"],
        }

    async def update_status(self, queue_id: str, status: str, error: str | None = None) -> None:
        """キューアイテムのステータスを更新する。

        Args:
            queue_id: 更新対象の queue_id
            status: 新しいステータス
            error: エラーメッセージ（失敗時の last_error）
        """
        now = datetime.now(UTC)

        completed_at_part = ""
        params: dict[str, Any] = {
            "queue_id": queue_id,
            "status": status,
            "now": now,
        }

        if status == "completed" or status == "failed":
            completed_at_part = ", completed_at = :now"

        if error is not None:
            error_history_entry = json.dumps([{"timestamp": now, "error": error}])
            query = f"""
                UPDATE indexing_queue
                SET status = :status,
                    last_error = :error,
                    error_history = COALESCE(error_history, '[]'::jsonb) || CAST(:error_history AS jsonb),
                    retry_count = retry_count + 1{completed_at_part}
                WHERE queue_id = :queue_id
            """
            params["error"] = error
            params["error_history"] = error_history_entry
        else:
            query = f"""
                UPDATE indexing_queue
                SET status = :status,
                    last_error = NULL{completed_at_part}
                WHERE queue_id = :queue_id
            """

        await self._db.execute(query, params)

        logger.debug(
            "Updated queue status",
            queue_id=queue_id,
            status=status,
            error=error,
        )

    async def update_progress(self, queue_id: str, progress: dict[str, Any]) -> None:
        """キューアイテムの進捗を更新する。中断・再開用。

        Args:
            queue_id: 更新対象の queue_id
            progress: 進捗情報の dict
        """
        progress_json = json.dumps(progress)
        query = """
            UPDATE indexing_queue
            SET progress = CAST(:progress AS jsonb),
                status = CASE WHEN status = 'processing' THEN 'partial' ELSE status END
            WHERE queue_id = :queue_id
        """
        await self._db.execute(query, {"queue_id": queue_id, "progress": progress_json})

        logger.debug("Updated queue progress", queue_id=queue_id, progress=progress)

    async def get_pending(self) -> list[dict[str, Any]]:
        """保留中のジョブ一覧を取得する。"""
        query = """
            SELECT queue_id, document_id, file_path, operation, status,
                   progress, retry_count, max_retries, created_at, started_at
            FROM indexing_queue
            WHERE status IN ('pending', 'partial')
            ORDER BY priority DESC, created_at ASC
        """
        rows = await self._db.execute(query, {})
        return [
            {
                "queue_id": row["queue_id"],
                "document_id": row["document_id"],
                "file_path": row["file_path"],
                "operation": row["operation"],
                "status": row["status"],
                "progress": row["progress"]
                if isinstance(row["progress"], dict)
                else json.loads(row["progress"] or "{}"),
                "retry_count": row["retry_count"],
                "max_retries": row["max_retries"],
                "created_at": row["created_at"].isoformat()
                if hasattr(row["created_at"], "isoformat")
                else row["created_at"],
            }
            for row in rows
        ]

    async def get_failed(self) -> list[dict[str, Any]]:
        """失敗したジョブ一覧を取得する。"""
        query = """
            SELECT queue_id, document_id, file_path, operation, status,
                   progress, retry_count, max_retries, last_error, error_history,
                   created_at, started_at, completed_at
            FROM indexing_queue
            WHERE status = 'failed'
            ORDER BY completed_at DESC
            LIMIT 100
        """
        rows = await self._db.execute(query, {})
        return [
            {
                "queue_id": row["queue_id"],
                "document_id": row["document_id"],
                "file_path": row["file_path"],
                "operation": row["operation"],
                "status": row["status"],
                "retry_count": row["retry_count"],
                "max_retries": row["max_retries"],
                "last_error": row["last_error"],
                "error_history": json.loads(row["error_history"])
                if isinstance(row.get("error_history"), str)
                else (row.get("error_history") or []),
                "created_at": row["created_at"].isoformat()
                if hasattr(row["created_at"], "isoformat")
                else row["created_at"],
                "started_at": row["started_at"].isoformat()
                if row.get("started_at") and hasattr(row["started_at"], "isoformat")
                else row.get("started_at"),
                "completed_at": row["completed_at"].isoformat()
                if row.get("completed_at") and hasattr(row["completed_at"], "isoformat")
                else row.get("completed_at"),
            }
            for row in rows
        ]

    async def retry(self, queue_id: str) -> None:
        """失敗したジョブをリトライ可能状態に戻す。"""
        query = """
            UPDATE indexing_queue
            SET status = 'pending',
                started_at = NULL,
                completed_at = NULL
            WHERE queue_id = :queue_id
              AND status = 'failed'
        """
        await self._db.execute(query, {"queue_id": queue_id})
        logger.info("Retrying queue item", queue_id=queue_id)

    async def clear_failed(self) -> int:
        """失敗したジョブをすべて削除する。

        Returns:
            削除された件数
        """
        query = """
            WITH deleted AS (
                DELETE FROM indexing_queue
                WHERE status = 'failed'
                RETURNING queue_id
            )
            SELECT count(*) as cnt FROM deleted
        """
        row = await self._db.execute_one(query, {})
        count = row["cnt"] if row else 0
        logger.info("Cleared failed queue items", count=count)
        return count

    async def get_stats(self) -> dict[str, int]:
        """キューの統計情報を取得する。"""
        query = """
            SELECT
                COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) AS pending,
                COALESCE(SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END), 0) AS processing,
                COALESCE(SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END), 0) AS partial,
                COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) AS completed,
                COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS failed
            FROM indexing_queue
        """
        row = await self._db.execute_one(query, {})
        if row is None:
            return {
                "pending": 0,
                "processing": 0,
                "partial": 0,
                "completed": 0,
                "failed": 0,
            }
        return {
            "pending": row["pending"],
            "processing": row["processing"],
            "partial": row["partial"],
            "completed": row["completed"],
            "failed": row["failed"],
        }
