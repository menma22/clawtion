# clawtion 完全タスク分解（Phase 0 〜 Phase 1）

設計書 v3 + ソフトウェア開発における設計思想を基に、Phase 1完了までの全タスクを詳細に分解する。
各チャンクは独立して実行可能な単位であり、順番にクリアすることでプロジェクト全体が完成する。

---

## Phase 0: 基盤構築

### Chunk 0-1: リポジトリ初期化とプロジェクト骨格

- [ ] **0-1-1** GitHubリポジトリ作成（MIT LICENSE, .gitignore for Python）
- [ ] **0-1-2** `pyproject.toml` 作成
  - プロジェクト名: clawtion
  - Python 3.11+ 指定
  - 依存パッケージ定義（click, fastapi, uvicorn, sqlalchemy, alembic, asyncpg, pgvector, watchdog, pysbd, structlog, keyring, cryptography, httpx, tenacity, langdetect, pydantic, mcp）
  - dev依存（pytest, pytest-asyncio, testcontainers, ruff, mypy, pre-commit, pyright）
  - エントリーポイント: `clawtion = "clawtion.__main__:main"`
  - tool.mypy strict設定
  - tool.ruff設定（target-version py311, line-length 100, select rules）
- [ ] **0-1-3** ディレクトリ構造の作成
  ```
  src/clawtion/__init__.py
  src/clawtion/__main__.py
  src/clawtion/core/__init__.py
  src/clawtion/core/indexing/__init__.py
  src/clawtion/core/search/__init__.py
  src/clawtion/core/note/__init__.py
  src/clawtion/core/embedding/__init__.py
  src/clawtion/core/trash/__init__.py
  src/clawtion/core/db/__init__.py
  src/clawtion/interfaces/__init__.py
  src/clawtion/interfaces/cli/__init__.py
  src/clawtion/interfaces/mcp/__init__.py
  src/clawtion/interfaces/api/__init__.py
  src/clawtion/claude_integration/__init__.py
  src/clawtion/claude_integration/templates/
  src/clawtion/i18n/__init__.py
  src/clawtion/i18n/locales/
  src/clawtion/config/__init__.py
  src/clawtion/utils/__init__.py
  tests/unit/__init__.py
  tests/integration/__init__.py
  tests/e2e/__init__.py
  alembic/
  docs/
  ```
- [ ] **0-1-4** `README.md` 初期版（プロジェクト概要、Quick Startプレースホルダー）
- [ ] **0-1-5** `.pre-commit-config.yaml` 作成（ruff + ruff-format + mypy）

### Chunk 0-2: Docker + PostgreSQL + pgvector 環境

- [ ] **0-2-1** `docker-compose.yml` 作成
  - サービス: postgres（pgvector/pgvector:pg16イメージ）
  - ポート: 5432:5432
  - ボリューム: `~/.clawtion/pgdata` マウント
  - 環境変数: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
  - ヘルスチェック設定
- [ ] **0-2-2** DB接続モジュール `src/clawtion/core/db/connection.py` 作成
  - asyncpgベースの非同期接続プール
  - 接続URL設定の読み込み（環境変数 > config.yaml > デフォルト）
  - Protocol定義: `DatabaseConnection`（第11原則 DI対応）
  - コネクションプールの初期化・クリーンアップ
- [ ] **0-2-3** DB接続の単体テスト用フィクスチャ作成
  - testcontainersを使ったテスト用Postgres起動
  - pytest fixture定義

### Chunk 0-3: Alembicマイグレーション基盤

- [ ] **0-3-1** `alembic/alembic.ini` 作成
  - DB URLをconfig.yamlまたは環境変数から読み取る設定
- [ ] **0-3-2** `alembic/env.py` 作成
  - async対応（asyncpg使用）
  - clawtion設定ファイルからDB URLを取得するロジック
- [ ] **0-3-3** 初期マイグレーション `001_initial_schema.py` 作成
  - `documents` テーブル（設計書3.2節準拠: document_id, file_path, folder_path, title, file_extension, file_size_bytes, content_hash, tags, wikilinks, metadata, total_chunks, has_file_level, has_coarse_level, has_fine_level, last_indexed_at, is_deleted, deleted_at, created_at, updated_at）
  - `document_chunks` テーブル（設計書3.2節準拠: chunk_id, document_id, chunk_level, chunk_index, chunk_total, parent_chunk_id, heading_path, page_number, content, content_with_context, content_hash, embedding vector(768), embedding_model, embedding_dimensions, embedded_at, token_count, char_count, tsvector, metadata, created_at, UNIQUE制約）
  - `indexing_queue` テーブル（queue_id, document_id, file_path, operation, status, progress, priority, retry_count, max_retries, last_error, error_history, created_at, started_at, completed_at）
  - `trash` テーブル（trash_id, original_document_id, original_file_path, original_content, original_metadata, deleted_at, auto_purge_at）
  - `vault_settings` テーブル（key, value, updated_at）
  - pgvector拡張有効化: `CREATE EXTENSION IF NOT EXISTS vector`
  - 全インデックス作成（HNSW, GIN, B-tree）
- [ ] **0-3-4** マイグレーションの動作テスト
  - `alembic upgrade head` の実行確認
  - テーブル存在確認クエリ

### Chunk 0-4: 設定ファイル基盤

- [ ] **0-4-1** `src/clawtion/config/defaults.py` 作成
  - 全設定項目のデフォルト値をdataclassまたはPydantic BaseSettingsで定義
  - 設計書15.2節の全項目をカバー
- [ ] **0-4-2** `src/clawtion/config/loader.py` 作成
  - YAML読み込み（PyYAML）
  - 優先順位ロジック: 環境変数 > Vault固有設定 > グローバル設定 > デフォルト
  - Pydanticモデルでバリデーション
  - 型安全な設定アクセス（`config.embedding.output_dimensionality` 形式）
- [ ] **0-4-3** `src/clawtion/config/secrets.py` 作成
  - OS keychain（keyringライブラリ）でのAPIキー保存・取得
  - フォールバック: 暗号化ファイル（cryptography使用）
  - 環境変数からの取得（最優先）
- [ ] **0-4-4** 設定の単体テスト
  - デフォルト値の確認
  - 優先順位の確認（環境変数が勝つこと）
  - 不正値のバリデーションエラー確認

### Chunk 0-5: エラー処理基盤

- [ ] **0-5-1** `src/clawtion/core/exceptions.py` 作成
  - 基底クラス `ClawtionError(Exception)` — code, message, details属性
  - `DocumentNotFoundError(ClawtionError)`
  - `EmbeddingError(ClawtionError)`
  - `IndexingError(ClawtionError)`
  - `VaultError(ClawtionError)`
  - `ConfigError(ClawtionError)`
  - `QueueError(ClawtionError)`
  - 設計書11.5節の統一パターン準拠
- [ ] **0-5-2** エラーコードとHTTPステータスの対応マップ定義
  - DOCUMENT_NOT_FOUND → 404
  - VALIDATION_ERROR → 422
  - EMBEDDING_API_ERROR → 502
  - QUEUE_FULL → 429
  - 等

### Chunk 0-6: ロギング基盤

- [ ] **0-6-1** `src/clawtion/utils/logging.py` 作成
  - structlog設定（JSON出力 + コンソール出力切り替え）
  - ログレベル設定読み込み
  - コンテキスト変数バインディング（request_id等）
  - ログローテーション設定（日次、30日保持、gzip）
- [ ] **0-6-2** ログ出力ヘルパー
  - 3層ログ構造対応（ユーザー向け / 開発者向け / Claude向け）
  - API呼び出しのメトリクスログ（duration_ms, tokens等）

### Chunk 0-7: i18n基盤

- [ ] **0-7-1** `src/clawtion/i18n/translator.py` 作成
  - JSONファイルからの翻訳読み込み
  - `t("cli.init.welcome")` 形式のキーアクセス
  - プレースホルダー置換（`{pending}`, `{count}` 等）
  - 言語自動判定（LANG環境変数 → OS設定 → 英語フォールバック）
- [ ] **0-7-2** `src/clawtion/i18n/locales/en.json` 作成（初期キー一式）
- [ ] **0-7-3** `src/clawtion/i18n/locales/ja.json` 作成（初期キー一式）
- [ ] **0-7-4** i18nの単体テスト（キー取得、フォールバック、プレースホルダー）

### Chunk 0-8: CLI骨格

- [ ] **0-8-1** `src/clawtion/__main__.py` 作成
  - Clickベースのメインエントリーポイント
  - `--version` オプション
  - `--help` 自動生成
- [ ] **0-8-2** `src/clawtion/interfaces/cli/main.py` 作成
  - Clickグループ定義（clawtion コマンドのルート）
  - サブコマンドグループ登録（init, start, stop, status, index, queue, search, note, trash, mcp-serve, api-serve, doctor, logs, config, service）
- [ ] **0-8-3** `clawtion start` / `clawtion stop` 実装
  - docker-compose up -d / down の呼び出し
  - DB接続確認
  - マイグレーション自動実行
- [ ] **0-8-4** `clawtion status` 実装
  - Docker稼働状態チェック
  - DB接続チェック
  - キュー状態サマリー

### Chunk 0-9: GitHub Actions CI

- [ ] **0-9-1** `.github/workflows/ci.yml` 作成
  - lint job: ruff check + mypy --strict
  - test job: pytest tests/unit + tests/integration
  - マトリクス: Python 3.11, 3.12, 3.13 × ubuntu-latest
  - Postgresサービスコンテナ（pgvector/pgvector:pg16）
- [ ] **0-9-2** ブランチ保護ルール設定のドキュメント化

### Chunk 0-10: ドメインモデル定義（第10原則適用）

- [ ] **0-10-1** `src/clawtion/core/db/models.py` 作成
  - ドメインエンティティをdataclass/Pydanticで定義
  - `Document` エンティティ（IDで識別される）
  - `Chunk` 値オブジェクト（frozen=True、content_hashで同一性判定）
  - `QueueItem` エンティティ
  - `TrashItem` エンティティ
  - 型エイリアス: `ChunkLevel = Literal["file", "coarse", "fine"]`, `QueueStatus = Literal["pending", "processing", "partial", "completed", "failed"]`
- [ ] **0-10-2** リポジトリプロトコル定義（第9原則 Hexagonal Architecture）
  - `DocumentRepository(Protocol)` — save, get, list, delete, update
  - `ChunkRepository(Protocol)` — upsert, get_by_document, get_by_hash, delete_by_document
  - `QueueRepository(Protocol)` — add, get_next, update_status, update_progress
  - `TrashRepository(Protocol)` — save, get, list, purge_expired, restore

---

## Phase 1: コア機能実装

### Chunk 1-1: EmbeddingClient（Protocol + Gemini実装）

- [ ] **1-1-1** `src/clawtion/core/embedding/client.py` — Protocolインターフェース定義
  - `EmbeddingClient(Protocol)`:
    - `async embed_document(content: str) -> list[float]`
    - `async embed_query(query: str) -> list[float]`
    - `async embed_batch(contents: list[str]) -> list[list[float]]`
    - `model_name: str` (property)
    - `dimensions: int` (property)
- [ ] **1-1-2** `src/clawtion/core/embedding/gemini.py` — Gemini Embedding 2 クライアント実装
  - Google GenAI SDKを使用
  - task_type設定（RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY）
  - output_dimensionality設定（デフォルト768）
  - `use_manual_prefix_fallback` 対応（テキストプレフィックス追加）
  - レート制限対応（tenacityで指数バックオフリトライ）
  - APIキーの設定ファイル/環境変数からの取得
- [ ] **1-1-3** `src/clawtion/core/embedding/batch.py` — Batch API対応
  - バッチ閾値判定（デフォルト100チャンク超でBatch API使用）
  - 通常APIとBatch APIの振り分けロジック
  - Batch APIのジョブ送信・完了待ちロジック
- [ ] **1-1-4** `src/clawtion/utils/retry.py` — リトライユーティリティ
  - tenacity設定のラッパー
  - RateLimitError, TimeoutError, NetworkError対応
  - 最大5回、指数バックオフ（min 4s, max 60s）
- [ ] **1-1-5** Embeddingクライアントの単体テスト
  - モックを使ったProtocol準拠テスト
  - リトライロジックのテスト
  - batch閾値判定のテスト

### Chunk 1-2: チャンキングエンジン

- [ ] **1-2-1** `src/clawtion/utils/tokens.py` — トークン数カウントユーティリティ
  - tiktoken or 近似カウント（文字数ベース）
  - `count_tokens(text: str) -> int`
- [ ] **1-2-2** `src/clawtion/utils/language.py` — 言語判定ユーティリティ
  - langdetectラッパー
  - `detect_language(text: str) -> str` （"ja", "en" 等）
  - 設定のfallback_language対応
- [ ] **1-2-3** `src/clawtion/core/indexing/chunker.py` — チャンカー本体
  - `chunk_file_level(content: str, max_tokens: int = 1500) -> Chunk | None`
    - ファイル全体を1チャンク。上限超過時はNone返却
  - `chunk_coarse_level(content: str, target: int = 800, max_tokens: int = 1500) -> list[Chunk]`
    - 見出しベース分割（H1/H2/H3）
    - 超過時は段落で再分割
    - 短いセクションの結合
  - `chunk_file_with_fallback(content: str) -> list[Chunk]`
    - file粒度を試す → 1500トークン超ならcoarse fallback
  - コンテキスト注入: `content_with_context` の生成
    - フォーマット: `folder: {folder_path} | file: {title} | section: {heading_path} | text: {content}`
  - content_hash計算（SHA-256）
- [ ] **1-2-4** 構造保護ルール実装
  - コードブロック（```）検出・不分割
  - テーブル（|パイプ）検出・不分割
  - リスト項目検出
  - 引用ブロック（>）検出
  - 画像参照（![alt](path)）の周辺テキスト保持
- [ ] **1-2-5** Markdownパーサーヘルパー
  - frontmatter抽出（YAML部分）
  - 見出し階層抽出（heading_path生成）
  - wikilink抽出（[[note-name]] パターン）
- [ ] **1-2-6** チャンキングの単体テスト
  - 短いファイル → file粒度で1チャンク
  - 長いファイル → coarse fallback
  - コードブロック保護
  - heading_path正確性
  - content_with_context生成の検証

### Chunk 1-3: ファイルプロセッサ（形式別処理）

- [ ] **1-3-1** `src/clawtion/core/indexing/processors/__init__.py` + Protocol定義
  - `FileProcessor(Protocol)`:
    - `can_process(file_path: str) -> bool`
    - `extract_content(file_path: str) -> ExtractedContent`
    - `get_supported_extensions() -> list[str]`
  - `ExtractedContent` dataclass: content, metadata, file_type
- [ ] **1-3-2** `markdown_processor.py` — Markdown処理
  - .md, .markdown 対応
  - frontmatter抽出 → metadata
  - wikilink抽出
  - テキスト全体を返却
- [ ] **1-3-3** `text_processor.py` — プレーンテキスト処理
  - .txt 対応
  - 段落分割
- [ ] **1-3-4** `pdf_processor.py` — PDF処理
  - .pdf 対応
  - ページ数チェック
  - 6ページ以下: 1ファイルとして処理
  - 6ページ超: 6ページずつ分割
  - pypdfでテキスト抽出（キーワード検索用）
  - page_rangeメタデータ記録
- [ ] **1-3-5** `image_processor.py` — 画像処理
  - .png, .jpg, .jpeg, .webp 対応
  - サイズチェック（20MB制限）
  - メタ情報（ファイル名、サイズ）をcontent化
  - 1画像1チャンクとして返却
- [ ] **1-3-6** ファイル形式判定ロジック
  - 拡張子による第一判定
  - python-magic による第二判定（magic number）
  - 隠しファイル・除外フォルダの判定
- [ ] **1-3-7** プロセッサの単体テスト

### Chunk 1-4: DBリポジトリ実装（第9原則: Repository層）

- [ ] **1-4-1** `src/clawtion/core/db/document_repo.py` — DocumentRepository実装
  - asyncpg使用
  - CRUD操作（INSERT, SELECT, UPDATE, DELETE）
  - content_hashによる変更検知クエリ
  - folder_path/tags/extensionフィルタクエリ
- [ ] **1-4-2** `src/clawtion/core/db/chunk_repo.py` — ChunkRepository実装
  - UPSERT（INSERT ON CONFLICT DO UPDATE）
  - ベクトル検索クエリ（embedding <=> 演算子）
  - キーワード検索クエリ（tsvector @@ plainto_tsquery）
  - ハイブリッド検索クエリ（RRF CTE）
  - content_hashによる既存チャンク検索（dedup用）
  - document_idによる一括削除
- [ ] **1-4-3** `src/clawtion/core/db/queue_repo.py` — QueueRepository実装
  - ジョブ追加（priority付き）
  - 次のpendingジョブ取得（priority DESC, created_at ASC）
  - ステータス更新（processing, partial, completed, failed）
  - progress JSON更新
  - 異常終了ジョブの回復クエリ（status='processing' AND started_at < 5min ago）
- [ ] **1-4-4** `src/clawtion/core/db/trash_repo.py` — TrashRepository実装
  - ゴミ箱保存
  - 期限切れ自動パージ（auto_purge_at < now()）
  - 復元ロジック
- [ ] **1-4-5** リポジトリの統合テスト（testcontainers使用）

### Chunk 1-5: IndexingService

- [ ] **1-5-1** `src/clawtion/core/indexing/service.py` — IndexingService本体
  - 依存注入: ChunkRepository, DocumentRepository, QueueRepository, EmbeddingClient, FileProcessor群
  - `index_file(file_path: str)` メソッド
    1. ファイル形式判定 → 適切なFileProcessor選択
    2. content_hash計算 → DB比較 → 変更なしならスキップ
    3. FileProcessorでコンテンツ抽出
    4. チャンク分割（file粒度 + fallback）
    5. 各チャンクのcontent_hash → 既存チャンクdedup
    6. 新規/変更チャンクのみembedding生成
    7. DB UPSERT
    8. documentレコード更新（total_chunks, last_indexed_at等）
  - `reindex_file(file_path: str)` — 既存チャンク全削除 → 全件再生成
  - `delete_file(file_path: str)` — ゴミ箱移動 + DB soft delete
- [ ] **1-5-2** `src/clawtion/core/indexing/snapshot.py` — スナップショット方式
  - ファイル内容をメモリにコピーしてindexing
  - indexing完了後にファイル変更検知 → 再キュー
- [ ] **1-5-3** `src/clawtion/core/indexing/queue.py` — キューマネージャー
  - ワーカーループ（非同期）
  - ジョブの取得 → 処理 → ステータス更新
  - 中断・再開対応（progress JSONを使った途中再開）
  - チャンク単位トランザクション（1チャンク失敗しても他は保存）
  - リトライ上限管理（max_retries=3）
- [ ] **1-5-4** 起動時の異常終了回復
  - `on_startup_recover()` — processing状態のジョブをpartialに戻す
- [ ] **1-5-5** IndexingServiceの統合テスト
  - .mdファイルのindexing → DB確認
  - 差分更新（一部変更時に変更チャンクのみ再embed）
  - 中断再開のシミュレーション

### Chunk 1-6: ファイル監視（watchdog）

- [ ] **1-6-1** `src/clawtion/core/indexing/watcher.py` — FileWatcher実装
  - watchdogのObserver使用
  - 再帰監視
  - exclude_foldersフィルタ
  - イベントハンドラ:
    - ファイル作成 → indexingキュー追加（operation='index'）
    - ファイル変更 → content_hashチェック → 変更時に再index
    - ファイル削除 → delete処理 + ゴミ箱
    - ファイルリネーム → DB file_path更新
  - デバウンス（短時間の連続変更をまとめる）
- [ ] **1-6-2** Vault全体スキャン機能
  - アプリ起動時に全ファイルをスキャン
  - DB内レコードとの差分を検出
  - 新規/変更/削除ファイルをキューに追加
- [ ] **1-6-3** FileWatcherの単体テスト（一時ディレクトリ使用）

### Chunk 1-7: SearchService

- [ ] **1-7-1** `src/clawtion/core/search/service.py` — SearchService本体
  - 依存注入: ChunkRepository, EmbeddingClient
  - `semantic_search(query, granularity, top_k, filter)` → SearchResult
  - `keyword_search(query, granularity, top_k, filter)` → SearchResult
  - `hybrid_search(query, granularity, top_k, semantic_weight, filter)` → SearchResult
- [ ] **1-7-2** `src/clawtion/core/search/semantic.py` — ベクトル検索ロジック
  - クエリのembedding生成（task_type=RETRIEVAL_QUERY）
  - pgvectorのcosine distance検索
  - similarity_scoreの計算
- [ ] **1-7-3** `src/clawtion/core/search/keyword.py` — キーワード検索ロジック
  - PostgreSQL ts_rank_cd使用
  - plainto_tsquery('simple', query)
- [ ] **1-7-4** `src/clawtion/core/search/hybrid.py` — ハイブリッド検索（RRF）
  - Reciprocal Rank Fusion実装
  - k=60定数
  - semantic_weight設定による重み調整
  - FULL OUTER JOINによる結果結合
- [ ] **1-7-5** `src/clawtion/core/search/filter.py` — メタデータフィルタ
  - folder, tags, date_from/to, extension, custom metadata
  - SQLクエリ条件の動的組み立て
- [ ] **1-7-6** ナビゲーション情報の生成
  - has_previous/has_next判定
  - previous_chunk_id/next_chunk_id取得
  - all_chunks_in_file取得
- [ ] **1-7-7** suggestions_for_claude生成ロジック
  - avg_score < 0.5 → "Low semantic match..."
  - count == 0 → "No results..."
  - 同一document_id 3件以上 → "Multiple hits from same file..."
  - score_range広い → "Results vary in relevance..."
- [ ] **1-7-8** SearchServiceの統合テスト
  - テストデータ投入 → semantic_search → 結果検証
  - hybrid_searchのRRFスコア計算検証
  - メタデータフィルタの動作検証

### Chunk 1-8: NoteService（CRUD）

- [ ] **1-8-1** `src/clawtion/core/note/service.py` — NoteService実装
  - 依存注入: DocumentRepository, IndexingService, TrashService
  - `add_note(title, content, folder, tags)` → Document
    - .mdファイル作成（Vault内）
    - frontmatter生成（title, tags, created）
    - indexing即時実行 or キュー追加
  - `get_note(document_id)` → Note
  - `update_note(document_id, content)` → success
    - .mdファイル更新
    - 再indexingトリガー
  - `delete_note(document_id, permanent)` → success
    - permanent=False: ゴミ箱移動
    - permanent=True: 物理削除
  - `list_notes(folder, limit, offset)` → NoteList
  - `list_folders()` → list[str]
- [ ] **1-8-2** NoteServiceの単体テスト

### Chunk 1-9: TrashService

- [ ] **1-9-1** `src/clawtion/core/trash/service.py` — TrashService実装
  - `move_to_trash(document_id)` — ファイル内容をtrashテーブル保存、ファイル移動
  - `restore(trash_id)` — ファイル復元 + 再indexing
  - `list_trash()` → list[TrashItem]
  - `empty_trash()` — 全件物理削除
  - `auto_purge()` — 期限切れアイテムの自動削除
- [ ] **1-9-2** TrashServiceの単体テスト

### Chunk 1-10: CLI完全実装

- [ ] **1-10-1** `src/clawtion/interfaces/cli/init.py` — `clawtion init` コマンド
  - 対話的セットアップウィザード
  - Vaultパス選択（デフォルト~/Documents/clawtion-vault）
  - APIキー入力 → keychain保存
  - Docker Desktopチェック
  - DB起動（docker-compose up -d）
  - マイグレーション実行
  - Claude Code統合ファイル配置
  - MCP設定自動更新（~/.claude.json）
  - 初回Vaultスキャン → キュー追加
  - サービスモード選択
  - `--non-interactive` フラグ対応
- [ ] **1-10-2** `src/clawtion/interfaces/cli/index.py` — indexingコマンド群
  - `clawtion index <path>` — 指定パスindexing
  - `clawtion index now` — キュー即時処理
  - `clawtion index --batch` — Batch API強制
  - `clawtion reindex` — 全件再indexing
- [ ] **1-10-3** `src/clawtion/interfaces/cli/search.py` — 検索コマンド
  - `clawtion search "query"` — hybrid search（デフォルト）
  - `--semantic` / `--keyword` フラグ
  - `--folder`, `--tags`, `--top-k` オプション
  - 結果のフォーマット表示（ファイルパス、スコア、スニペット）
- [ ] **1-10-4** `src/clawtion/interfaces/cli/note.py` — ノート操作コマンド
  - add, get, update, delete, list
- [ ] **1-10-5** `src/clawtion/interfaces/cli/trash.py` — ゴミ箱コマンド
  - list, restore, empty
- [ ] **1-10-6** `src/clawtion/interfaces/cli/queue_cmd.py` — キュー管理コマンド
  - status, list, clear --failed, retry
- [ ] **1-10-7** `src/clawtion/interfaces/cli/doctor.py` — `clawtion doctor` コマンド
  - Docker状態チェック
  - DB接続チェック
  - スキーマバージョンチェック
  - APIキー検証
  - Claude Code設定チェック
  - Vault可用性チェック
  - ディスクスペースチェック
  - キュー状態サマリー
  - 総合判定（HEALTHY / WARNING / ERROR）
- [ ] **1-10-8** `src/clawtion/interfaces/cli/config.py` — 設定コマンド
  - `clawtion config` — 表示
  - `clawtion config edit` — $EDITORで開く
  - `clawtion config get <key>`
  - `clawtion config set <key> <value>`
  - `clawtion config set-key gemini` — APIキー設定
- [ ] **1-10-9** `src/clawtion/interfaces/cli/service.py` — サービス管理コマンド
  - `clawtion service install --mode <manual|scheduled|background>`
  - `clawtion service uninstall`
  - Windows: タスクスケジューラ登録/削除
  - macOS: launchd plist作成/削除
- [ ] **1-10-10** `src/clawtion/interfaces/cli/logs.py` — ログ表示コマンド
  - `clawtion logs` — 最新ログ表示
  - `--tail N` / `--level <level>` オプション

### Chunk 1-11: MCPサーバー実装

- [ ] **1-11-1** `src/clawtion/interfaces/mcp/server.py` — MCPサーバー本体
  - mcp Python SDK使用
  - stdio transport
  - ツール登録（全MCPツール）
  - エラーハンドリング → MCPプロトコルエラー変換
- [ ] **1-11-2** `src/clawtion/interfaces/mcp/tools.py` — MCPツール定義
  - 検索系: semantic_search, keyword_search, hybrid_search, metadata_filter
  - ナビゲーション系: get_file_chunks, get_neighbor_chunks
  - CRUD系: add_note, get_note, update_note, delete_note, list_notes, list_folders
  - 各ツールの入力スキーマ定義（JSON Schema）
  - 各ツールの出力フォーマット（SearchResult型準拠）
- [ ] **1-11-3** `clawtion mcp-serve` CLIコマンド
  - MCPサーバープロセス起動
- [ ] **1-11-4** MCPサーバーの統合テスト（stdioモックでツール呼び出し）

### Chunk 1-12: REST API実装（FastAPI）

- [ ] **1-12-1** `src/clawtion/interfaces/api/app.py` — FastAPIアプリケーション本体
  - アプリ初期化
  - ミドルウェア設定:
    - RequestIDMiddleware（X-Request-ID）
    - CORSMiddleware
  - 例外ハンドラー（ClawtionError → JSON変換）
  - ライフスパンイベント（DB接続プール初期化/クリーンアップ）
  - APIバージョニング: `/api/v1/` プレフィックス
- [ ] **1-12-2** 統一レスポンスモデル
  - `APIResponse(BaseModel, Generic[T])` — data, meta
  - `APIError(BaseModel)` — code, message, details
- [ ] **1-12-3** `src/clawtion/interfaces/api/routes/search.py` — 検索エンドポイント
  - `POST /api/v1/search/semantic`
  - `POST /api/v1/search/keyword`
  - `POST /api/v1/search/hybrid`
  - `GET /api/v1/search/metadata-filter`
  - リクエスト/レスポンスPydanticモデル定義
- [ ] **1-12-4** `src/clawtion/interfaces/api/routes/notes.py` — ノートエンドポイント
  - `POST /api/v1/notes`
  - `GET /api/v1/notes/{document_id}`
  - `PUT /api/v1/notes/{document_id}`
  - `DELETE /api/v1/notes/{document_id}`
  - `GET /api/v1/notes`
  - `GET /api/v1/folders`
- [ ] **1-12-5** `src/clawtion/interfaces/api/routes/chunks.py` — チャンクエンドポイント
  - `GET /api/v1/chunks/{document_id}/all`
  - `GET /api/v1/chunks/{chunk_id}/neighbors`
- [ ] **1-12-6** `src/clawtion/interfaces/api/routes/queue.py` — キューエンドポイント
  - `GET /api/v1/queue/status`
  - `POST /api/v1/queue/process`
  - `POST /api/v1/queue/retry/{queue_id}`
- [ ] **1-12-7** `src/clawtion/interfaces/api/routes/system.py` — システムエンドポイント
  - `GET /api/v1/health`
  - `GET /api/v1/version`
- [ ] **1-12-8** API認証ミドルウェア
  - APIキー方式（`Authorization: Bearer <api-key>`）
  - 認証スキップ: /health, /version
- [ ] **1-12-9** `clawtion api-serve --port 8080` CLIコマンド
  - uvicorn起動
- [ ] **1-12-10** REST APIの統合テスト（httpx AsyncClient使用）

### Chunk 1-13: Claude Code統合

- [ ] **1-13-1** `src/clawtion/claude_integration/templates/subagent.md` — サブエージェント定義テンプレート
  - 設計書10.2節の全内容
  - ツール一覧、Decision Framework、Output Format
- [ ] **1-13-2** `src/clawtion/claude_integration/templates/skill.md` — スキル定義テンプレート
  - 設計書10.3節の全内容
  - トリガー条件、呼び出し方法、注意事項
- [ ] **1-13-3** `src/clawtion/claude_integration/installer.py` — 統合ファイルインストーラー
  - `install()`: 
    - `~/.claude/agents/clawtion-knowledge.md` 配置
    - `~/.claude/skills/clawtion-search/SKILL.md` 配置
    - `~/.claude.json` のmcpServersに追加（既存設定をマージ）
  - `uninstall()`:
    - 上記ファイル削除
    - `~/.claude.json` からclawtionセクション削除
  - バックアップ機能（既存ファイルがある場合）
- [ ] **1-13-4** `clawtion uninstall` コマンド実装
  - 確認プロンプト
  - サービス停止
  - Claude Code統合ファイル削除
  - MCP設定削除
  - DB削除確認
  - APIキー削除

### Chunk 1-14: サービス管理（スケジューラ統合）

- [ ] **1-14-1** Windows タスクスケジューラ連携
  - schtasks /create による定期実行登録
  - PC起動時トリガー
  - 1時間ごとトリガー
  - 削除コマンド
- [ ] **1-14-2** macOS launchd連携
  - plist生成（~/Library/LaunchAgents/com.clawtion.scheduler.plist）
  - RunAtLoad + StartInterval設定
  - launchctl load/unload
- [ ] **1-14-3** バックグラウンドモード
  - ファイル監視 + workerの常駐起動
  - シグナルハンドリング（graceful shutdown）

### Chunk 1-15: テスト網羅

- [ ] **1-15-1** 単体テスト追加
  - コアロジック全クラスのテスト（カバレッジ80%以上目標）
  - チャンカーの網羅テスト（日本語、英語、混合、エッジケース）
  - RRFスコア計算のテスト
  - suggestions_for_claude生成のテスト
- [ ] **1-15-2** 統合テスト追加
  - indexing → search の一連フロー
  - ノート作成 → 検索ヒットの確認
  - ゴミ箱移動 → 検索からの除外確認
  - 差分更新（ファイル一部変更 → 変更チャンクのみ再embed確認）
- [ ] **1-15-3** E2Eテスト
  - `clawtion init --non-interactive` → index → search → 結果確認
  - MCP経由の検索テスト
  - REST API経由の全エンドポイントテスト
- [ ] **1-15-4** パフォーマンステスト
  - 100ファイルのindexing時間計測
  - 10,000チャンク規模での検索レイテンシ計測

### Chunk 1-16: ドキュメント

- [ ] **1-16-1** `docs/quickstart.md` — クイックスタートガイド
  - インストール手順（pipx）
  - 初期セットアップ（clawtion init）
  - 最初の検索体験
- [ ] **1-16-2** `docs/cli-reference.md` — CLI全コマンドリファレンス
- [ ] **1-16-3** `docs/mcp-reference.md` — MCPツール全リファレンス
- [ ] **1-16-4** `docs/api-reference.md` — REST API全リファレンス（OpenAPI自動生成も含む）
- [ ] **1-16-5** `docs/architecture.md` — アーキテクチャ概要図
- [ ] **1-16-6** `README.md` 完成版
  - 概要、特徴、インストール、Quick Start、コントリビュート、ライセンス

### Chunk 1-17: リリース準備

- [ ] **1-17-1** PyPIパッケージビルド設定
  - pyproject.toml の[build-system]設定
  - MANIFEST.in（翻訳ファイル、テンプレート含める）
  - `pip install -e .` の動作確認
- [ ] **1-17-2** バージョニング
  - `src/clawtion/__init__.py` に __version__ 定義
  - CHANGELOG.md 初期版
- [ ] **1-17-3** リリース前手動チェックリスト実行
  - クリーンインストール成功
  - init → search 動作確認
  - 100ファイル一括indexing
  - 強制終了 → 再開確認
  - uninstall完全削除確認
  - Windows / macOS 両方動作確認

---

## 設計原則チェックポイント（各チャンク完了時に確認）

以下の原則を各実装チャンクで遵守しているか確認する:

### アーキテクチャ（第9原則）
- [ ] コアロジック層がHTTP/CLI/MCPに依存していないか
- [ ] 依存の方向: Interface → Core → DB（逆方向なし）
- [ ] DBをモックに差し替えてコアロジックをテストできるか

### DI（第11原則）
- [ ] 全サービスクラスが依存をコンストラクタで受け取っているか
- [ ] 具体クラスではなくProtocolに依存しているか

### 型安全性
- [ ] mypy --strict が通るか
- [ ] Any型を使っていないか
- [ ] Pydanticでリクエスト/レスポンスを型定義しているか

### エラー処理
- [ ] ClawtionError階層を使っているか
- [ ] bare except: がないか

### ロギング
- [ ] structlogで構造化ログを出力しているか
- [ ] APIキー等のシークレットをログに含めていないか

### テスト
- [ ] 新規コードに対応するテストが存在するか
- [ ] テストがビジネスロジックを検証しているか（実装詳細ではなく）

---

## 進捗サマリー

| フェーズ | チャンク数 | 完了 | 残り |
|---------|-----------|------|------|
| Phase 0 | 10 | 0 | 10 |
| Phase 1 | 17 | 0 | 17 |
| **合計** | **27** | **0** | **27** |

最終目標: 全27チャンク完了 → `pip install clawtion` → `clawtion init` → Claude Codeからナレッジ検索が動作
