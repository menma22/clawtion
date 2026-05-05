"""ハイブリッド検索モジュール。

セマンティック検索（ベクトル）とキーワード検索（BM25近似）の結果を
Reciprocal Rank Fusion (RRF) で融合する。

RRF スコア = Σ (1 / (k + rank_i))
RRF 定数 k = 60
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from clawtion.utils.logging import get_logger

from .keyword import KeywordSearch
from .semantic import SemanticSearch

if TYPE_CHECKING:
    from clawtion.core.db.connection import DatabaseManager
    from clawtion.core.embedding.client import EmbeddingClient

    from .filter import MetadataFilter

logger = get_logger(__name__)


class HybridSearch:
    """セマンティック + キーワードのハイブリッド検索。

    Reciprocal Rank Fusion (RRF) アルゴリズムを使用して、
    両方の検索結果の順位を統合する。
    """

    RRF_K: int = 60

    def __init__(self, db: DatabaseManager, embedder: EmbeddingClient) -> None:
        self._semantic = SemanticSearch(db, embedder)
        self._keyword = KeywordSearch(db)

    async def search(
        self,
        query: str,
        chunk_level: str = "file",
        top_k: int = 10,
        semantic_weight: float = 0.5,
        metadata_filter: MetadataFilter | None = None,
    ) -> dict[str, Any]:
        """ハイブリッド検索を実行する。

        Args:
            query: 検索クエリ文字列
            chunk_level: 検索対象のチャンク粒度
            top_k: 返す最大件数
            semantic_weight: セマンティック検索の重み（0.0 = キーワードのみ, 1.0 = セマンティックのみ）
            metadata_filter: メタデータフィルタ

        Returns:
            ``{"results": [...], "context": {...}}`` の形式
        """
        start_time = time.time()

        # 1. クエリの埋め込みベクトルを生成
        try:
            embedding_result = await self._semantic._embedder.embed_query(query)
            query_embedding = embedding_result.embedding
        except Exception as e:
            logger.error("Failed to embed query for hybrid search", error=str(e))
            # embedding が失敗したらキーワード検索のみにフォールバック
            keyword_result = await self._keyword.search(
                query, chunk_level=chunk_level, top_k=top_k, metadata_filter=metadata_filter
            )
            keyword_result["context"]["tool"] = "hybrid_search (keyword fallback)"
            keyword_result["context"]["suggestions_for_claude"].append(
                "Semantic embedding failed. Results are keyword-only."
            )
            return keyword_result

        # 2. 両方の検索を実行
        try:
            semantic_results = await self._semantic.search_raw(
                query_embedding,
                chunk_level=chunk_level,
                top_k=100,
                metadata_filter=metadata_filter,
            )
        except Exception as e:
            logger.error("Semantic search failed in hybrid", error=str(e))
            semantic_results = []

        try:
            keyword_results = await self._keyword.search_raw(
                query,
                chunk_level=chunk_level,
                top_k=100,
                metadata_filter=metadata_filter,
            )
        except Exception as e:
            logger.error("Keyword search failed in hybrid", error=str(e))
            keyword_results = []

        # 3. RRF で融合
        fused = self._fuse_rrf(
            semantic_results,
            keyword_results,
            semantic_weight=semantic_weight,
        )

        # 4. 上位 top_k 件の詳細情報を取得
        chunk_ids = [item["chunk_id"] for item in fused[:top_k]]
        detailed_results = await self._fetch_chunk_details(chunk_ids)

        # 5. スコアを付与
        score_map = {item["chunk_id"]: item["rrf_score"] for item in fused}
        for result in detailed_results:
            result["score"] = score_map.get(result["chunk_id"], 0.0)
            result["rrf_score"] = result["score"]

        execution_time_ms = int((time.time() - start_time) * 1000)
        context = self._build_context(
            query=query,
            results=detailed_results,
            execution_time_ms=execution_time_ms,
            semantic_weight=semantic_weight,
            filter_applied=metadata_filter.to_dict() if metadata_filter else {},
        )

        return {"results": detailed_results, "context": context}

    async def _fetch_chunk_details(
        self, chunk_ids: list[str]
    ) -> list[dict[str, Any]]:
        """チャンクIDのリストから詳細情報を取得する。"""
        if not chunk_ids:
            return []

        # IN 句用にパラメータを構築
        params: dict[str, Any] = {}
        conditions: list[str] = []
        for i, cid in enumerate(chunk_ids):
            key = f"cid_{i}"
            params[key] = cid
            conditions.append(f":{key}")

        in_clause = ", ".join(conditions)

        query = f"""
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
            WHERE dc.chunk_id IN ({in_clause})
        """

        rows = await self._db.execute(query, params)

        # 元の順序を保持
        id_to_row = {row["chunk_id"]: row for row in rows}
        return [
            {
                "chunk_id": cid,
                "document_id": id_to_row[cid]["document_id"],
                "content": id_to_row[cid]["content"],
                "content_with_context": id_to_row[cid]["content_with_context"],
                "chunk_level": id_to_row[cid]["chunk_level"],
                "chunk_index": id_to_row[cid]["chunk_index"],
                "chunk_total": id_to_row[cid]["chunk_total"],
                "heading_path": id_to_row[cid]["heading_path"],
                "token_count": id_to_row[cid]["token_count"],
                "char_count": id_to_row[cid]["char_count"],
                "file_path": id_to_row[cid]["file_path"],
                "folder_path": id_to_row[cid]["folder_path"],
                "title": id_to_row[cid]["title"],
                "score": 0.0,  # 呼び出し元で設定
                "rrf_score": 0.0,
            }
            for cid in chunk_ids
            if cid in id_to_row
        ]

    def _fuse_rrf(
        self,
        semantic_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
        semantic_weight: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Reciprocal Rank Fusion で結果を融合する。

        各チャンクの RRF スコアを計算し、降順でソートして返す。

        RRF スコア = semantic_weight * (1 / (k + rank_s)) + (1 - semantic_weight) * (1 / (k + rank_k))
        """
        k = self.RRF_K
        score_map: dict[str, float] = {}

        for item in semantic_results:
            cid = item["chunk_id"]
            rank = item["rank_semantic"]
            score_map[cid] = score_map.get(cid, 0.0) + semantic_weight * (1.0 / (k + rank))

        for item in keyword_results:
            cid = item["chunk_id"]
            rank = item["rank_keyword"]
            score_map[cid] = score_map.get(cid, 0.0) + (1.0 - semantic_weight) * (1.0 / (k + rank))

        # スコア降順でソート
        sorted_items = sorted(score_map.items(), key=lambda x: x[1], reverse=True)

        return [
            {"chunk_id": cid, "rrf_score": score}
            for cid, score in sorted_items
        ]

    def _build_context(
        self,
        query: str,
        results: list[dict[str, Any]],
        execution_time_ms: int,
        semantic_weight: float,
        filter_applied: dict[str, Any],
    ) -> dict[str, Any]:
        """診断コンテキストを構築する。"""
        scores = [r.get("score", 0.0) for r in results]
        count = len(results)
        score_range: list[float] = [min(scores), max(scores)] if scores else [0.0, 0.0]
        avg_score = sum(scores) / count if count > 0 else 0.0

        suggestions: list[str] = [
            f"Hybrid search with semantic_weight={semantic_weight}",
        ]
        if count == 0:
            suggestions.append("No results. Try broadening query or removing filters.")
        elif avg_score < 0.3:
            suggestions.append(
                "Low overall relevance. Try adjusting semantic_weight or broadening query."
            )
        else:
            suggestions.append(
                f"Hybrid search results balanced (semantic:keyword = {semantic_weight:.1f}:{1.0-semantic_weight:.1f})."
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
            "tool": "hybrid_search",
            "query": query,
            "embedding_model": self._semantic._embedder.model_name,
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
