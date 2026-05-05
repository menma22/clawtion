"""ノート CRUD サービスの実装。

.md ファイルをプライマリストレージとして、そのメタデータを DB で管理する。
ファイル作成・編集・削除時に自動的に IndexingService に通知する。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from clawtion.utils.exceptions import (
    ClawtionError,
    DocumentNotFoundError,
)
from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.indexing.service import IndexingService

logger = get_logger(__name__)

# サポートするノートファイル拡張子
NOTE_EXTENSIONS: set[str] = {".md", ".txt", ".rst"}


class NoteService:
    """ノート CRUD サービスクラス。

    ファイルシステム上のノートファイルと、DB 上のメタデータを統合管理する。
    作成・更新時に IndexingService に自動通知する。

    Constructor DI:
        ``db``: データベース接続
        ``vault_path``: Vault フォルダの絶対パス
        ``indexing_service``: 自動 indexing 用
    """

    def __init__(
        self,
        db: DatabaseManager,
        vault_path: str,
        indexing_service: IndexingService,
    ) -> None:
        self._db = db
        self._vault_path = vault_path
        self._indexing = indexing_service

    async def create(
        self,
        title: str,
        content: str,
        folder: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """新規ノートを作成する。

        1. Vault 内に .md ファイルを作成
        2. documents テーブルにレコードを挿入
        3. 自動 indexing をトリガー

        Args:
            title: ノートのタイトル（ファイル名のベースになる）
            content: ノートの本文（Markdown）
            folder: Vault 内のフォルダパス（例: ``"tech/rag"``）
            tags: タグのリスト

        Returns:
            作成されたノート情報の dict
                ``{"document_id": str, "file_path": str, "title": str}``
        """
        document_id = str(uuid.uuid4())
        sanitized_title = self._sanitize_filename(title)
        file_name = f"{sanitized_title}.md"
        file_path = os.path.join(folder, file_name) if folder else file_name
        abs_path = os.path.join(self._vault_path, file_path)
        folder_path = f"{folder}/" if folder else ""

        # ファイルが既に存在するかチェック
        if os.path.exists(abs_path):
            raise ClawtionError(
                code="FILE_EXISTS",
                message=f"File already exists: {file_path}. Use update instead.",
            )

        # ファイルを作成
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        file_content = self._build_note_content(content, tags=tags)
        file_bytes = file_content.encode("utf-8")

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        now = datetime.now(UTC).isoformat()

        # DB に挿入
        query = """
            INSERT INTO documents (
                document_id, file_path, folder_path, title,
                file_extension, file_size_bytes, content_hash,
                tags, metadata, created_at, updated_at
            ) VALUES (
                :document_id, :file_path, :folder_path, :title,
                :file_extension, :file_size_bytes, :content_hash,
                :tags::jsonb, :metadata::jsonb, :created_at, :created_at
            )
        """
        await self._db.execute(
            query,
            {
                "document_id": document_id,
                "file_path": file_path,
                "folder_path": folder_path,
                "title": title,
                "file_extension": ".md",
                "file_size_bytes": len(file_bytes),
                "content_hash": content_hash,
                "tags": json.dumps(tags or [], ensure_ascii=False),
                "metadata": "{}",
                "created_at": now,
            },
        )

        # 自動 indexing をトリガー
        try:
            await self._indexing.index_file(abs_path)
        except Exception as e:
            logger.warning(
                "Note created but indexing failed",
                document_id=document_id,
                error=str(e),
            )

        logger.info("Note created", document_id=document_id, title=title, folder=folder)
        return {
            "document_id": document_id,
            "file_path": file_path,
            "title": title,
        }

    async def get(self, document_id: str) -> dict[str, Any]:
        """指定されたノートの情報を取得する。"""
        query = """
            SELECT
                document_id, file_path, folder_path, title,
                file_extension, file_size_bytes, content_hash,
                tags, metadata, total_chunks, last_indexed_at,
                created_at, updated_at
            FROM documents
            WHERE document_id = :document_id
              AND is_deleted = false
        """
        row = await self._db.execute_one(query, {"document_id": document_id})
        if row is None:
            raise DocumentNotFoundError(document_id=document_id)

        # ファイル本文も読み込む
        abs_path = os.path.join(self._vault_path, row["file_path"])
        content = ""
        try:
            if os.path.exists(abs_path):
                with open(abs_path, encoding="utf-8") as f:
                    content = f.read()
        except (OSError, PermissionError) as e:
            logger.warning("Failed to read note file", file_path=abs_path, error=str(e))

        return {
            "document_id": row["document_id"],
            "file_path": row["file_path"],
            "folder_path": row["folder_path"],
            "title": row["title"],
            "file_extension": row["file_extension"],
            "file_size_bytes": row["file_size_bytes"],
            "content_hash": row["content_hash"],
            "tags": row["tags"] if isinstance(row["tags"], list) else json.loads(row["tags"] or "[]"),
            "metadata": row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}"),
            "total_chunks": row["total_chunks"],
            "content": content,
            "last_indexed_at": (
                row["last_indexed_at"].isoformat()
                if hasattr(row["last_indexed_at"], "isoformat")
                else row["last_indexed_at"]
            ),
            "created_at": (
                row["created_at"].isoformat()
                if hasattr(row["created_at"], "isoformat")
                else row["created_at"]
            ),
            "updated_at": (
                row["updated_at"].isoformat()
                if hasattr(row["updated_at"], "isoformat")
                else row["updated_at"]
            ),
        }

    async def update(self, document_id: str, content: str) -> dict[str, Any]:
        """ノートの内容を更新する。"""
        # 現在のドキュメント情報を取得
        row = await self._db.execute_one(
            """
            SELECT file_path, title FROM documents
            WHERE document_id = :document_id AND is_deleted = false
            """,
            {"document_id": document_id},
        )
        if row is None:
            raise DocumentNotFoundError(document_id=document_id)

        file_path = row["file_path"]
        abs_path = os.path.join(self._vault_path, file_path)

        # ファイルを更新
        file_bytes = content.encode("utf-8")
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        now = datetime.now(UTC).isoformat()

        # DB を更新
        await self._db.execute(
            """
            UPDATE documents
            SET content_hash = :content_hash,
                file_size_bytes = :file_size_bytes,
                updated_at = :now
            WHERE document_id = :document_id
            """,
            {
                "document_id": document_id,
                "content_hash": content_hash,
                "file_size_bytes": len(file_bytes),
                "now": now,
            },
        )

        # 自動再 indexing
        try:
            await self._indexing.reindex_file(abs_path)
        except Exception as e:
            logger.warning(
                "Note updated but indexing failed",
                document_id=document_id,
                error=str(e),
            )

        logger.info("Note updated", document_id=document_id)
        return {
            "document_id": document_id,
            "file_path": file_path,
            "title": row["title"],
            "content_hash": content_hash,
        }

    async def delete(
        self, document_id: str, permanent: bool = False
    ) -> dict[str, Any]:
        """ノートを削除する。

        Args:
            document_id: 削除するノートの UUID
            permanent: True の場合は完全削除（ファイルも削除）、
                       False の場合は論理削除（is_deleted = true）

        Returns:
            削除されたノートの情報
        """
        row = await self._db.execute_one(
            """
            SELECT document_id, file_path, title, content_hash, folder_path, metadata
            FROM documents
            WHERE document_id = :document_id AND is_deleted = false
            """,
            {"document_id": document_id},
        )
        if row is None:
            raise DocumentNotFoundError(document_id=document_id)

        file_path = row["file_path"]
        abs_path = os.path.join(self._vault_path, file_path)

        if permanent:
            # 完全削除: ファイルも削除
            if os.path.exists(abs_path):
                os.remove(abs_path)

            await self._db.execute(
                "DELETE FROM documents WHERE document_id = :document_id",
                {"document_id": document_id},
            )
            logger.info("Note permanently deleted", document_id=document_id)
        else:
            # 論理削除: ゴミ箱へ
            now = datetime.now(UTC).isoformat()

            # ファイル内容を保存
            file_content = ""
            if os.path.exists(abs_path):
                with open(abs_path, encoding="utf-8") as f:
                    file_content = f.read()

            # trash テーブルに挿入
            from datetime import timedelta

            purge_at = (
                datetime.now(UTC) + timedelta(days=7)
            ).isoformat()

            await self._db.execute(
                """
                INSERT INTO trash
                    (original_document_id, original_file_path,
                     original_content, original_metadata, auto_purge_at)
                VALUES
                    (:document_id, :file_path,
                     :content, :metadata::jsonb, :purge_at::timestamptz)
                """,
                {
                    "document_id": document_id,
                    "file_path": file_path,
                    "content": file_content,
                    "metadata": json.dumps(
                        row["metadata"] if isinstance(row["metadata"], dict) else {},
                        ensure_ascii=False,
                    ),
                    "purge_at": purge_at,
                },
            )

            # 論理削除
            await self._db.execute(
                """
                UPDATE documents
                SET is_deleted = true, deleted_at = :now
                WHERE document_id = :document_id
                """,
                {"document_id": document_id, "now": now},
            )

            # チャンク削除
            await self._db.execute(
                "DELETE FROM document_chunks WHERE document_id = :document_id",
                {"document_id": document_id},
            )

            logger.info("Note moved to trash", document_id=document_id)

        return {
            "document_id": document_id,
            "file_path": file_path,
            "title": row["title"],
            "permanent": permanent,
        }

    async def list_notes(
        self,
        folder: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """ノート一覧を取得する。"""
        filter_clause = ""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if folder is not None:
            filter_clause = " AND d.folder_path = :folder"
            params["folder"] = folder

        query = f"""
            SELECT
                d.document_id, d.file_path, d.folder_path, d.title,
                d.file_extension, d.file_size_bytes, d.content_hash,
                d.tags, d.total_chunks, d.last_indexed_at,
                d.created_at, d.updated_at
            FROM documents d
            WHERE d.is_deleted = false
              {filter_clause}
            ORDER BY d.updated_at DESC
            LIMIT :limit
            OFFSET :offset
        """
        rows = await self._db.execute(query, params)
        return [
            {
                "document_id": row["document_id"],
                "file_path": row["file_path"],
                "folder_path": row["folder_path"],
                "title": row["title"],
                "file_extension": row["file_extension"],
                "file_size_bytes": row["file_size_bytes"],
                "content_hash": row["content_hash"],
                "tags": row["tags"] if isinstance(row["tags"], list) else json.loads(row.get("tags") or "[]"),
                "total_chunks": row["total_chunks"],
                "last_indexed_at": (
                    row["last_indexed_at"].isoformat()
                    if hasattr(row["last_indexed_at"], "isoformat")
                    else row["last_indexed_at"]
                ),
                "created_at": (
                    row["created_at"].isoformat()
                    if hasattr(row["created_at"], "isoformat")
                    else row["created_at"]
                ),
                "updated_at": (
                    row["updated_at"].isoformat()
                    if hasattr(row["updated_at"], "isoformat")
                    else row["updated_at"]
                ),
            }
            for row in rows
        ]

    async def list_folders(self) -> list[str]:
        """Vault 内のユニークなフォルダパス一覧を取得する。"""
        query = """
            SELECT DISTINCT folder_path
            FROM documents
            WHERE is_deleted = false
            ORDER BY folder_path
        """
        rows = await self._db.execute(query, {})
        return [row["folder_path"] for row in rows if row["folder_path"]]

    # ---- 内部ヘルパー ----

    def _sanitize_filename(self, title: str) -> str:
        """ファイル名として使用できない文字を除去する。"""
        # Windows で使用不可の文字: \ / : * ? " < > |
        sanitized = re.sub(r'[\\/:*?"<>|]', "_", title)
        # 先頭と末尾のスペース・ドットを除去
        sanitized = sanitized.strip(". ")
        if not sanitized:
            sanitized = "untitled"
        return sanitized

    def _build_note_content(
        self, content: str, tags: list[str] | None = None
    ) -> str:
        """ノートファイルの内容を構築する（frontmatter 付き）。"""
        if tags:
            tags_yaml = ", ".join(tags)
            frontmatter = f"---\ntags: [{tags_yaml}]\n---\n\n"
            return frontmatter + content
        return content


