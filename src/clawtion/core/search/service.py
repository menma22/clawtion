"""検索サービスの統合インターフェース。

セマンティック検索・キーワード検索・ハイブリッド検索の3つを統合し、
チャンクナビゲーションやフォルダ一覧などの補助機能も提供する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from clawtion.utils.logging import get_logger

from .filter import MetadataFilter
from .hybrid import HybridSearch
from .keyword import KeywordSearch
from .semantic import SemanticSearch

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.client import EmbeddingClient

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """検索結果を保持するデータクラス。"""

    results: list[dict[str, Any]]
    context: dict[str, Any]


@dataclass
class NavigationInfo:
    """チャンクナビゲーション情報。

    同一ファイル内での前後のチャンク位置を提供する。
    """

    file_path: str
    has_previous: bool
    has_next: bool
    previous_chunk_id: str | None = None
    next_chunk_id: str | None = None
    all_chunks_in_file: list[str] = field(default_factory=list)


class SearchService:
    """検索サービスの統合インターフェース。

    3種類の検索（セマンティック・キーワード・ハイブリッド）を統合し、
    チャンクナビゲーション・フォルダ一覧などの補助機能を提供する。
    """

    def __init__(self, db: DatabaseManager, embedder: EmbeddingClient) -> None:
        self._semantic = SemanticSearch(db, embedder)
        self._keyword = KeywordSearch(db)
        self._hybrid_search = HybridSearch(db, embedder)
        self._db = db

    # ---- 検索メソッド ----

    async def semantic_search(
        self,
        query: str,
        granularity: str = "file",
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> SearchResult:
        """セマンティック検索を実行する。"""
        mf = self._dict_to_filter(filter)
        result = await self._semantic.search(
            query,
            chunk_level=granularity,
            top_k=top_k,
            metadata_filter=mf,
        )
        return SearchResult(
            results=result["results"],
            context=result["context"],
        )

    async def keyword_search(
        self,
        query: str,
        granularity: str = "file",
        top_k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> SearchResult:
        """キーワード検索を実行する。"""
        mf = self._dict_to_filter(filter)
        result = await self._keyword.search(
            query,
            chunk_level=granularity,
            top_k=top_k,
            metadata_filter=mf,
        )
        return SearchResult(
            results=result["results"],
            context=result["context"],
        )

    async def hybrid_search(
        self,
        query: str,
        granularity: str = "file",
        top_k: int = 10,
        semantic_weight: float = 0.5,
        filter: dict[str, Any] | None = None,
    ) -> SearchResult:
        """ハイブリッド検索（RRF融合）を実行する。"""
        mf = self._dict_to_filter(filter)
        result = await self._hybrid_search.search(
            query,
            chunk_level=granularity,
            top_k=top_k,
            semantic_weight=semantic_weight,
            metadata_filter=mf,
        )
        return SearchResult(
            results=result["results"],
            context=result["context"],
        )

    # ---- チャンクナビゲーション ----

    async def get_file_chunks(
        self, document_id: str, level: str = "file"
    ) -> list[dict[str, Any]]:
        """指定ドキュメントの全チャンクを順序通りに取得する。"""
        query = """
            SELECT
                dc.chunk_id,
                dc.document_id,
                dc.content,
                dc.content_with_context,
                dc.chunk_level,
                dc.chunk_index,
                dc.chunk_total,
                dc.heading_path,
                dc.token_count,
                dc.char_count,
                d.file_path,
                d.folder_path,
                d.title
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE dc.document_id = :document_id
              AND (:chunk_level IS NULL OR dc.chunk_level = :chunk_level)
            ORDER BY dc.chunk_index ASC
        """
        rows = await self._db.execute(
            query,
            {"document_id": document_id, "chunk_level": level},
        )
        return [dict(row._mapping) for row in rows]

    async def get_neighbor_chunks(
        self, chunk_id: str, before: int = 1, after: int = 1
    ) -> list[dict[str, Any]]:
        """指定チャンクの前後 N 個のチャンクを同一ファイル内から取得する。"""
        # まず対象チャンクの document_id と chunk_level, chunk_index を取得
        current = await self._db.execute_one(
            """
            SELECT document_id, chunk_level, chunk_index
            FROM document_chunks
            WHERE chunk_id = :chunk_id
            """,
            {"chunk_id": chunk_id},
        )
        if current is None:
            return []

        document_id = current["document_id"]
        chunk_level = current["chunk_level"]
        chunk_index = current["chunk_index"]

        # 前後を取得
        query = """
            SELECT
                dc.chunk_id,
                dc.document_id,
                dc.content,
                dc.content_with_context,
                dc.chunk_level,
                dc.chunk_index,
                dc.chunk_total,
                dc.heading_path,
                dc.token_count,
                dc.char_count,
                d.file_path,
                d.folder_path,
                d.title
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE dc.document_id = :document_id
              AND dc.chunk_level = :chunk_level
              AND dc.chunk_index >= :min_index
              AND dc.chunk_index <= :max_index
            ORDER BY dc.chunk_index ASC
        """
        rows = await self._db.execute(
            query,
            {
                "document_id": document_id,
                "chunk_level": chunk_level,
                "min_index": max(0, chunk_index - before),
                "max_index": chunk_index + after,
            },
        )
        return [dict(row._mapping) for row in rows]

    async def get_parent_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """指定チャンクの親チャンクを取得する（fine > coarse > file の階層）。

        Phase 2 用。Phase 1 では ``parent_chunk_id`` が NULL のため None を返す。
        """
        row = await self._db.execute_one(
            """
            SELECT parent_chunk_id FROM document_chunks
            WHERE chunk_id = :chunk_id
            """,
            {"chunk_id": chunk_id},
        )
        if row is None or row["parent_chunk_id"] is None:
            return None

        parent = await self._db.execute_one(
            """
            SELECT
                chunk_id, document_id, content, content_with_context,
                chunk_level, chunk_index, chunk_total, heading_path,
                token_count, char_count
            FROM document_chunks
            WHERE chunk_id = :parent_chunk_id
            """,
            {"parent_chunk_id": row["parent_chunk_id"]},
        )
        if parent is None:
            return None
        return {key: parent[key] for key in parent}

    # ---- フォルダ・ノート一覧 ----

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

    async def list_notes(
        self,
        folder: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Vault 内のノート一覧を取得する。"""
        filter_clause = ""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if folder is not None:
            filter_clause = " AND d.folder_path = :folder"
            params["folder"] = folder

        query = f"""
            SELECT
                d.document_id,
                d.file_path,
                d.folder_path,
                d.title,
                d.file_extension,
                d.file_size_bytes,
                d.content_hash,
                d.tags,
                d.metadata,
                d.total_chunks,
                d.last_indexed_at,
                d.created_at,
                d.updated_at
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
                "tags": row["tags"] if isinstance(row["tags"], list) else [],
                "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
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

    # ---- 内部ヘルパー ----

    def _build_navigation(
        self, chunk: dict[str, Any], all_chunks: list[dict[str, Any]]
    ) -> NavigationInfo:
        """チャンクのナビゲーション情報を構築する。"""
        chunk_id = chunk["chunk_id"]
        chunk_ids = [c["chunk_id"] for c in all_chunks]

        try:
            current_idx = chunk_ids.index(chunk_id)
        except ValueError:
            return NavigationInfo(file_path=chunk.get("file_path", ""), has_previous=False, has_next=False)

        has_previous = current_idx > 0
        has_next = current_idx < len(chunk_ids) - 1

        return NavigationInfo(
            file_path=chunk.get("file_path", ""),
            has_previous=has_previous,
            has_next=has_next,
            previous_chunk_id=chunk_ids[current_idx - 1] if has_previous else None,
            next_chunk_id=chunk_ids[current_idx + 1] if has_next else None,
            all_chunks_in_file=chunk_ids,
        )

    def _generate_suggestions(
        self, results: list[dict[str, Any]], context: dict[str, Any]
    ) -> list[str]:
        """検索結果に基づいて Claude Code 向けのサジェスチョンを生成する。"""
        suggestions: list[str] = []
        count = len(results)

        if count == 0:
            suggestions.append("No results found. Try broadening query or removing filters.")
            return suggestions

        scores = [r.get("score", 0.0) for r in results]
        avg_score = sum(scores) / count if count > 0 else 0.0

        if avg_score < 0.3:
            suggestions.append(
                "Low relevance scores. Consider keyword_search for exact matching."
            )
        elif avg_score >= 0.7:
            suggestions.append(
                f"Strong relevance (avg score {avg_score:.2f}). Results are likely reliable."
            )

        # 同一ファイルからの複数ヒット
        from collections import Counter

        doc_ids = [r["document_id"] for r in results]
        doc_counts = Counter(doc_ids)
        multi_hit = {doc_id: cnt for doc_id, cnt in doc_counts.items() if cnt >= 3}
        if multi_hit:
            suggestions.append(
                "Multiple chunks from the same file found. Use get_file_chunks for complete context."
            )
            suggestions.append(
                f"Files with multiple hits: {', '.join(multi_hit.keys())}"
            )

        return suggestions

    def _dict_to_filter(
        self, filter_dict: dict[str, Any] | None
    ) -> MetadataFilter | None:
        """dict 形式のフィルタを MetadataFilter に変換する。"""
        if filter_dict is None:
            return None

        mf = MetadataFilter(
            folder=filter_dict.get("folder"),
            tags=filter_dict.get("tags"),
            date_from=filter_dict.get("date_from"),
            date_to=filter_dict.get("date_to"),
            extension=filter_dict.get("extension"),
            custom=filter_dict.get("custom"),
        )

        if mf.is_empty():
            return None

        return mf
