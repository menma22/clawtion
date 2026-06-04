"""キーワード検索モジュール。

PostgreSQL の ``tsvector`` / ``tsquery`` を使用して BM25 近似の
全文テキスト検索を実行する。``plainto_tsquery`` でユーザークエリを
パースし、``ts_rank_cd`` でスコアリングする。

tsvector で十分な結果が得られなかった場合、pg_trgm の ``similarity()``
による部分一致検索で補完する（英語の部分一致・日本語の文字列内一致に対応）。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from clawtion.utils.logging import get_logger

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager

    from .filter import MetadataFilter

logger = get_logger(__name__)

_TRIGRAM_SIMILARITY_THRESHOLD = 0.10


def _build_level_clause(chunk_level: str) -> tuple[str, dict[str, str]]:
    """chunk_level から SQL 条件とパラメータを構築する。

    "all" / "" / None → 全粒度対象（フィルタなし）。
    "file,coarse" → IN (:cl_0, :cl_1) 条件。
    """
    if not chunk_level or chunk_level == "all":
        return "", {}
    levels = [lv.strip() for lv in chunk_level.split(",") if lv.strip()]
    if not levels:
        return "", {}
    if len(levels) == 1:
        return "AND dc.chunk_level = :chunk_level", {"chunk_level": levels[0]}
    placeholders = ", ".join(f":cl_{i}" for i in range(len(levels)))
    params = {f"cl_{i}": lv for i, lv in enumerate(levels)}
    return f"AND dc.chunk_level IN ({placeholders})", params


class KeywordSearch:
    """キーワード検索を実行する。

    PostgreSQL の ``tsvector`` 全文検索に加え、
    pg_trgm による部分一致検索で補完する。
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

        level_clause, level_params = _build_level_clause(chunk_level)

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
              AND d.is_deleted = false
              {level_clause}
              {filter_clause}
            ORDER BY keyword_score DESC
            LIMIT :top_k
        """

        params: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
        }
        params.update(level_params)
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
        tsvector_ids: set[str] = set()
        for row in rows:
            r = self._row_to_result(row)
            results.append(r)
            tsvector_ids.add(r["chunk_id"])

        # tsvector で十分な件数が取れなかった場合、trigram で補完
        if len(results) < top_k:
            try:
                trigram_results = await self._search_trigram(
                    query=query,
                    chunk_level=chunk_level,
                    top_k=top_k - len(results),
                    metadata_filter=metadata_filter,
                    exclude_ids=tsvector_ids,
                )
                results.extend(trigram_results)
            except Exception as e:
                logger.warning("Trigram search supplement failed", error=str(e))

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

        level_clause, level_params = _build_level_clause(chunk_level)

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
              AND d.is_deleted = false
              {level_clause}
              {filter_clause}
            ORDER BY keyword_score DESC
            LIMIT :top_k
        """

        params: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "rrf_k": self.RRF_K,
        }
        params.update(level_params)
        params.update(filter_params)

        rows = await self._db.execute(query_sql, params)
        base_results: list[dict[str, Any]] = [
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

        # tsvector で十分な件数が取れなかった場合、trigram で補完
        if len(base_results) < top_k:
            tsvector_ids = {r["chunk_id"] for r in base_results}
            trigram_rows = await self._search_trigram_raw(
                query=query,
                chunk_level=chunk_level,
                top_k=top_k - len(base_results),
                metadata_filter=metadata_filter,
                exclude_ids=tsvector_ids,
                start_rank=len(base_results) + 1,
            )
            base_results.extend(trigram_rows)

        return base_results

    async def _search_trigram(
        self,
        query: str,
        chunk_level: str,
        top_k: int,
        metadata_filter: MetadataFilter | None,
        exclude_ids: set[str],
    ) -> list[dict[str, Any]]:
        """pg_trgm similarity による部分一致検索。

        tsvector で十分な結果が得られなかった場合の補完として使用。
        similarity(content, query) で類似度を計算し閾値以上を返す。
        """
        filter_clause = ""
        filter_params: dict[str, Any] = {}
        if metadata_filter is not None and not metadata_filter.is_empty():
            filter_clause, filter_params = metadata_filter.to_sql_conditions()

        level_clause, level_params = _build_level_clause(chunk_level)

        exclude_clause = ""
        for i, cid in enumerate(exclude_ids):
            key = f"ex_{i}"
            filter_params[key] = cid
            exclude_clause += f" AND dc.chunk_id != :{key}"

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
                word_similarity(:query, dc.content) AS keyword_score
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE d.is_deleted = false
              AND word_similarity(:query, dc.content) > :trgm_threshold
              {level_clause}
              {filter_clause}
              {exclude_clause}
            ORDER BY keyword_score DESC
            LIMIT :top_k
        """

        params: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "trgm_threshold": _TRIGRAM_SIMILARITY_THRESHOLD,
        }
        params.update(level_params)
        params.update(filter_params)

        rows = await self._db.execute(query_sql, params)
        results: list[dict[str, Any]] = []
        for row in rows:
            r = self._row_to_result(row)
            r["keyword_score"] = float(row["keyword_score"])
            r["score"] = float(row["keyword_score"])
            results.append(r)
        return results

    async def _search_trigram_raw(
        self,
        query: str,
        chunk_level: str,
        top_k: int,
        metadata_filter: MetadataFilter | None,
        exclude_ids: set[str],
        start_rank: int,
    ) -> list[dict[str, Any]]:
        """trigram 検索の生結果（HybridSearch 用内部API）。

        rank は tsvector 結果の続き番号を割り当てる。
        """
        filter_clause = ""
        filter_params: dict[str, Any] = {}
        if metadata_filter is not None and not metadata_filter.is_empty():
            filter_clause, filter_params = metadata_filter.to_sql_conditions()

        level_clause, level_params = _build_level_clause(chunk_level)

        exclude_clause = ""
        for i, cid in enumerate(exclude_ids):
            key = f"rex_{i}"
            filter_params[key] = cid
            exclude_clause += f" AND dc.chunk_id != :{key}"

        query_sql = f"""
            SELECT
                dc.chunk_id,
                dc.document_id,
                dc.chunk_level,
                word_similarity(:query, dc.content) AS keyword_score
            FROM document_chunks dc
            JOIN documents d ON d.document_id = dc.document_id
            WHERE d.is_deleted = false
              AND word_similarity(:query, dc.content) > :trgm_threshold
              {level_clause}
              {filter_clause}
              {exclude_clause}
            ORDER BY keyword_score DESC
            LIMIT :top_k
        """

        params: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "trgm_threshold": _TRIGRAM_SIMILARITY_THRESHOLD,
        }
        params.update(level_params)
        params.update(filter_params)

        rows = await self._db.execute(query_sql, params)
        results: list[dict[str, Any]] = []
        for i, row in enumerate(rows):
            rank = start_rank + i
            results.append(
                {
                    "chunk_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "chunk_level": row["chunk_level"],
                    "rank_keyword": rank,
                    "rrf_score_keyword": 1.0 / (self.RRF_K + rank),
                    "keyword_score": float(row["keyword_score"]),
                }
            )
        return results

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
            suggestions.append("No keyword matches. Try semantic_search for meaning-based search or check spelling.")
        elif avg_score < 0.1:
            suggestions.append("Low keyword relevance. Try semantic_search for broader meaning matching.")
        elif avg_score > 0.5:
            suggestions.append(
                f"Strong keyword matches (avg {avg_score:.2f}). Results likely contain exact query terms."
            )

        if count > 0:
            from collections import Counter

            doc_ids = [r["document_id"] for r in results]
            multi_hit_docs = {doc_id: cnt for doc_id, cnt in Counter(doc_ids).items() if cnt >= 3}
            if multi_hit_docs:
                suggestions.append("Multiple hits from same file. Consider get_file_chunks for full context.")

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
