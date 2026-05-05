"""Indexing サービスの実装。

ファイルの index/reindex/delete を統合的に管理するオーケストレーター。
チャンク分割 → 重複排除 → Embedding生成 → DB保存 のパイプラインを実行する。
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from clawtion.config.loader import get_config
from clawtion.utils.exceptions import (
    ClawtionError,
    DocumentNotFoundError,
    EmbeddingError,
    IndexingError,
)
from clawtion.utils.logging import get_logger
from clawtion.utils.retry import with_retry

from .chunker import Chunk, chunk_file
from .snapshot import FileSnapshot, compute_content_hash, take_snapshot

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.client import (
        EmbeddingClient,
        EmbeddingResult,
        FileProcessor,
    )

    from .queue import QueueManager


logger = get_logger(__name__)

# サポートするファイル拡張子
_SUPPORTED_EXTENSIONS: set[str] = {
    ".md", ".txt", ".rst", ".html", ".htm",
    ".json", ".yaml", ".yml", ".toml", ".csv", ".xml",
    ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h",
    ".rs", ".go", ".rb", ".php", ".swift", ".kt", ".scala",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".sql", ".r", ".tex", ".org", ".adoc", ".asciidoc", ".log",
}


class _TextFileProcessor:
    """テキストファイル用のデフォルトプロセッサ。"""

    def can_process(self, file_path: str) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext in _SUPPORTED_EXTENSIONS

    def extract_content(self, file_path: str) -> dict[str, Any]:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        return {"text": text}

    def get_supported_extensions(self) -> list[str]:
        return sorted(_SUPPORTED_EXTENSIONS)


class IndexingService:
    """Indexing サービスのメインクラス。

    ファイルの indexing パイプライン全体をオーケストレーションする。
    チャンク分割 → 重複排除 → Embedding生成 → DB保存 を実行する。
    """

    def __init__(
        self,
        db: DatabaseManager,
        embedder: EmbeddingClient,
        queue: QueueManager,
        vault_path: str,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._db = db
        self._embedder = embedder
        self._queue = queue
        self._vault_path = vault_path
        self._config = config or get_config()
        # コアプロセッサー（常に利用可能）
        self._file_processors: list[FileProcessor] = []

        # 構造化フォーマット用プロセッサー（テキストフォールバックより優先）
        from .loaders import (
            _DOCX_AVAILABLE,
            _EBOOKLIB_AVAILABLE,
            CSVProcessor,
            HTMLProcessor,
            JSONProcessor,
        )

        self._file_processors.append(HTMLProcessor())
        self._file_processors.append(CSVProcessor())
        self._file_processors.append(JSONProcessor())

        # オプションのプロセッサー（必要なライブラリがインストールされている場合のみ）
        if _EBOOKLIB_AVAILABLE:
            from .loaders import EPUBProcessor

            self._file_processors.append(EPUBProcessor())
            logger.info("EPUBProcessor registered (ebooklib available)")
        else:
            logger.debug("EPUBProcessor not available (ebooklib not installed)")

        if _DOCX_AVAILABLE:
            from .loaders import DocxProcessor

            self._file_processors.append(DocxProcessor())
            logger.info("DocxProcessor registered (python-docx available)")
        else:
            logger.debug("DocxProcessor not available (python-docx not installed)")

        # 汎用テキストプロセッサー（最後のフォールバック）
        self._file_processors.append(_TextFileProcessor())

    # ---- パブリック API ----

    async def index_file(self, file_path: str) -> list[str]:
        """単一ファイルを indexing する。

        Full flow:
            1. content_hash チェック（変更なければスキップ）
            2. ファイルをスナップショット
            3. チャンク分割
            4. チャンク重複排除（既存ハッシュがあれば再利用）
            5. Embedding 生成
            6. DB に UPSERT
            7. ドキュメントメタデータ更新

        Args:
            file_path: ファイルの絶対パス

        Returns:
            作成されたチャンク ID のリスト

        Raises:
            DocumentNotFoundError: ファイルが見つからない場合
            IndexingError: indexing 処理中にエラーが発生した場合
        """
        if not os.path.isfile(file_path):
            raise DocumentNotFoundError(file_path=file_path)

        # Vault 相対パスを計算
        rel_path = self._to_relative_path(file_path)
        folder_path = str(Path(rel_path).parent) + "/" if str(Path(rel_path).parent) != "." else ""
        title = Path(rel_path).stem
        ext = Path(rel_path).suffix.lower()

        # スナップショットを取得
        snapshot = take_snapshot(file_path)

        # 既存ドキュメントの content_hash をチェック
        existing = await self._db.execute_one(
            """
            SELECT document_id, content_hash, total_chunks
            FROM documents
            WHERE file_path = :file_path AND is_deleted = false
            """,
            {"file_path": rel_path},
        )

        if existing:
            db_hash = existing["content_hash"]
            if db_hash == snapshot.content_hash:
                logger.debug("File unchanged, skipping indexing", file_path=rel_path)
                # 既存のチャンク ID を返す
                chunk_rows = await self._db.execute(
                    """
                    SELECT chunk_id FROM document_chunks
                    WHERE document_id = :document_id
                    ORDER BY chunk_index ASC
                    """,
                    {"document_id": existing["document_id"]},
                )
                return [row["chunk_id"] for row in chunk_rows]

            document_id = existing["document_id"]
        else:
            document_id = str(uuid.uuid4())

        # テキストコンテンツを抽出
        content = self._extract_content(file_path, snapshot)

        # チャンク分割
        try:
            chunks = chunk_file(
                file_path, content, folder_path=folder_path, config=self._config,
            )
        except Exception as e:
            logger.error("Chunking failed", file_path=rel_path, error=str(e))
            raise IndexingError(
                message=f"Chunking failed for {rel_path}: {e}",
            ) from e

        # 生成されたチャンクのレベルを検出
        chunk_levels: set[str] = {c.level for c in chunks}
        has_file_level: bool = "file" in chunk_levels
        has_coarse_level: bool = "coarse" in chunk_levels
        has_fine_level: bool = "fine" in chunk_levels

        if not chunks:
            logger.warning("No chunks generated", file_path=rel_path)
            # 空のドキュメントとして登録
            await self._upsert_document(
                document_id=document_id,
                rel_path=rel_path,
                folder_path=folder_path,
                title=title,
                ext=ext,
                snapshot=snapshot,
                total_chunks=0,
                has_file_level=False,
                has_coarse_level=False,
                has_fine_level=False,
            )
            return []

        # ドキュメントを upsert
        await self._upsert_document(
            document_id=document_id,
            rel_path=rel_path,
            folder_path=folder_path,
            title=title,
            ext=ext,
            snapshot=snapshot,
            total_chunks=len(chunks),
            has_file_level=has_file_level,
            has_coarse_level=has_coarse_level,
            has_fine_level=has_fine_level,
        )

        # 既存チャンクを削除（古いチャンクをクリア）
        if existing:
            await self._db.execute(
                "DELETE FROM document_chunks WHERE document_id = :document_id",
                {"document_id": document_id},
            )

        # チャンク重複排除と Embedding 生成
        chunk_ids = await self._process_chunks(document_id, chunks)

        logger.info(
            "File indexed successfully",
            file_path=rel_path,
            document_id=document_id,
            chunk_count=len(chunk_ids),
        )

        return chunk_ids

    async def index_folder(self, folder_path: str) -> dict[str, Any]:
        """フォルダ内の全サポート対象ファイルを再帰的に indexing する。

        Args:
            folder_path: Vault 内のフォルダパス（相対）

        Returns:
            処理結果の集計::
                {"indexed": int, "skipped": int, "failed": int, "errors": list[str]}
        """
        abs_path = os.path.join(self._vault_path, folder_path) if folder_path else self._vault_path
        if not os.path.isdir(abs_path):
            raise ClawtionError(
                code="FOLDER_NOT_FOUND",
                message=f"Folder not found: {abs_path}",
            )

        stats: dict[str, Any] = {
            "indexed": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        for root, dirs, files in os.walk(abs_path):
            # .clawtion 設定ディレクトリを除外
            dirs[:] = [d for d in dirs if not d.startswith(".clawtion")]
            for file_name in sorted(files):
                file_abs = os.path.join(root, file_name)
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in _SUPPORTED_EXTENSIONS:
                    continue

                try:
                    chunk_ids = await self.index_file(file_abs)
                    if chunk_ids:
                        stats["indexed"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append(f"{file_name}: {e}")
                    logger.error(
                        "Failed to index file in folder scan",
                        file=file_name,
                        error=str(e),
                    )

        return stats

    async def reindex_file(self, file_path: str) -> list[str]:
        """content_hash チェックをスキップして強制的に再 indexing する。

        Args:
            file_path: ファイルの絶対パス

        Returns:
            作成されたチャンク ID のリスト
        """
        if not os.path.isfile(file_path):
            raise DocumentNotFoundError(file_path=file_path)

        # content_hash を無効化するため、一時的にドキュメントのハッシュを空に
        rel_path = self._to_relative_path(file_path)
        await self._db.execute(
            "UPDATE documents SET content_hash = '' WHERE file_path = :file_path",
            {"file_path": rel_path},
        )

        return await self.index_file(file_path)

    async def reindex_all(self) -> dict[str, Any]:
        """全ドキュメントを強制的に再 indexing する。

        Returns:
            処理結果の集計
        """
        rows = await self._db.execute(
            """
            SELECT file_path FROM documents
            WHERE is_deleted = false
            """,
            {},
        )

        stats: dict[str, Any] = {
            "total": len(rows),
            "reindexed": 0,
            "failed": 0,
            "errors": [],
        }

        for row in rows:
            abs_path = os.path.join(self._vault_path, row["file_path"])
            try:
                await self.reindex_file(abs_path)
                stats["reindexed"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"{row['file_path']}: {e}")
                logger.error(
                    "Failed to reindex", file=row["file_path"], error=str(e)
                )

        logger.info(
            "Reindex all completed",
            total=stats["total"],
            reindexed=stats["reindexed"],
            failed=stats["failed"],
        )
        return stats

    async def delete_file(self, file_path: str) -> None:
        """ファイルをインデックスから削除する（論理削除 + ゴミ箱）。

        Args:
            file_path: ファイルの絶対パス
        """
        rel_path = self._to_relative_path(file_path)

        row = await self._db.execute_one(
            """
            SELECT document_id, title, metadata
            FROM documents
            WHERE file_path = :file_path AND is_deleted = false
            """,
            {"file_path": rel_path},
        )

        if row is None:
            logger.warning("Document not found for deletion", file_path=rel_path)
            return

        document_id = row["document_id"]
        now = datetime.now(UTC)

        # ファイル内容を保存
        file_content = ""
        if os.path.isfile(file_path):
            try:
                with open(file_path, encoding="utf-8", errors="replace") as f:
                    file_content = f.read()
            except Exception as e:
                logger.warning("Failed to read file for trash", error=str(e))

        # trash テーブルに挿入
        from datetime import timedelta

        purge_at = (datetime.now(UTC) + timedelta(days=7)).isoformat()

        await self._db.execute(
            """
            INSERT INTO trash
                (original_document_id, original_file_path,
                 original_content, original_metadata, auto_purge_at)
            VALUES
                (:document_id, :file_path, :content, CAST(:metadata AS jsonb), CAST(:purge_at AS timestamptz))
            """,
            {
                "document_id": document_id,
                "file_path": rel_path,
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

        logger.info("File deleted from index", file_path=rel_path)

    async def process_queue(self) -> dict[str, Any]:
        """キュー内の全 pending ジョブを処理する。

        Returns:
            処理結果の集計::
                {"processed": int, "completed": int, "failed": int, "errors": list[dict]}
        """
        stats: dict[str, Any] = {
            "processed": 0,
            "completed": 0,
            "failed": 0,
            "errors": [],
        }

        while True:
            job = await self._queue.dequeue()
            if job is None:
                break

            stats["processed"] += 1
            queue_id = job["queue_id"]
            operation = job["operation"]
            file_path = job.get("file_path", "")
            abs_path = os.path.join(self._vault_path, file_path)

            try:
                if operation == "index" or operation == "reindex":
                    if os.path.isfile(abs_path):
                        if operation == "reindex":
                            await self.reindex_file(abs_path)
                        else:
                            await self.index_file(abs_path)
                        await self._queue.update_status(queue_id, "completed")
                    else:
                        # ファイルが存在しない場合は削除扱い
                        await self.delete_file(abs_path)
                        await self._queue.update_status(queue_id, "completed")
                elif operation == "delete":
                    await self.delete_file(abs_path)
                    await self._queue.update_status(queue_id, "completed")
                else:
                    await self._queue.update_status(
                        queue_id, "failed", error=f"Unknown operation: {operation}"
                    )

                stats["completed"] += 1

            except DocumentNotFoundError as e:
                await self._queue.update_status(
                    queue_id, "completed",
                    error=f"File not found, skipping: {e}",
                )
                stats["completed"] += 1

            except Exception as e:
                await self._queue.update_status(
                    queue_id, "failed", error=str(e),
                )
                stats["failed"] += 1
                stats["errors"].append({
                    "queue_id": queue_id,
                    "file_path": file_path,
                    "error": str(e),
                })
                logger.error(
                    "Queue processing failed",
                    queue_id=queue_id,
                    file=file_path,
                    error=str(e),
                )

        logger.info(
            "Queue processing completed",
            processed=stats["processed"],
            completed=stats["completed"],
            failed=stats["failed"],
        )
        return stats

    async def get_file_processors(self) -> list[FileProcessor]:
        """登録されているファイルプロセッサのリストを返す。"""
        return list(self._file_processors)

    def register_file_processor(self, processor: FileProcessor) -> None:
        """ファイルプロセッサを追加登録する。"""
        self._file_processors.append(processor)

    async def scan_vault(self) -> dict[str, Any]:
        """Vault をスキャンし、新規・変更・削除されたファイルを検出してキューに追加する。

        Returns:
            スキャン結果の集計::
                {"scanned": int, "new": int, "changed": int, "deleted": int,
                 "enqueued": int}
        """
        stats: dict[str, Any] = {
            "scanned": 0,
            "new": 0,
            "changed": 0,
            "deleted": 0,
            "enqueued": 0,
        }

        # DB 内の全アクティブドキュメントのパスを取得
        db_rows = await self._db.execute(
            "SELECT file_path, content_hash FROM documents WHERE is_deleted = false",
            {},
        )
        db_files: dict[str, str] = {row["file_path"]: row["content_hash"] for row in db_rows}

        # Vault をスキャン
        vault_files: dict[str, str] = {}
        for root, dirs, files in os.walk(self._vault_path):
            # .clawtion 設定ディレクトリを除外
            dirs[:] = [d for d in dirs if not d.startswith(".clawtion")]
            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in _SUPPORTED_EXTENSIONS:
                    continue

                full_path = os.path.join(root, file_name)
                rel_path = self._to_relative_path(full_path)
                stats["scanned"] += 1

                # ハッシュ計算
                try:
                    with open(full_path, "rb") as f:
                        content_hash = compute_content_hash(f.read())
                except OSError as e:
                    logger.warning("Cannot read file during scan", file=rel_path, error=str(e))
                    continue

                vault_files[rel_path] = content_hash

                if rel_path not in db_files:
                    # 新規ファイル
                    stats["new"] += 1
                    await self._queue.enqueue("", rel_path, operation="index")
                    stats["enqueued"] += 1
                elif db_files[rel_path] != content_hash:
                    # 変更ファイル
                    stats["changed"] += 1
                    await self._queue.enqueue("", rel_path, operation="index")
                    stats["enqueued"] += 1

        # DB にあって Vault にないファイル（削除検出）
        for rel_path in db_files:
            if rel_path not in vault_files:
                stats["deleted"] += 1
                await self._queue.enqueue("", rel_path, operation="delete")
                stats["enqueued"] += 1

        logger.info(
            "Vault scan completed",
            scanned=stats["scanned"],
            new=stats["new"],
            changed=stats["changed"],
            deleted=stats["deleted"],
            enqueued=stats["enqueued"],
        )
        return stats

    async def resume_indexing(self, queue_id: str) -> dict[str, Any]:
        """中断された indexing を進捗チェックポイントから再開する。

        Args:
            queue_id: 再開するキューアイテムの ID

        Returns:
            処理結果::
                {"status": str, "chunks_processed": int, "error": str | None}
        """
        job = await self._db.execute_one(
            """
            SELECT queue_id, document_id, file_path, operation, status, progress
            FROM indexing_queue
            WHERE queue_id = :queue_id
            """,
            {"queue_id": queue_id},
        )

        if job is None:
            raise ClawtionError(
                code="QUEUE_ITEM_NOT_FOUND",
                message=f"Queue item not found: {queue_id}",
            )

        if job["status"] not in ("partial", "processing"):
            return {
                "status": "cannot_resume",
                "chunks_processed": 0,
                "error": f"Job status is '{job['status']}', expected 'partial' or 'processing'",
            }

        progress = job["progress"]
        if isinstance(progress, str):
            progress = json.loads(progress)
        if not isinstance(progress, dict):
            progress = {}

        file_path = job["file_path"]
        abs_path = os.path.join(self._vault_path, file_path)

        if not os.path.isfile(abs_path):
            await self._queue.update_status(
                queue_id, "failed", error="File no longer exists"
            )
            return {
                "status": "failed",
                "chunks_processed": 0,
                "error": "File no longer exists",
            }

        # ステータスを processing に戻す
        await self._db.execute(
            """
            UPDATE indexing_queue
            SET status = 'processing'
            WHERE queue_id = :queue_id
            """,
            {"queue_id": queue_id},
        )

        # 完全な indexing を実行（中断時点から再開よりも、ファイル全体を再処理のほうが安全）
        try:
            chunk_ids = await self.index_file(abs_path)
            await self._queue.update_status(queue_id, "completed")
            return {
                "status": "completed",
                "chunks_processed": len(chunk_ids),
                "error": None,
            }
        except Exception as e:
            await self._queue.update_status(queue_id, "failed", error=str(e))
            logger.error("Resume indexing failed", queue_id=queue_id, error=str(e))
            return {
                "status": "failed",
                "chunks_processed": 0,
                "error": str(e),
            }

    # ---- 内部メソッド ----

    async def _upsert_document(
        self,
        document_id: str,
        rel_path: str,
        folder_path: str,
        title: str,
        ext: str,
        snapshot: FileSnapshot,
        total_chunks: int,
        has_file_level: bool = False,
        has_coarse_level: bool = False,
        has_fine_level: bool = False,
    ) -> None:
        """ドキュメントレコードを UPSERT する。

        Args:
            document_id: ドキュメント UUID
            rel_path: Vault 相対パス
            folder_path: フォルダ相対パス
            title: ファイルタイトル（拡張子なしベース名）
            ext: ファイル拡張子
            snapshot: ファイルスナップショット
            total_chunks: 全チャンク数の合計
            has_file_level: ファイルレベルチャンクが存在するか
            has_coarse_level: Coarse レベルチャンクが存在するか
            has_fine_level: Fine レベルチャンクが存在するか
        """

        now = datetime.now(UTC)

        await self._db.execute(
            """
            INSERT INTO documents (
                document_id, file_path, folder_path, title,
                file_extension, file_size_bytes, content_hash,
                total_chunks, has_file_level, has_coarse_level,
                has_fine_level, last_indexed_at,
                created_at, updated_at
            ) VALUES (
                :document_id, :file_path, :folder_path, :title,
                :extension, :file_size, :content_hash,
                :total_chunks, :has_file_level, :has_coarse_level,
                :has_fine_level, :now,
                :now, :now
            )
            ON CONFLICT (file_path) DO UPDATE SET
                content_hash = EXCLUDED.content_hash,
                file_size_bytes = EXCLUDED.file_size_bytes,
                total_chunks = EXCLUDED.total_chunks,
                has_file_level = EXCLUDED.has_file_level,
                has_coarse_level = EXCLUDED.has_coarse_level,
                has_fine_level = EXCLUDED.has_fine_level,
                last_indexed_at = EXCLUDED.last_indexed_at,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "document_id": document_id,
                "file_path": rel_path,
                "folder_path": folder_path,
                "title": title,
                "extension": ext,
                "file_size": len(snapshot.content),
                "content_hash": snapshot.content_hash,
                "total_chunks": total_chunks,
                "has_file_level": has_file_level,
                "has_coarse_level": has_coarse_level,
                "has_fine_level": has_fine_level,
                "now": now,
            },
        )

    async def _process_chunks(
        self, document_id: str, chunks: list[Chunk]
    ) -> list[str]:
        """チャンクリストを処理する。

        1. 既存チャンクのハッシュと照合して重複排除
        2. 新規チャンクの Embedding を生成
        3. DB に挿入

        Args:
            document_id: ドキュメントの UUID
            chunks: 処理するチャンクのリスト

        Returns:
            作成されたチャンク ID のリスト
        """
        chunk_ids: list[str] = []
        new_chunks: list[tuple[Chunk, str]] = []  # (chunk, chunk_id)

        # 既存の content_hash を一括取得
        chunk_hashes = [c.content_hash for c in chunks]
        existing_map: dict[str, dict[str, Any]] = {}

        if chunk_hashes:
            # IN 句用パラメータ
            params: dict[str, Any] = {
                f"h_{i}": h for i, h in enumerate(chunk_hashes)
            }
            in_clause = ", ".join(f":h_{i}" for i in range(len(chunk_hashes)))

            try:
                existing_rows = await self._db.execute(
                    f"""
                    SELECT chunk_id, content_hash, embedding
                    FROM document_chunks
                    WHERE content_hash IN ({in_clause})
                    """,
                    params,
                )
                for row in existing_rows:
                    existing_map[row["content_hash"]] = {
                        "chunk_id": row["chunk_id"],
                        "embedding": row["embedding"],
                    }
            except Exception:
                # 初回などテーブルが空の場合
                existing_map = {}

        for chunk in chunks:
            chunk_id = str(uuid.uuid4())

            if chunk.content_hash in existing_map:
                # 重複: 既存の embedding を再利用
                existing = existing_map[chunk.content_hash]
                reuse_id = existing["chunk_id"]
                embedding = existing.get("embedding")

                await self._insert_chunk(
                    chunk_id=reuse_id,
                    document_id=document_id,
                    chunk=chunk,
                    embedding=embedding,
                    is_reuse=True,
                )
                chunk_ids.append(reuse_id)
            else:
                # 新規: Embedding を生成
                new_chunks.append((chunk, chunk_id))

        # 一括 Embedding 生成
        if new_chunks:
            contents = [c[0].content_with_context for c in new_chunks]
            try:
                embeddings = await self._generate_embeddings(contents)
            except EmbeddingError as e:
                logger.error("Embedding generation failed in batch", error=str(e))
                # Embedding なしでもチャンクを挿入（後で再試行可能）
                embeddings = [None] * len(new_chunks)

            for (chunk, cid), embedding in zip(new_chunks, embeddings, strict=False):
                await self._insert_chunk(
                    chunk_id=cid,
                    document_id=document_id,
                    chunk=chunk,
                    embedding=embedding,
                    is_reuse=False,
                )
                chunk_ids.append(cid)

        return chunk_ids

    async def _insert_chunk(
        self,
        chunk_id: str,
        document_id: str,
        chunk: Chunk,
        embedding: Any | None,
        is_reuse: bool,
    ) -> None:
        """チャンクレコードを DB に挿入する。"""
        now = datetime.now(UTC)

        embedding_json = None
        if embedding is not None:
            embedding_json = json.dumps(embedding)

        # メタデータ
        metadata = json.dumps({
            "reused_embedding": is_reuse,
            "level": chunk.level,
        }, ensure_ascii=False)

        try:
            await self._db.execute(
                """
                INSERT INTO document_chunks (
                    chunk_id, document_id, chunk_level, chunk_index, chunk_total,
                    heading_path, content, content_with_context, content_hash,
                    embedding, embedding_model, embedding_dimensions,
                    token_count, char_count, metadata, created_at
                ) VALUES (
                    :chunk_id, :document_id, :chunk_level, :chunk_index, :chunk_total,
                    :heading_path, :content, :content_with_context, :content_hash,
                    CAST(:embedding AS vector), :embedding_model, :embedding_dimensions,
                    :token_count, :char_count, CAST(:metadata AS jsonb), :created_at
                )
                ON CONFLICT (chunk_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    content_with_context = EXCLUDED.content_with_context,
                    content_hash = EXCLUDED.content_hash,
                    chunk_index = EXCLUDED.chunk_index,
                    chunk_total = EXCLUDED.chunk_total,
                    heading_path = EXCLUDED.heading_path,
                    token_count = EXCLUDED.token_count,
                    char_count = EXCLUDED.char_count,
                    embedding = COALESCE(EXCLUDED.embedding, document_chunks.embedding),
                    updated_at = EXCLUDED.created_at
                """,
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "chunk_level": chunk.level,
                    "chunk_index": chunk.chunk_index,
                    "chunk_total": chunk.chunk_total,
                    "heading_path": chunk.heading_path,
                    "content": chunk.content,
                    "content_with_context": chunk.content_with_context,
                    "content_hash": chunk.content_hash,
                    "embedding": embedding_json,
                    "embedding_model": self._embedder.model_name if embedding is not None else "",
                    "embedding_dimensions": self._embedder.dimensions if embedding is not None else 0,
                    "token_count": chunk.token_count,
                    "char_count": chunk.char_count,
                    "metadata": metadata,
                    "created_at": now,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to insert chunk",
                chunk_id=chunk_id,
                document_id=document_id,
                error=str(e),
            )
            raise

    async def _generate_embeddings(
        self, contents: list[str]
    ) -> list[list[float] | None]:
        """テキストリストの Embedding を一括生成する。"""
        if not contents:
            return []

        try:
            results: list[EmbeddingResult] = await with_retry(
                self._embedder.embed_batch,
                contents=contents,
                config=None,
                error_types=(Exception,),
            )
            return [r.embedding for r in results]
        except Exception as e:
            logger.error(
                "Batch embedding failed after retries",
                count=len(contents),
                error=str(e),
            )
            # 個別にリトライ
            individual_results: list[list[float] | None] = []
            for content in contents:
                try:
                    emb_result: EmbeddingResult = await with_retry(
                        self._embedder.embed_document,
                        content=content,
                        config=None,
                        error_types=(Exception,),
                    )
                    individual_results.append(emb_result.embedding)
                except Exception as e2:
                    logger.error(
                        "Individual embedding failed",
                        error=str(e2),
                    )
                    individual_results.append(None)
            return individual_results

    def _extract_content(
        self, file_path: str, snapshot: FileSnapshot
    ) -> str:
        """ファイルからテキストコンテンツを抽出する。

        適切な FileProcessor を使用してコンテンツを抽出する。
        """
        for processor in self._file_processors:
            if processor.can_process(file_path):
                try:
                    extracted = processor.extract_content(file_path)
                    if isinstance(extracted, dict):
                        return str(extracted.get("text", ""))
                    return str(extracted)
                except Exception as e:
                    logger.warning(
                        "File processor failed, trying next",
                        file=file_path,
                        error=str(e),
                    )
        # デフォルト: UTF-8 として読み込む
        return snapshot.content.decode("utf-8", errors="replace")

    def _to_relative_path(self, abs_path: str) -> str:
        """絶対パスを Vault 相対パスに変換する。"""
        try:
            return str(Path(abs_path).relative_to(Path(self._vault_path)))
        except ValueError:
            return str(abs_path)
