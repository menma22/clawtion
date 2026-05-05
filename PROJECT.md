# clawtion プロジェクト文書

---

## PART 1: BASE DESIGN DOCUMENT (現時点の設計真実)

### 1. プロジェクト要件

**目的:** Claude Codeから操作可能なローカル知識ベース + 人間が使えるメモ帳アプリ

**コア問題:**
- AIエージェントがユーザーのローカル情報（ノート、文書）を参照できない
- 既存のRAGソリューションはセットアップが複雑
- プライバシーを保ちつつAI検索したい

**理想状態:**
- `pip install clawtion` + `clawtion init` で5分でセットアップ完了
- Claude Codeが「私のノートのXについて教えて」で検索可能
- 人間もCLI/REST APIでノートを検索・管理可能

**ターゲットユーザー:**
- Claude Codeを日常的に使う開発者・知識労働者
- ObsidianユーザーでAI機能を追加したい層
- データプライバシー重視のユーザー

**絶対要件:**
- ローカル完結（クラウド同期不要）
- PostgreSQL + pgvector によるベクトル検索
- Gemini Embedding 2 による埋め込み生成
- 3層アーキテクチャ（コア/インターフェース/ストレージ）
- MCPプロトコルによるClaude Code統合
- 構造化ログ（structlog）による可観測性

### 2. 現在のシステム仕様とステータス

#### 実装済みコンポーネント

**設定システム:**
- `config/defaults.py`: 全設定のデフォルト値（vault, ui, embedding, chunking, indexing, trash, logging, service, backup, graphrag, contextual_retrieval）
- `config/loader.py`: 4層オーバーライドチェーン（デフォルト → ~/.clawtion/config.yaml → vault/.clawtion/config.yaml → 環境変数）
  - `get_config()`: マージ済み設定を返す（キャッシュあり）
  - `get(key_path, default)`: ドット区切りキーで設定値を取得
  - `reload_config()`: キャッシュクリア
- `config/secrets.py`: 3層シークレット管理（環境変数 → OS keychain → 暗号化ファイル）
  - `get_secret(key)`, `set_secret(key, value)`, `delete_secret(key)`

**ユーティリティ:**
- `utils/exceptions.py`: ClawtionError階層（DocumentNotFoundError, EmbeddingError, IndexingError, VaultError, ValidationError, QueueError）
- `utils/logging.py`: 3層構造化ログ（structlog + TimedRotatingFileHandler + ConsoleRenderer）
  - `setup_logging()`, `get_logger(name)`
- `utils/retry.py`: 指数バックオフ + ジッター付きリトライ
  - `RetryConfig` dataclass、`with_retry()`、`@retryable` デコレータ
- `utils/tokens.py`: トークンカウント（CJK考慮の文字ベース推定）
  - `count_tokens(text, model)`
- `utils/language.py`: langdetectによる言語検出（"ja" フォールバック）
  - `detect_language(text)`, `is_cjk(text)`

**コアIndexingService:**
- `core/indexing/chunker.py`: 3粒度チャンキングエンジン（マルチレゾリューション対応）
  - `Chunk` frozen dataclass（level, content, content_with_context, content_hash, chunk_index, chunk_total, heading_path, token_count, char_count）
  - `chunk_file_level()`: ファイル全体1チャンク、1500トークン超過時は空リスト
  - `chunk_coarse_level()`: H1/H2/H3見出しベース分割、超過時は段落フォールバック
  - `chunk_fine_level()`: pysbdによる文単位分割、target=100トークン
  - `chunk_file()`: メインエントリポイント（configパラメータ対応）
    - Phase 2（multi_resolution enabled）: configで有効な全レベル（file/coarse/fine）を同時生成
    - Phase 1（multi_resolution disabled）: file→coarseフォールバック戦略
  - `build_context()`: Embedding入力用コンテキスト注入（`folder: X | file: Y | section: Z | text: ...`）
  - 構造保護: コードブロック・テーブルは分割禁止、SHA-256ハッシュ
  - `merge_short_adjacent()`: 短すぎる隣接チャンクの結合（target_min=200）
- `core/indexing/snapshot.py`: スナップショット方式ファイル読み込み
  - `FileSnapshot` frozen dataclass（file_path, content, content_hash, taken_at）
  - `take_snapshot()`: バッファリング読み込み + SHA-256 + タイムスタンプ
  - `has_changed()`: 現在ファイルとスナップショットのハッシュ比較
  - `compute_content_hash()`: SHA-256ユーティリティ
- `core/indexing/queue.py`: キュー管理
  - `QueueManager`（Constructor DI for DatabaseManager）
  - `enqueue()`: ジョブ追加（document_id自動解決対応）
  - `dequeue()`: CTE + FOR UPDATE SKIP LOCKED による信頼性のある取得
  - `update_status()`: ステータス遷移（completed時はcompleted_at設定、エラー時はerror_history蓄積）
  - `update_progress()`: 中断・再開用JSONB進捗保存（ステータスをpartialに変更）
  - `get_pending()`, `get_failed()`, `retry()`, `clear_failed()`, `get_stats()`
- `core/indexing/watcher.py`: watchdogファイル監視
  - `FileWatcher`（vault_path, queue_manager, exclude_folders）
  - `start()`/`stop()`/`is_running()`: Observerライフサイクル
  - `_ClawtionEventHandler`: on_created/on_modified/on_deleted/on_moved
  - デバウンス（2秒間隔）、除外フォルダ対応、サポート拡張子フィルタ
- `core/indexing/service.py`: IndexingService（メインオーケストレーター）
  - `index_file()`: 完全パイプライン（hashチェック→スナップショット→chunk→dedup→embed→upsert）
    - `chunk_file()`にconfigを渡してマルチレゾリューション対応
    - チャンクレベル検出（file/coarse/fine） → has_*_levelフラグをDBに保存
  - `index_folder()`: フォルダ再帰indexing（.clawtion除外）
  - `reindex_file()`, `reindex_all()`: 強制再indexing
  - `delete_file()`: 論理削除 + trashテーブル保存 + chunk削除
  - `process_queue()`: キュー内全pendingジョブ逐次処理
  - `scan_vault()`: Vault全体スキャン（新規/変更/削除検出 → キュー追加）
  - `resume_indexing()`: 中断ジョブ再開（進捗チェックポイント対応）
  - チャンク重複排除: content_hashによる既存embedding再利用
  - Batch Embedding + 個別フォールバック（with_retry統合）
  - _TextFileProcessor: デフォルトテキスト抽出プロセッサ

**コア検索サービス:**
- `core/search/filter.py`: メタデータフィルタビルダー
  - `MetadataFilter`（チェーン可能ビルダーパターン）
  - `by_folder()`, `by_tags()`, `by_date_range()`, `by_extension()`, `by_custom()`
  - `to_sql_conditions()` → `(WHERE句, params dict)`
  - `to_jsonb_condition()` → JSONB包含条件
- `core/search/semantic.py`: セマンティック検索
  - `SemanticSearch`（pgvector `<=>` コサイン距離）
  - `search()`: embedding生成 → SQL実行 → context構築（suggestions_for_claude含む）
  - `search_raw()`: HybridSearch用内部API（rank + RRFスコア部分）
  - `_build_context()`: スコア範囲・平均・文書重複からClaude向けサジェスチョン生成
- `core/search/keyword.py`: キーワード検索
  - `KeywordSearch`（PostgreSQL tsvector, `plainto_tsquery`, `ts_rank_cd`）
  - `search()`: 全文検索SQL実行 → context構築
  - `search_raw()`: HybridSearch用内部API
- `core/search/hybrid.py`: ハイブリッド検索（RRF融合）
  - `HybridSearch`（セマンティック + キーワードのRRF融合）
  - `search()`: 両方の検索を並行実行 → RRFスコア計算 → 詳細取得
  - `_fuse_rrf()`: RRF = Σ (1 / (k + rank))、k=60、semantic_weight対応
  - Embedding失敗時はキーワード検索にフォールバック
- `core/search/service.py`: 検索統合インターフェース
  - `SearchService`: semantic/keyword/hybrid検索3種を統合
  - `SearchResult` dataclass（results + context）
  - `NavigationInfo` dataclass（file_path, has_previous/next, chunk_ids）
  - `get_file_chunks()`, `get_neighbor_chunks()`, `get_parent_chunk()`
  - `list_folders()`, `list_notes()`

**コアノートサービス:**
- `core/note/service.py`: ノートCRUDサービス
  - `NoteService`（Constructor DI: DatabaseManager, vault_path, IndexingService）
  - `create()`: .md作成 + documents INSERT + 自動indexing
  - `get()`: DB情報 + ファイル本文読み込み
  - `update()`: ファイル更新 + content_hash更新 + 自動reindexing
  - `delete()`: 完全削除（permanent=true）または論理削除+trash保存
  - `list_notes()`, `list_folders()`

**コアゴミ箱サービス:**
- `core/trash/service.py`: ゴミ箱管理
  - `TrashService`（Constructor DI: DatabaseManager, vault_path）
  - `list_items()`: 全ゴミ箱アイテム一覧（deleted_at降順）
  - `restore()`: ファイル復元 + documentsテーブル復元 + trash削除（既存ファイルは.bak保存）
  - `empty()`: 全アイテム物理削除
  - `purge_expired()`: auto_purge_at <= now のアイテム削除

**REST API（FastAPI）:**
- `interfaces/api/app.py`: FastAPIアプリケーションファクトリ
  - `create_app()`: 完全構成済みFastAPIインスタンスを返す
  - CORSミドルウェア（全オリジン許可）
  - Request IDミドルウェア（X-Request-IDヘッダー）
  - グローバル例外ハンドラ（ClawtionError → HTTPステータス + `{error: {code, message, details}}`）
  - 統一レスポンスラッパー: `APIResponse[T](data, meta)` / `APIError(code, message, details)`
  - Lifespanによるサービス初期化: DatabaseManager, GeminiEmbeddingClient, SearchService, NoteService, TrashService, QueueManagerをapp.stateに設定
  - `GET /health`, `GET /version` エンドポイント
  - 全ルーターを `/api/v1/` プレフィックスで登録
- `interfaces/api/routes/search.py`: 検索エンドポイント
  - `POST /api/v1/search/semantic` - ベクトル類似度検索
  - `POST /api/v1/search/keyword` - 全文キーワード検索
  - `POST /api/v1/search/hybrid` - ハイブリッド検索（ベクトル + キーワード）
  - `GET /api/v1/chunks/{document_id}/all` - ドキュメントの全チャンク取得
  - `GET /api/v1/chunks/{chunk_id}/neighbors` - 前後チャンク取得
  - `GET /api/v1/chunks/{chunk_id}/parent` - 親チャンク取得
  - 全検索に実行時間計測メタデータ付与
- `interfaces/api/routes/notes.py`: ノートCRUDエンドポイント
  - `POST /api/v1/notes` - 新規ノート作成（201 Created）
  - `GET /api/v1/notes/{document_id}` - ノート取得
  - `PUT /api/v1/notes/{document_id}` - ノート更新（content, title, folder, tags）
  - `DELETE /api/v1/notes/{document_id}?permanent=false` - ノート削除（ゴミ箱経由/完全削除）
  - `GET /api/v1/notes` - ノート一覧（folderフィルタ、limit/offsetページネーション）
  - `GET /api/v1/folders` - フォルダ一覧
- `interfaces/api/routes/queue.py`: キュー管理エンドポイント
  - `GET /api/v1/queue/status` - キュー統計（pending/processing/completed/failed/cancelled）
  - `GET /api/v1/queue/pending` - ペンディングジョブ一覧
  - `GET /api/v1/queue/failed` - 失敗ジョブ一覧
  - `POST /api/v1/queue/process` - キュー処理トリガー
  - `POST /api/v1/queue/retry/{queue_id}` - 特定ジョブリトライ
  - `POST /api/v1/queue/clear-failed` - 全失敗ジョブクリア
  - `GET /api/v1/metrics` - システムメトリクス（総ドキュメント数、チャンク数、キュー状態）
- `interfaces/api/cli_serve.py`: CLIエントリポイント
  - `run_api_server(host, port)`: uvicornでFastAPIサーバー起動
  - `run_mcp_server()`: MCPサーバー起動（ModuleNotFoundError時に明確なエラーメッセージ）

**Claude Code統合:**
- `claude_integration/installer.py`: ClaudeCodeIntegrationInstallerクラス
  - `install()`: サブエージェント定義、スキル定義、MCP設定をインストール
  - `uninstall()`: 全統合ファイルを削除（MCP設定はclawtionセクションのみ削除、他は維持）
  - `is_installed()`: 各コンポーネントのインストール状態を確認
  - `_write_subagent_definition()`: ~/.claude/agents/clawtion-knowledge.md を配置
  - `_write_skill_definition()`: ~/.claude/skills/clawtion-search/SKILL.md を配置
  - `_update_claude_config()`: ~/.claude.json の mcpServers.clawtion を更新/作成
  - 既存ファイルのバックアップ機能付き
- `claude_integration/templates/subagent.md`: サブエージェント定義テンプレート
  - YAML frontmatter: name, description, tools（MCPツール一覧）, model: sonnet, memory: project
  - 検索戦略の意思決定フレームワーク（クエリ種類に応じた手法選択）
  - マルチステップ検索戦略（初回失敗時の代替手段）
  - 結果合成ルール（main agentに返すべき内容/返すべきでない内容）
  - 出力フォーマット指定（Summary, Key Findings, Relevant Files, Suggested Next Steps）
- `claude_integration/templates/skill.md`: スキル定義テンプレート
  - トリガー条件（ユーザーが自分のノートについて質問したとき）
  - 呼び出し方法（subagent_type='clawtion-knowledge'）
  - 禁止事項（MCPツール直接呼び出し禁止、一般知識で回答しない）

**コア名前空間サービス（Namespace）:**
- `core/namespace/service.py`: 論理パーティション管理サービス
  - `NamespaceService`（Constructor DI: DatabaseManager）
  - `create(name, description)`: 名前空間作成（一意性制約、100文字制限）
  - `list_all()`: 全名前空間一覧（チャンク数付き）
  - `get(namespace_id)`: 単一名前空間取得
  - `delete(namespace_id)`: 名前空間削除（ON DELETE SET NULL）
  - `assign_chunk(chunk_id, namespace_id)`: 単一チャンク割り当て
  - `assign_document(document_id, namespace_id)`: ドキュメント全チャンク割り当て
  - `get_chunks(namespace_id)`: 名前空間内全チャンク取得
  - `NamespaceInfo` frozen dataclass（namespace_id, name, description, created_at, chunk_count）

**コアGraphRAGサービス（Graph）:**
- `core/graph/service.py`: エンティティ抽出・グラフ探索サービス
  - `GraphService`（Constructor DI: DatabaseManager, EmbeddingClient）
  - `extract_entities(chunk_id)`: ヒューリスティックエンティティ抽出（既知辞書 + 4種正規表現パターン）
  - `add_entity(name, entity_type, description)`: エンティティ追加（重複時は既存ID返却、embedding自動生成）
  - `add_relation(source_id, target_id, relation_type, weight, chunk_id)`: リレーション追加（重複防止）
  - `graph_search(starting_entity, max_hops, relation_types)`: 再帰的SQL CTEによるNホップグラフ探索
  - `find_related(chunk_id, max_hops)`: エンティティ共有に基づく関連チャンク検索
  - `extract_and_store(chunk_id)`: 抽出→保存→共起関係生成の一括実行
  - Entity + Relation 2テーブル構成、エンティティベクトルはembedding自動生成

**コアノート編集サービス:**
- `core/note/editor.py`: 見出しベースノート編集
  - `NoteEditor`（Constructor DI: vault_path）
  - `update_section(file_path, target_heading, new_content, match_context)`: 見出し指定セクション置換
  - `append_content(file_path, content, position, target_heading)`: 3ポジション追記（end/after_heading/before_heading）
  - `_find_heading_position()`: 正規表現によるMarkdown見出し検出 + match_context曖昧性解消

**MCP名前空間ツール:**
- `create_namespace(name, description)`: 名前空間作成
- `list_namespaces()`: 名前空間一覧
- `assign_to_namespace(document_id, namespace_id)`: ドキュメント → 名前空間割り当て

**MCP GraphRAGツール（Phase 2）:**
- `graph_search(starting_entity, max_hops=2, relation_types=None)`: エンティティグラフのNホップ探索（再帰的SQL CTE）
- `get_related_chunks(chunk_id, max_hops=1)`: エンティティ共有に基づく関連チャンク検索
- `extract_entities_from_chunk(chunk_id, store=False)`: チャンクからのエンティティ抽出（store=TrueでDB保存＋共起関係生成）

**MCPノート編集ツール（Phase 2）:**
- `update_note_section(document_id, target_heading, new_content, match_context=None)`: 見出し指定によるセクション内容の置換
- `append_to_note(document_id, content, position="end", target_heading=None)`: ノート末尾/見出し前後へのコンテンツ追記

**CLI名前空間コマンド:**
- `clawtion namespace create <name> [--description]`: 名前空間作成
- `clawtion namespace list`: 名前空間一覧
- `clawtion namespace assign <document_id> <namespace_id>`: 割り当て

**検索名前空間フィルタ:**
- 全検索（semantic/keyword/hybrid）に `namespace` パラメータ追加
- MetadataFilter.by_namespace() で名前空間フィルタ条件構築
- CLI `--namespace` オプション、MCPツール `namespace` パラメータ

**データベースマイグレーション:**
- `alembic/versions/001_initial_schema.py`: 初期スキーマ作成
  - documentsテーブル（UUID PK, file_path, folder_path, title, file_extension, file_size_bytes, content_hash, tags JSONB, wikilinks JSONB, metadata JSONB, total_chunks, has_file_level/coarse/fine, last_indexed_at, is_deleted, deleted_at, created_at, updated_at）
  - document_chunksテーブル（UUID PK, document_id FK, chunk_level, chunk_index, chunk_total, parent_chunk_id self-ref FK, heading_path, page_number, content, content_with_context, content_hash, embedding vector(768), embedding_model, embedding_dimensions, embedded_at, token_count, char_count, tsvector GENERATED ALWAYS, metadata JSONB, created_at, UNIQUE(document_id, chunk_level, chunk_index)）
  - indexing_queueテーブル（queue_id PK, document_id FK, file_path, operation, status, progress JSONB, priority, retry_count, max_retries, last_error, error_history JSONB, timestamps）
  - trashテーブル（trash_id PK, original_document_id, original_file_path, original_content, original_metadata JSONB, deleted_at, auto_purge_at）
  - vault_settingsテーブル（key PK, value JSONB, updated_at）
  - インデックス: HNSW on embedding, GIN on tsvector, GIN on tags, B-tree各種
- `alembic/versions/002_namespace_support.py`: 名前空間スキーマ追加
  - namespacesテーブル（UUID PK, name VARCHAR(100) UNIQUE, description TEXT, created_at）
  - document_chunksにnamespace_id UUID FK追加（ON DELETE SET NULL）
  - idx_chunks_namespace インデックス追加
- `alembic/versions/003_graph_rag.py`: GraphRAG エンティティ・リレーションテーブル追加
  - entitiesテーブル（entity_id UUID PK, name VARCHAR(200), entity_type VARCHAR(50), description TEXT, embedding vector(768), created_at, UNIQUE(name, entity_type))
  - relationsテーブル（relation_id UUID PK, source_entity_id UUID FK→entities CASCADE, target_entity_id UUID FK→entities CASCADE, relation_type VARCHAR(100), weight FLOAT DEFAULT 1.0, source_chunk_id UUID FK→document_chunks SET NULL, created_at）
  - インデックス: HNSW on entities.embedding, B-tree各種 on relations

### 3. 詳細アーキテクチャ

```
3層アーキテクチャ:

[Claude Code] ←→ [インターフェース層] ←→ [コアロジック層] ←→ [ストレージ層]
   ↑                    │                     │
   │  MCP/stdio         │ CLI / REST API      │ Indexing/Search/Note
   │                    │                     │
   └── subagent ── skill (claude_integration)

設定層:
  defaults.py → ~/.clawtion/config.yaml → vault/.clawtion/config.yaml → CLAWTION_* env vars
                                                                              ↓
                                                                       secrets.py
                                                                    (keychain/enc/env)

Claude Code 統合構造:
  [Claude Code メインエージェント]
         ↓ Skill検知 → Subagent委譲
  [clawtion-knowledge サブエージェント]  ← 専用コンテキスト
         ↓ MCPツール呼び出し
  [clawtion MCPサーバー]  ← 生のデータ操作
         ↓
  [Postgres + pgvector DB]
```

### 4. ディレクトリ構造

```
clawtion/
├── alembic.ini                           # Alembic設定
├── alembic/
│   ├── env.py                            # 非同期Alembic環境
│   └── versions/
│       └── 001_initial_schema.py         # 初期スキーママイグレーション
├── src/clawtion/
│   ├── config/
│   │   ├── defaults.py                   # デフォルト設定辞書
│   │   ├── loader.py                     # 設定ローダー（オーバーライドチェーン）
│   │   └── secrets.py                    # シークレット管理
│   ├── utils/
│   │   ├── exceptions.py                 # ClawtionError階層
│   │   ├── logging.py                    # structlog 3層ログ
│   │   ├── retry.py                      # リトライユーティリティ
│   │   ├── tokens.py                     # トークンカウント
│   │   └── language.py                   # 言語検出
│   ├── core/
│   │   ├── db/
│   │   │   ├── connection.py             # DatabaseManager（async engine + session）
│   │   │   ├── models.py                 # SQLAlchemyモデル定義
│   │   │   └── migrations.py            # マイグレーションユーティリティ
│   │   ├── embedding/
│   │   │   ├── client.py                 # EmbeddingClient Protocol + EmbeddingResult
│   │   │   ├── gemini.py                 # GeminiEmbeddingClient実装
│   │   │   └── batch.py                  # Batch API対応
│   │   ├── graph/
   │   │   └── service.py               # GraphRAGサービス（entity抽出、graph traversal CTE）
   │   ├── indexing/
│   │   │   ├── chunker.py                # 3粒度チャンキング（file/coarse/fine）
│   │   │   ├── queue.py                  # キュー管理（FOR UPDATE SKIP LOCKED）
│   │   │   ├── watcher.py                # watchdogファイル監視
│   │   │   ├── snapshot.py              # スナップショット方式読み込み
│   │   │   └── service.py               # IndexingService（パイプライン統括）
│   │   ├── search/
│   │   │   ├── filter.py                 # メタデータフィルタビルダー
│   │   │   ├── semantic.py               # セマンティック検索（pgvector <=>）
│   │   │   ├── keyword.py                # キーワード検索（tsvector）
│   │   │   ├── hybrid.py                # ハイブリッド検索（RRF fusion, k=60）
│   │   │   └── service.py               # SearchService（3検索統合 + ナビゲーション）
│   │   ├── namespace/
│   │   │   ├── __init__.py                 # パッケージ定義
│   │   │   └── service.py                 # 名前空間管理（CRUD + 代入 + 検索フィルタ）
│   │   ├── note/
│   │   │   ├── __init__.py                  # パッケージ定義
│   │   │   ├── editor.py                    # NoteEditor（見出しベースセクション編集・追記）
│   │   │   └── service.py                # ノートCRUD（ファイルI/O + DB同期）
│   │   └── trash/
│   │       └── service.py                # ゴミ箱管理（復元/パージ）
│   ├── i18n/
│   │   ├── translator.py                 # 翻訳エンジン
│   │   └── locales/
│   │       ├── en.json                   # 英語翻訳
│   │       └── ja.json                   # 日本語翻訳
│   ├── interfaces/
│   │   ├── api/
│   │   │   ├── app.py                    # FastAPI ファクトリ（create_app）
│   │   │   ├── cli_serve.py              # CLIエントリ（uvicorn/mcp起動）
│   │   │   └── routes/
│   │   │       ├── search.py             # 検索エンドポイント
│   │   │       ├── notes.py              # ノートCRUDエンドポイント
│   │   │       └── queue.py              # キュー管理エンドポイント
│   │   ├── cli/                          # CLIインターフェース
│   │   └── mcp/                          # MCPサーバー
│   └── claude_integration/
│       ├── installer.py                  # ClaudeCodeIntegrationInstaller
│       └── templates/
│           ├── subagent.md               # サブエージェント定義テンプレート
│           └── skill.md                  # スキル定義テンプレート
```

### 5. 依存関係

| モジュール | 依存先 |
|---|---|
| config/loader.py | config/defaults.py, pyyaml |
| config/secrets.py | keyring, cryptography |
| utils/retry.py | utils/logging.py |
| utils/tokens.py | google-genai (optional) |
| utils/language.py | langdetect |
| i18n/translator.py | (標準ライブラリのみ) |
| alembic/env.py | clawtion.core.db.models, sqlalchemy[asyncio], alembic |
| alembic/001_initial_schema.py | pgvector.sqlalchemy, alembic |
| alembic/003_graph_rag.py | pgvector.sqlalchemy, alembic |
| core/db/connection.py | sqlalchemy[asyncio], asyncpg |
| core/embedding/client.py | typing.Protocol (標準ライブラリ) |
| core/embedding/gemini.py | core/embedding/client.py, google-genai |
| core/indexing/chunker.py | utils/tokens.py, utils/language.py, utils/exceptions.py, hashlib, re, pysbd |
| core/indexing/queue.py | core/db/connection.py, utils/exceptions.py, utils/logging.py |
| core/indexing/watcher.py | core/indexing/queue.py, watchdog, utils/exceptions.py |
| core/indexing/snapshot.py | utils/exceptions.py, utils/logging.py, hashlib |
| core/indexing/service.py | core/db/connection.py, core/embedding/client.py, config/loader.py, utils/retry.py, utils/exceptions.py, core/indexing/chunker.py, core/indexing/queue.py, core/indexing/snapshot.py |
| core/search/filter.py | (標準ライブラリのみ) |
| core/search/semantic.py | core/db/connection.py, core/embedding/client.py, utils/logging.py, search/filter.py |
| core/search/keyword.py | core/db/connection.py, utils/logging.py, search/filter.py |
| core/search/hybrid.py | core/db/connection.py, core/embedding/client.py, utils/logging.py, search/semantic.py, search/keyword.py, search/filter.py |
| core/search/service.py | core/db/connection.py, core/embedding/client.py, utils/logging.py, search/semantic.py, search/keyword.py, search/hybrid.py, search/filter.py |
| core/graph/service.py | core/db/connection.py, core/embedding/client.py, utils/exceptions.py, utils/logging.py |
| core/note/service.py | core/db/connection.py, core/indexing/service.py, utils/exceptions.py, utils/logging.py |
| core/note/editor.py | utils/exceptions.py, utils/logging.py |
| core/namespace/service.py | core/db/connection.py, utils/exceptions.py, utils/logging.py |
| core/trash/service.py | core/db/connection.py, utils/exceptions.py, utils/logging.py |
| interfaces/api/app.py | fastapi, uvicorn, pydantic, core/db/connection.py, core/embedding/gemini.py, core/search/service.py, core/note/service.py, core/trash/service.py, core/indexing/queue.py |
| interfaces/api/routes/search.py | fastapi, pydantic, interfaces/api/app.py |
| interfaces/api/routes/notes.py | fastapi, pydantic, interfaces/api/app.py |
| interfaces/api/routes/queue.py | fastapi, pydantic, interfaces/api/app.py |
| interfaces/api/cli_serve.py | uvicorn (optional), interfaces/mcp/server.py (optional) |
| claude_integration/installer.py | config/loader.py, shutil, json |
| claude_integration/templates/subagent.md | （テンプレートファイル、実行依存なし） |
| claude_integration/templates/skill.md | （テンプレートファイル、実行依存なし） |

---

## PART 2: BEST PRACTICES & DESIGN EVOLUTION

### GraphRAGエンティティグラフ（Phase 2）

- **Subject:** エンティティ抽出のヒューリスティック手法
  - **(a) Original Design:** エンティティ抽出にLLM（Claude Haiku）を使用する計画だった
  - **(b) Change & Rationale:** LLM依存はレイテンシ・コスト・外部依存の3点で問題がある。Phase 2ではキーワード/正規表現ベースのヒューリスティック抽出を実装。既知エンティティ辞書 + 人物名/組織名/技術名/概念パターンの4種の正規表現でカバレッジを確保。LLM抽出はPhase 3でopt-in機能として追加予定
  - **(c) Adopted Best Practice:** `extract_entities()` は純粋な文字列処理（regex + 辞書引き）。DBアクセスはエンティティの内容取得のみ。`extract_and_store()` コンビニエンスメソッドで抽出→保存→共起関係生成を1コールで実行可能

- **Subject:** グラフ探索の再帰的CTE方式
  - **(a) Original Design:** NetworkX等のインメモリグラフライブラリで探索する計画だった
  - **(b) Change & Rationale:** 全エンティティをメモリにロードするのは大規模Vaultで非効率。PostgreSQLの `WITH RECURSIVE` CTEを使用することで、DB内部でNホップ探索を完結させ、必要最小限のデータのみ転送。relation_typeフィルタもCTE内で適用可能
  - **(c) Adopted Best Practice:** SQL再帰CTEでグラフ探索。Anchorメンバで開始エンティティからの最初のホップ、Recursiveメンバで `gt.hop < max_hops` の条件で反復。結果はentities一覧、relations一覧、adjacency listの3構造で返却

### ノート編集機能（Phase 2）

- **Subject:** 見出しベースセクション編集
  - **(a) Original Design:** 既存のNoteService.update()はファイル全体の置換のみをサポート
  - **(b) Change & Rationale:** Claude Codeからノートの一部を編集するユースケースでは、ファイル全体の読み書きよりセクション単位の手術的編集が必要。NoteEditorをNoteServiceとは別の責務（ファイル操作特化）として分離。NoteServiceはメタデータ管理＋インデキシングトリガー、NoteEditorはファイルコンテンツ操作を担当
  - **(c) Adopted Best Practice:** NoteEditorはファイルシステムに直接アクセスし、見出し位置を正規表現で検出。`update_section()` は対象見出しから同レベル以上の次見出しまでを置換範囲とする標準Markdownセクション定義に準拠。`append_content()` は末尾/見出し前/見出し後の3ポジションをサポート

### 設計原則（Phase 0 確立）

- **Subject:** 例外階層設計
  - **(a) Original Design:** 単一のExceptionクラスで全エラーを表現していた
  - **(b) Change & Rationale:** エラーの種類によってインターフェース層（CLI/MCP/REST API）でのハンドリング方法が異なるため、意味のある階層が必要。コード、メッセージ、詳細情報の統一構造により、どのインターフェースでも一貫したエラー応答が可能
  - **(c) Adopted Best Practice:** `ClawtonError` 基底クラス + 意味別サブクラス（DocumentNotFoundError, EmbeddingError等）。全例外に `code`, `message`, `details` 属性を持たせ、`to_dict()` でシリアライズ可能

- **Subject:** 設定オーバーライドチェーン
  - **(a) Original Design:** 単一のconfig.yamlのみを参照
  - **(b) Change & Rationale:** マルチVault対応とユーザー固有設定の分離が必要。グローバル設定 + Vault固有設定 + 環境変数の3層+デフォルトの4層構造により、各レイヤーで適切な優先度で設定を上書き可能
  - **(c) Adopted Best Practice:** `_deep_merge()` による再帰的マージ。環境変数（CLAWTION_*）が最優先、次にVault固有設定、次にグローバル設定、最後にデフォルト値

- **Subject:** シークレット管理の多層フォールバック
  - **(a) Original Design:** OS keychainのみを想定
  - **(b) Change & Rationale:** keyringライブラリが全ての環境で動作するとは限らない（CI/CD、ヘッドレス環境等）。暗号化ファイルと環境変数のフォールバックを追加することで、あらゆる環境での動作を保証
  - **(c) Adopted Best Practice:** 環境変数（最優先）→ OS keychain → 暗号化ファイル（~/.clawtion/secrets.enc）の3層フォールバック。暗号化キーはマシン固有情報から導出

- **Subject:** i18n翻訳のキー構造
  - **(a) Original Design:** フラットなキー構造（例: "app.welcome"）
  - **(b) Change & Rationale:** 設計書の構造（cli.init, cli.indexing, cli.errors, ui.search）に合わせるため、ネストされたJSON構造を採用。ドット区切りで解決することで、グループ化と名前空間の分離が自然に行える
  - **(c) Adopted Best Practice:** JSONネスト構造 + ドット区切りキー解決。変数補間は `{variable}` 形式。未訳キーはキー名をそのまま返す（英語フォールバック）

- **Subject:** Alembic非同期対応
  - **(a) Original Design:** 同期エンジン（psycopg2）を使用
  - **(b) Change & Rationale:** プロジェクト全体がasyncpgベースの非同期DB接続を使用するため、マイグレーションも非同期エンジンで統一。`asyncio.run()` でラップして実行
  - **(c) Adopted Best Practice:** `create_async_engine` → `connection.run_sync(do_run_migrations)` パターン。env.pyは環境変数CLAWTION_DB_URLからURLを取得

- **Subject:** REST API統一レスポンスフォーマット
  - **(a) Original Design:** エンドポイントごとに異なるレスポンス形式
  - **(b) Change & Rationale:** APIクライアント（特にClaude Code MCPとTauri UI）が一貫したレスポンス構造を期待する。全エンドポイントで `{data: ..., meta: {...}}` の統一ラッパーを使用し、エラー時は `{error: {code, message, details}}` に統一。Pydantic Generic モデル `APIResponse[T]` で型安全性を確保
  - **(c) Adopted Best Practice:** `APIResponse(BaseModel, Generic[T])` を全ルーターで使用。エラーハンドラは `ClawtionError.code` → HTTPステータスコードのマッピングテーブルで一元管理

- **Subject:** FastAPI依存性注入パターン
  - **(a) Original Design:** 各ルーター内でサービスを直接importしてインスタンス化
  - **(b) Change & Rationale:** アプリケーションライフサイクル管理（DB接続の開始/終了）が必要。FastAPIのlifespan機構でサービスを初期化し、app.stateに格納。ルーターは `Depends()` 経由でRequestからサービスを取得。これによりテスト時はapp.stateをモックで置き換え可能
  - **(c) Adopted Best Practice:** `@asynccontextmanager lifespan(app)` 内で全サービスを初期化。各ルーターは `_get_service(request: Request)` ヘルパーを `Depends` 経由で使用

- **Subject:** Claude Code統合の3層分離
  - **(a) Original Design:** 単一のCLIコマンドから直接知識ベースにアクセス
  - **(b) Change & Rationale:** Claude Codeのメインエージェントコンテキストを検索ノイズで汚染しないため、サブエージェント + スキルの2段階委譲アーキテクチャを採用。サブエージェントは専用コンテキストで検索を実行し、整形済みサマリーのみをメインエージェントに返す
  - **(c) Adopted Best Practice:** メインエージェント → Skill検知 → Subagent委譲 → MCPツール実行 の4段階パイプライン。インストーラは `~/.claude/agents/`、`~/.claude/skills/`、`~/.claude.json` の3箇所を自動設定

- **Subject:** マルチレゾリューションチャンキング（Phase 2）
  - **(a) Original Design (Phase 1):** `chunk_file()` はファイルトークン数に応じて単一レベルのチャンキング戦略を選択。1500トークン以下ならfileレベル、超過時はcoarseレベルにフォールバック。設定値 `multi_resolution.enabled = false`、coarse/fineレベルはデフォルト無効。
  - **(b) Change & Rationale:** 設計書セクション4の要件に従い、3粒度（file/coarse/fine）を常時並行生成するマルチレゾリューション方式に移行。これにより、検索時に状況に応じて最適な粒度のチャンクを選択可能になる（例: 概要把握にはfileレベル、詳細調査にはfineレベル）。ただし従来のPhase 1動作も互換性のために維持（multi_resolution無効時）。
  - **(c) Adopted Best Practice:** `chunk_file()` は `config` パラメータを受け取り、`chunking.multi_resolution.enabled` に応じて分岐。有効時は有効な全レベルのチャンク関数を直列実行し、結果をフラットリストに結合。各チャンクの `chunk_index/chunk_total` はレベル別に独立管理。context注入は全チャンクに対して統一的に適用。設定はCLIコマンド（`toggle-multi-resolution`, `enable-level`, `disable-level`）で動的に変更可能。

- **Subject:** 名前空間（Namespace）論理パーティション（Phase 2）
  - **(a) Original Design:** 単一Vault内にすべてのドキュメントとチャンクがフラットに格納されていた。論理的な分離手段はなく、マルチプロジェクト用途では複数Vaultが必要だった。
  - **(b) Change & Rationale:** 設計書セクション17.12の要件に従い、単一Vault内で論理パーティションを実現する名前空間を導入。チャンクレベルでnamespace_id FKを持たせることで、検索時に`dc.namespace_id`フィルタでスコープを限定可能。`ON DELETE SET NULL`により名前空間削除時もチャンクデータは保持される。MetadataFilterに`by_namespace()`を追加し、既存の検索パイプラインに最小限の変更で名前空間フィルタを統合。
  - **(c) Adopted Best Practice:** 名前空間はチャンクレベル（document_chunksテーブル）での紐付けとし、ドキュメントテーブルには直接カラムを追加しない。検索フィルタはMetadataFilterの拡張として`dc.namespace_id`のWHERE条件を生成。MCPツールとCLIは別個の命名空間コマンドグループとして提供し、既存インターフェースには`namespace`オプションパラメータとして追加。

---

## PART 3: PROJECT MANAGEMENT

### 現在のフェーズ: Phase 2 進行中（GraphRAG + ノート編集 実装完了）

**完了タスク:**
- [x] プロジェクト構造の確立（src/clawtion/ パッケージ構成）
- [x] pyproject.toml（依存関係、mypy strict、ruff設定）
- [x] docker-compose.yml（PostgreSQL + pgvector）
- [x] 設定システム（defaults → loader → secrets）
- [x] ユーティリティ（例外、ロギング、リトライ、トークン、言語）
- [x] 国際化（en.json, ja.json, 翻訳エンジン）
- [x] 初期Alembicマイグレーション（全5テーブル + インデックス）
- [x] REST APIフレームワーク（FastAPI ファクトリ、CORS、Request ID、例外ハンドラ、レスポンスラッパー、lifespan管理）
- [x] 検索API（semantic/keyword/hybrid search、チャンクナビゲーション）
- [x] ノートCRUD API（作成/取得/更新/削除/一覧/フォルダ一覧）
- [x] キュー管理API（ステータス/一覧/処理/リトライ/クリア/メトリクス）
- [x] APIサーバーCLIエントリポイント（uvicorn起動、MCP起動）
- [x] Claude Code統合インストーラ（install/uninstall/is_installed）
- [x] サブエージェントテンプレート（検索戦略、結果合成ルール含む設計書準拠）
- [x] スキルテンプレート（トリガー条件、呼び出し方法、禁止事項含む設計書準拠）
- [x] **Phase 2: マルチレゾリューションチャンキング**
  - [x] `chunk_file()` のconfigパラメータ対応（multi_resolution.enabled判定）
  - [x] 3レベル同時生成（file/coarse/fine）
  - [x] 設定デフォルト値更新（multi_resolution/coarse/fine 全有効化）
  - [x] `_upsert_document()` のhas_coarse_level/has_fine_levelカラム対応
  - [x] CLI config toggle/enable/disable コマンド追加
- [x] **Phase 2: 名前空間（Namespace）サポート**
  - [x] Namespace SQLAlchemyモデル（namespacesテーブル）
  - [x] DocumentChunkにnamespace_id FK追加（nullable, ON DELETE SET NULL）
  - [x] NamespaceService（create/list/get/delete + assign_chunk/assign_document/get_chunks）
  - [x] NamespaceInfo frozen dataclass
  - [x] MetadataFilter.by_namespace() + 名前空間フィルタSQL生成
  - [x] SearchService全メソッドにnamespaceパラメータ追加
  - [x] MCPツール: create_namespace / list_namespaces / assign_to_namespace
  - [x] CLIコマンド: clawtion namespace create/list/assign
  - [x] CLI検索に--namespaceオプション追加
  - [x] Alembicマイグレーション002追加
  - [x] i18n翻訳キー追加

**完了タスク:**
- [x] **Phase 2: GraphRAGエンティティグラフ**
  - [x] Entity SQLAlchemyモデル（entitiesテーブル: entity_id, name, entity_type, description, embedding, created_at + UNIQUE(name, entity_type)）
  - [x] Relation SQLAlchemyモデル（relationsテーブル: relation_id, source_entity_id FK, target_entity_id FK, relation_type, weight, source_chunk_id FK, created_at）
  - [x] GraphService（extract_entities, add_entity, add_relation, graph_search, find_related, extract_and_store）
  - [x] ヒューリスティックエンティティ抽出（既知辞書 + 正規表現パターン4種）
  - [x] 再帰的SQL CTEによるNホップグラフ探索
  - [x] エンティティベクトル検索用embedding自動生成
  - [x] MCPツール: graph_search / get_related_chunks / extract_entities_from_chunk
  - [x] Alembicマイグレーション003追加
- [x] **Phase 2: ノート編集機能**
  - [x] NoteEditor（update_section, append_content, _find_heading_position）
  - [x] 見出しベースセクション置換（Markdown見出しレベル認識）
  - [x] 複数見出し一致時のmatch_contextによる曖昧性解消
  - [x] 3ポジション追記（end / after_heading / before_heading）
  - [x] MCPツール: update_note_section / append_to_note
  - [x] MCPサーバー: get_graph_service / get_note_editor ファクトリ追加

**未完了（次のアクション）:**
- [ ] CLIインターフェース（Clickコマンド）のGraphRAG/NoteEditing対応
- [ ] REST API（FastAPI）のGraphRAG/NoteEditingエンドポイント追加
- [ ] Phase 3: LLMベースエンティティ抽出（Claude Haiku統合）
- [ ] Phase 3: コンテキスト検索（Contextual Retrieval）
- [ ] E2Eテスト：GraphRAGグラフ探索・ノート編集シナリオ
