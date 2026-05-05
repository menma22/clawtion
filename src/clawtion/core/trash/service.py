"""ゴミ箱管理サービスの実装。

削除されたファイルの一時保管・復元・自動パージを管理する。
``trash`` テーブルを使用し、``auto_purge_at`` に基づいて
自動削除を実行する。
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from clawtion.utils.exceptions import ClawtionError
from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager

logger = get_logger(__name__)


class TrashService:
    """ゴミ箱サービスクラス。

    削除されたファイルの一覧表示・復元・完全削除・期限切れパージを提供する。
    Constructor DI で DatabaseManager と vault_path を受け取る。
    """

    def __init__(self, db: DatabaseManager, vault_path: str) -> None:
        self._db = db
        self._vault_path = vault_path

    async def list_items(self) -> list[dict[str, Any]]:
        """ゴミ箱内の全アイテムを一覧表示する。

        Returns:
            削除日時の降順でソートされたゴミ箱アイテムのリスト
        """
        query = """
            SELECT
                trash_id,
                original_document_id,
                original_file_path,
                original_metadata,
                deleted_at,
                auto_purge_at
            FROM trash
            ORDER BY deleted_at DESC
            LIMIT 1000
        """
        rows = await self._db.execute(query, {})

        results: list[dict[str, Any]] = []
        for row in rows:
            metadata: dict[str, Any] = {}
            if row.get("original_metadata"):
                metadata = (
                    row["original_metadata"]
                    if isinstance(row["original_metadata"], dict)
                    else json.loads(row["original_metadata"])
                )

            results.append({
                "trash_id": row["trash_id"],
                "original_document_id": row["original_document_id"],
                "original_file_path": row["original_file_path"],
                "original_metadata": metadata,
                "deleted_at": (
                    row["deleted_at"].isoformat()
                    if hasattr(row["deleted_at"], "isoformat")
                    else row["deleted_at"]
                ),
                "auto_purge_at": (
                    row["auto_purge_at"].isoformat()
                    if hasattr(row["auto_purge_at"], "isoformat")
                    else row["auto_purge_at"]
                ),
            })

        return results

    async def restore(self, trash_id: str) -> dict[str, Any]:
        """ゴミ箱からアイテムを復元する。

        1. trash テーブルからレコードを取得
        2. 元のファイルを復元（既存ファイルがあればバックアップ）
        3. documents テーブルにレコードを復元（is_deleted = false に更新）
        4. trash テーブルからレコードを削除

        Args:
            trash_id: 復元するゴミ箱アイテムの UUID

        Returns:
            復元されたドキュメント情報の dict
                ``{"document_id": str, "file_path": str, "title": str}``

        Raises:
            ClawtionError: ゴミ箱アイテムが見つからない場合
        """
        query = """
            SELECT
                trash_id,
                original_document_id,
                original_file_path,
                original_content,
                original_metadata
            FROM trash
            WHERE trash_id = :trash_id
        """
        row = await self._db.execute_one(query, {"trash_id": trash_id})

        if row is None:
            raise ClawtionError(
                code="TRASH_ITEM_NOT_FOUND",
                message=f"Trash item not found: {trash_id}",
            )

        document_id = row["original_document_id"]
        file_path = row["original_file_path"]
        content = row["original_content"]
        if row.get("original_metadata"):
            (
                row["original_metadata"]
                if isinstance(row["original_metadata"], dict)
                else json.loads(row["original_metadata"])
            )

        # ファイルを復元
        abs_path = os.path.join(self._vault_path, file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        # 既存ファイルがあればバックアップ
        if os.path.exists(abs_path):
            backup_path = abs_path + ".bak." + datetime.now().strftime("%Y%m%d%H%M%S")
            shutil.copy2(abs_path, backup_path)
            logger.warning(
                "Existing file backed up during restore",
                file_path=file_path,
                backup=backup_path,
            )

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        # documents テーブルを復元
        update_query = """
            UPDATE documents
            SET is_deleted = false,
                deleted_at = NULL,
                updated_at = NOW()
            WHERE document_id = :document_id
        """
        await self._db.execute(update_query, {"document_id": document_id})

        # trash から削除
        delete_query = """
            DELETE FROM trash
            WHERE trash_id = :trash_id
        """
        await self._db.execute(delete_query, {"trash_id": trash_id})

        title = Path(file_path).stem
        logger.info(
            "Restored document from trash",
            document_id=document_id,
            file_path=file_path,
        )

        return {
            "document_id": document_id,
            "file_path": file_path,
            "title": title,
        }

    async def empty(self) -> int:
        """ゴミ箱を空にする（全アイテムを物理削除）。

        Returns:
            削除されたアイテム数
        """
        query = """
            WITH deleted AS (
                DELETE FROM trash
                RETURNING trash_id
            )
            SELECT count(*) as cnt FROM deleted
        """
        row = await self._db.execute_one(query, {})
        count = row["cnt"] if row else 0

        logger.info("Emptied trash", deleted_count=count)
        return count

    async def purge_expired(self) -> int:
        """期限切れのゴミ箱アイテムを削除する。

        ``auto_purge_at`` が現在時刻より前のアイテムを物理削除する。

        Returns:
            削除されたアイテム数
        """
        now = datetime.now(UTC).isoformat()

        query = """
            WITH expired AS (
                DELETE FROM trash
                WHERE auto_purge_at <= :now::timestamptz
                RETURNING trash_id
            )
            SELECT count(*) as cnt FROM expired
        """
        row = await self._db.execute_one(query, {"now": now})
        count = row["cnt"] if row else 0

        if count > 0:
            logger.info("Purged expired trash items", deleted_count=count)

        return count
