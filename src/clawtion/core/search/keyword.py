"""キーワード検索モジュール。

PostgreSQL の ``tsvector`` / ``tsquery`` を使用して BM25 近似の
全文テキスト検索を実行する。``plainto_tsquery`` でユーザークエリを
パースし、``ts_rank_cd`` でスコアリングする。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager

    from .filter import MetadataFilter

logger = get_logger(__name__)


class KeywordSearch:
    """キーワード検索を実行する。

    PostgreSQL の ``tsvector`` 全文検索を使用し、
    正確な単語・フレーズの一致に基づく検索結果を返す。
    """

    RRF_K: int = 60

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def search(
        self,
        query: str,
        chunk_level: str = "file",
        top_k: int = 10,
        metadata_filter: MetadataFilter | None = None,
    ) -> dict[str, Any]:
        """キーワード検索を実行する。

        Args:
            query: 検索クエリ文字列
            chunk_level: 検索対象のチャンク粒度
            top_k: 返す最大件数
            metadata_filter: メタデータフィルタ（オプション）

        Returns:
            ``{"results": [...], "context": {...}}`` の形式
        """
        start_time = time.time()

        filter_clause = ""
        filter_params: dict[str, Any] = {}
        if metadata_filter is not None and not metadata_filter.is_empty():
            filter_clause, filter_params = metadata_filter.to_sql_conditions()

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
                ts_rank_cd(dc.tsvector, plainto_tsquery('simple', :query), 32) AS keyword_score
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id,
                 plainto_tsquery('simple', :query) query
            WHERE dc.tsvector @@ query
              AND (:chunk_level IS NULL OR dc.chunk_level = :chunk_level)
              AND d.is_deleted = false
              {filter_clause}
            ORDER BY keyword_score DESC
            LIMIT :top_k
        """

        params: dict[str, Any] = {
            "query": query,
            "chunk_level": chunk_level,
            "top_k": top_k,
        }
        params.update(filter_params)

        try:
            rows = await self._db.execute(query_sql, params)
        except Exception as e:
            logger.error("Keyword search query failed", error=str(e))
            return {
                "results": [],
                "context": {
                    "tool": "keyword_search",
                    "query": query,
                    "error": f"Database query failed: {e}",
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "suggestions_for_claude": [
                        "Keyword search database error. Try semantic_search as fallback.",
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
        query: str,
        chunk_level: str = "file",
        top_k: int = 100,
        metadata_filter: MetadataFilter | None = None,
    ) -> list[dict[str, Any]]:
        """キーワード検索の生結果を返す（HybridSearch 用内部API）。

        上位100件を返し、rank 情報を含める。
        """
        filter_clause = ""
        filter_params: dict[str, Any] = {}
        if metadata_filter is not None and not metadata_filter.is_empty():
            filter_clause, filter_params = metadata_filter.to_sql_conditions()

        query_sql = f"""
            SELECT
                dc.chunk_id,
                dc.document_id,
                dc.chunk_level,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(dc.tsvector, plainto_tsquery('simple', :query), 32) DESC) AS rank,
                1.0 / (:rrf_k + ROW_NUMBER() OVER (ORDER BY ts_rank_cd(dc.tsvector, plainto_tsquery('simple', :query), 32) DESC)) AS rrf_score_part,
                ts_rank_cd(dc.tsvector, plainto_tsquery('simple', :query), 32) AS keyword_score
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id,
                 plainto_tsquery('simple', :query) query
            WHERE dc.tsvector @@ query
              AND (:chunk_level IS NULL OR dc.chunk_level = :chunk_level)
              AND d.is_deleted = false
              {filter_clause}
            ORDER BY keyword_score DESC
            LIMIT :top_k
        """

        params: dict[str, Any] = {
            "query": query,
            "chunk_level": chunk_level,
            "top_k": top_k,
            "rrf_k": self.RRF_K,
        }
        params.update(filter_params)

        rows = await self._db.execute(query_sql, params)
        return [
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "chunk_level": row["chunk_level"],
                "rank_keyword": row["rank"],
                "rrf_score_keyword": row["rrf_score_part"],
                "keyword_score": row["keyword_score"],
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
            "keyword_score": float(row["keyword_score"]),
            "score": float(row["keyword_score"]),
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

        suggestions: list[str] = []
        if count == 0:
            suggestions.append(
                "No keyword matches. Try semantic_search for meaning-based search or check spelling."
            )
        elif avg_score < 0.1:
            suggestions.append(
                "Low keyword relevance. Try semantic_search for broader meaning matching."
            )
        elif avg_score > 0.5:
            suggestions.append(
                f"Strong keyword matches (avg {avg_score:.2f}). Results likely contain exact query terms."
            )

        if count > 0:
            from collections import Counter

            doc_ids = [r["document_id"] for r in results]
            multi_hit_docs = {doc_id: cnt for doc_id, cnt in Counter(doc_ids).items() if cnt >= 3}
            if multi_hit_docs:
                suggestions.append(
                    "Multiple hits from same file. Consider get_file_chunks for full context."
                )

        return {
            "tool": "keyword_search",
            "query": query,
            "search_space": {
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
