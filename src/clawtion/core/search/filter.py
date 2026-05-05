"""メタデータフィルタビルダー。

検索クエリに付与するフィルタ条件を構築する。
フォルダパス・タグ・日付範囲・拡張子・カスタムメタデータに対応する。
"""

from __future__ import annotations

from typing import Any


class MetadataFilter:
    """検索用メタデータフィルタ。

    チェーン可能なビルダーパターンを採用::

        filter = (
            MetadataFilter()
            .by_folder("tech/rag")
            .by_tags(["rag", "agentic"])
            .by_date_range("2026-01-01", "2026-06-01")
            .by_extension("md")
        )
        conditions, params = filter.to_sql_conditions()
    """

    def __init__(
        self,
        folder: str | None = None,
        tags: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        extension: str | None = None,
        custom: dict[str, Any] | None = None,
    ) -> None:
        self._folder = folder
        self._tags = tags
        self._date_from = date_from
        self._date_to = date_to
        self._extension = extension
        self._custom = custom or {}

    def by_folder(self, folder: str) -> MetadataFilter:
        """フォルダパスでフィルタする。

        ``LIKE`` マッチングを使用するため、末尾に ``/`` を付けると
        そのフォルダ直下のみ、付けなければ前方一致になる。

        例:
            ``"tech/"`` → tech フォルダ直下のみ
            ``"tech"`` → tech から始まる全フォルダ
        """
        self._folder = folder
        return self

    def by_tags(self, tags: list[str]) -> MetadataFilter:
        """タグでフィルタする。指定されたタグをすべて含むドキュメントに絞り込む。"""
        self._tags = tags
        return self

    def by_date_range(self, date_from: str | None, date_to: str | None) -> MetadataFilter:
        """更新日時でフィルタする（ISO 8601 日付文字列）。"""
        self._date_from = date_from
        self._date_to = date_to
        return self

    def by_extension(self, extension: str) -> MetadataFilter:
        """ファイル拡張子でフィルタする（例: ``"md"``）。"""
        self._extension = extension
        return self

    def by_custom(self, key: str, value: Any) -> MetadataFilter:
        """カスタムメタデータフィールドでフィルタする。"""
        self._custom[key] = value
        return self

    def to_sql_conditions(self) -> tuple[str, dict[str, Any]]:
        """SQL WHERE 条件とパラメータを生成する。

        Returns:
            ``(where_clause, params_dict)`` のタプル。
            ``where_clause`` は ``AND`` で連結された条件文字列。
            条件がない場合は ``("", {})`` を返す。
        """
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if self._folder is not None:
            # 末尾が / の場合は完全一致、それ以外は前方一致
            if self._folder.endswith("/"):
                conditions.append("d.folder_path = :filter_folder")
                params["filter_folder"] = self._folder
            else:
                conditions.append("d.folder_path LIKE :filter_folder_pattern")
                params["filter_folder_pattern"] = f"{self._folder}%"

        if self._tags is not None and len(self._tags) > 0:
            conditions.append("d.tags @> :filter_tags::jsonb")
            import json

            params["filter_tags"] = json.dumps(self._tags, ensure_ascii=False)

        if self._date_from is not None:
            conditions.append("d.updated_at >= :filter_date_from::timestamptz")
            params["filter_date_from"] = self._date_from

        if self._date_to is not None:
            conditions.append("d.updated_at <= :filter_date_to::timestamptz")
            params["filter_date_to"] = self._date_to

        if self._extension is not None:
            ext = self._extension if self._extension.startswith(".") else f".{self._extension}"
            conditions.append("d.file_extension = :filter_extension")
            params["filter_extension"] = ext.lower()

        for key, value in self._custom.items():
            param_name = f"filter_custom_{key.replace(' ', '_')}"
            conditions.append(f"d.metadata @> :{param_name}::jsonb")
            import json

            params[param_name] = json.dumps({key: value})

        where_clause = " AND ".join(conditions)
        if where_clause:
            where_clause = " AND " + where_clause

        return (where_clause, params)

    def to_jsonb_condition(self) -> str:
        """簡易的な JSONB 包含条件を生成する。

        チャンクレベルのメタデータフィルタ用。
        """
        filter_parts: list[str] = []
        import json

        if self._folder is not None:
            filter_parts.append(
                json.dumps({"folder_path": self._folder}, ensure_ascii=False)
            )

        if self._tags is not None and len(self._tags) > 0:
            filter_parts.append(
                json.dumps({"tags": self._tags}, ensure_ascii=False)
            )

        if self._extension is not None:
            ext = self._extension if self._extension.startswith(".") else f".{self._extension}"
            filter_parts.append(
                json.dumps({"file_extension": ext}, ensure_ascii=False)
            )

        if not filter_parts:
            return "'{}'::jsonb"

        if len(filter_parts) == 1:
            return f"'{filter_parts[0]}'::jsonb"

        # 複数条件を結合（すべての条件が JSONB 包含でマッチすることを要求）
        combined = " || ".join(f"'{p}'::jsonb" for p in filter_parts)
        return combined

    def is_empty(self) -> bool:
        """フィルタ条件が空かどうかを返す。"""
        return all(
            x is None or x == {} or x == []
            for x in [self._folder, self._tags, self._date_from, self._date_to, self._extension, self._custom]
        )

    def to_dict(self) -> dict[str, Any]:
        """フィルタ条件を dict として返す（ログ出力・診断情報用）。"""
        result: dict[str, Any] = {}
        if self._folder is not None:
            result["folder"] = self._folder
        if self._tags:
            result["tags"] = self._tags
        if self._date_from:
            result["date_from"] = self._date_from
        if self._date_to:
            result["date_to"] = self._date_to
        if self._extension:
            result["extension"] = self._extension
        if self._custom:
            result["custom"] = self._custom
        return result

    def __repr__(self) -> str:
        return f"MetadataFilter({self.to_dict()})"
