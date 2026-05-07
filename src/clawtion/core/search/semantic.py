"""セマンティック（ベクトル）検索モジュール。

pgvector の ``<=>`` （コサイン距離）演算子を使用して、
クエリの埋め込みベクトルに最も近いチャンクを検索する。
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.client import EmbeddingClient

    from .filter import MetadataFilter

logger = get_logger(__name__)


class SemanticSearch:
    """セマンティック（ベクトル）検索を実行する。

    PostgreSQL の pgvector 拡張を使用し、embedding ベクトルの
    コサイン距離による類似度検索を行う。
    """

    # RRF で使用する定数（hybrid 検索と合わせる）
    RRF_K: int = 60

    def __init__(self, db: DatabaseManager, embedder: EmbeddingClient) -> None:
        self._db = db
        self._embedder = embedder

    async def search(
        self,
        query: str,
        chunk_level: str = "file",
        top_k: int = 10,
        metadata_filter: MetadataFilter | None = None,
    ) -> dict[str, Any]:
        """セマンティック検索を実行する。

        Args:
            query: 検索クエリ文字列
            chunk_level: 検索対象のチャンク粒度（'file' / 'coarse' / 'fine'）
            top_k: 返す最大件数
            metadata_filter: メタデータフィルタ（オプション）

        Returns:
            ``{"results": [...], "context": {...}}`` の形式
        """
        start_time = time.time()

        # クエリの埋め込みベクトルを生成
        try:
            embedding_result = await self._embedder.embed_query(query)
            query_embedding = embedding_result.embedding
        except Exception as e:
            logger.error("Failed to embed query", query=query, error=str(e))
            return {
                "results": [],
                "context": {
                    "tool": "semantic_search",
                    "query": query,
                    "error": f"Embedding generation failed: {e}",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "suggestions_for_claude": [
                        "Embedding model unavailable. Try keyword_search instead.",
                    ],
                },
            }

        embedding_json = json.dumps(query_embedding)

        # フィルタ条件を構築
        filter_clause = ""
        filter_params: dict[str, Any] = {}
        if metadata_filter is not None and not metadata_filter.is_empty():
            filter_clause, filter_params = metadata_filter.to_sql_conditions()

        # chunk_level: "all" / None → search all levels; otherwise filter.
        # Use a dedicated param to avoid asyncpg AmbiguousParameterError.
        level_clause = ""
        if chunk_level and chunk_level != "all":
            level_clause = "AND dc.chunk_level = :chunk_level"

        # メインクエリ
        query_sql = f"""
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
                d.title,
                dc.embedding <=> CAST(:query_embedding AS vector) AS distance,
                1 - (dc.embedding <=> CAST(:query_embedding AS vector)) AS similarity_score
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE d.is_deleted = false
              {level_clause}
              {filter_clause}
            ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
        """

        params: dict[str, Any] = {
            "query_embedding": embedding_json,
            "top_k": top_k,
        }
        if chunk_level and chunk_level != "all":
            params["chunk_level"] = chunk_level
        params.update(filter_params)

        try:
            rows = await self._db.execute(query_sql, params)
        except Exception as e:
            logger.error("Semantic search query failed", error=str(e))
            return {
                "results": [],
                "context": {
                    "tool": "semantic_search",
                    "query": query,
                    "error": f"Database query failed: {e}",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "suggestions_for_claude": [
                        "Database error occurred. Try keyword_search as fallback.",
                    ],
                },
            }

        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(self._row_to_result(row))

        execution_time_ms = int((time.time() - start_time) * 1000)

        context = self._build_context(
            query=query,
            results=results,
            execution_time_ms=execution_time_ms,
            filter_applied=metadata_filter.to_dict() if metadata_filter else {},
        )

        return {"results": results, "context": context}

    async def search_raw(
        self,
        query_embedding: list[float],
        chunk_level: str = "file",
        top_k: int = 100,
        metadata_filter: MetadataFilter | None = None,
    ) -> list[dict[str, Any]]:
        """埋め込みベクトルを直接指定して検索する（HybridSearch 用内部API）。

        上位100件を返し、RRF で使用できるように rank を含める。
        """
        embedding_json = json.dumps(query_embedding)

        filter_clause = ""
        filter_params: dict[str, Any] = {}
        if metadata_filter is not None and not metadata_filter.is_empty():
            filter_clause, filter_params = metadata_filter.to_sql_conditions()

        level_clause = ""
        if chunk_level and chunk_level != "all":
            level_clause = "AND dc.chunk_level = :chunk_level"

        query_sql = f"""
            SELECT
                dc.chunk_id,
                dc.document_id,
                dc.chunk_level,
                ROW_NUMBER() OVER (ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)) AS rank,
                1.0 / (:rrf_k + ROW_NUMBER() OVER (ORDER BY dc.embedding <=> CAST(:query_embedding AS vector))) AS rrf_score_part,
                dc.embedding <=> CAST(:query_embedding AS vector) AS distance
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE d.is_deleted = false
              {level_clause}
              {filter_clause}
            ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
        """

        params: dict[str, Any] = {
            "query_embedding": embedding_json,
            "top_k": top_k,
            "rrf_k": self.RRF_K,
        }
        if chunk_level and chunk_level != "all":
            params["chunk_level"] = chunk_level
        params.update(filter_params)

        rows = await self._db.execute(query_sql, params)
        return [
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "chunk_level": row["chunk_level"],
                "rank_semantic": row["rank"],
                "rrf_score_semantic": row["rrf_score_part"],
                "distance": row["distance"],
            }
            for row in rows
        ]

    def _row_to_result(self, row: Any) -> dict[str, Any]:
        """DB 行を結果 dict に変換する。"""
        return {
            "chunk_id": row["chunk_id"],
            "document_id": row["document_id"],
            "content": row["content"],
            "content_with_context": row["content_with_context"],
            "chunk_level": row["chunk_level"],
            "chunk_index": row["chunk_index"],
            "chunk_total": row["chunk_total"],
            "heading_path": row["heading_path"],
            "token_count": row["token_count"],
            "char_count": row["char_count"],
            "file_path": row["file_path"],
            "folder_path": row["folder_path"],
            "title": row["title"],
            "distance": float(row["distance"]),
            "similarity_score": float(row["similarity_score"]),
            "score": float(row["similarity_score"]),
        }

    def _build_context(
        self,
        query: str,
        results: list[dict[str, Any]],
        execution_time_ms: int,
        filter_applied: dict[str, Any],
    ) -> dict[str, Any]:
        """検索結果の診断コンテキストを構築する。"""
        scores = [r["score"] for r in results]
        count = len(results)
        score_range: list[float] = [min(scores), max(scores)] if scores else [0.0, 0.0]
        avg_score = sum(scores) / count if count > 0 else 0.0

        # suggestions_for_claude を生成
        suggestions: list[str] = []
        if count == 0:
            suggestions.append(
                "No results. Try broadening query or check folder filter."
            )
        elif avg_score < 0.5:
            suggestions.append(
                "Low semantic match. Try keyword_search for exact term matching or broaden query."
            )
        elif avg_score >= 0.7:
            suggestions.append(
                f"Score range is healthy (>{avg_score:.2f}), results likely relevant."
            )

        if count > 0 and score_range[1] - score_range[0] > 0.3:
            suggestions.append(
                "Results vary in relevance. Consider top 2-3 only."
            )
        elif count > 0 and score_range[1] - score_range[0] < 0.1 and avg_score > 0.7:
            suggestions.append("Strong consistent matches across all results.")

        # 同一ファイルから複数ヒットしているか確認
        doc_ids = [r["document_id"] for r in results]
        from collections import Counter

        doc_counts = Counter(doc_ids)
        multi_hit_docs = {doc_id: cnt for doc_id, cnt in doc_counts.items() if cnt >= 3}
        if multi_hit_docs:
            suggestions.append(
                "Multiple hits from same file detected. Consider get_file_chunks for full context."
            )

        # 汎用サジェスチョン
        suggestions.append(
            "If too generic or results lack precision, try hybrid_search combining semantic + keyword."
        )

        return {
            "tool": "semantic_search",
            "query": query,
            "embedding_model": self._embedder.model_name,
            "search_space": {
                "chunk_level": None,  # 実際の件数は別クエリで取得可能
                "filter_applied": filter_applied,
            },
            "results_summary": {
                "count": count,
                "score_range": score_range,
                "avg_score": round(avg_score, 4),
            },
            "execution_time_ms": execution_time_ms,
            "suggestions_for_claude": suggestions,
        }
