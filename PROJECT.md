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

**データベースマイグレーション:**
- `alembic.ini`: Alembic設定（sqlalchemy.urlは環境変数から）
- `alembic/env.py`: 非同期エンジンベースのAlembic env
- `alembic/versions/001_initial_schema.py`: 初期スキーマ作成
  - documentsテーブル（UUID PK, file_path, folder_path, title, file_extension, file_size_bytes, content_hash, tags JSONB, wikilinks JSONB, metadata JSONB, total_chunks, has_file_level/coarse/fine, last_indexed_at, is_deleted, deleted_at, created_at, updated_at）
  - document_chunksテーブル（UUID PK, document_id FK, chunk_level, chunk_index, chunk_total, parent_chunk_id self-ref FK, heading_path, page_number, content, content_with_context, content_hash, embedding vector(768), embedding_model, embedding_dimensions, embedded_at, token_count, char_count, tsvector GENERATED ALWAYS, metadata JSONB, created_at, UNIQUE(document_id, chunk_level, chunk_index)）
  - indexing_queueテーブル（queue_id PK, document_id FK, file_path, operation, status, progress JSONB, priority, retry_count, max_retries, last_error, error_history JSONB, timestamps）
  - trashテーブル（trash_id PK, original_document_id, original_file_path, original_content, original_metadata JSONB, deleted_at, auto_purge_at）
  - vault_settingsテーブル（key PK, value JSONB, updated_at）
  - インデックス: HNSW on embedding, GIN on tsvector, GIN on tags, B-tree各種

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
│   └── i18n/
│       ├── translator.py                 # 翻訳エンジン
│       └── locales/
│           ├── en.json                   # 英語翻訳
│           └── ja.json                   # 日本語翻訳
│   ├── interfaces/
│   │   └── api/
│   │       ├── __init__.py               # パッケージ
│   │       ├── app.py                    # FastAPI ファクトリ（create_app）
│   │       ├── cli_serve.py              # CLIエントリ（uvicorn/mcp起動）
│   │       └── routes/
│   │           ├── __init__.py           # パッケージ
│   │           ├── search.py             # 検索エンドポイント
│   │           ├── notes.py              # ノートCRUDエンドポイント
│   │           └── queue.py              # キュー管理エンドポイント
│   └── claude_integration/
│       ├── __init__.py                   # パッケージ
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
| interfaces/api/app.py | fastapi, uvicorn, pydantic, clawtion.core.db.connection, clawtion.core.embedding.gemini, clawtion.core.search.service, clawtion.core.note.service, clawtion.core.trash.service, clawtion.indexing.queue |
| interfaces/api/routes/search.py | fastapi, pydantic, clawtion.interfaces.api.app |
| interfaces/api/routes/notes.py | fastapi, pydantic, clawtion.interfaces.api.app |
| interfaces/api/routes/queue.py | fastapi, pydantic, clawtion.interfaces.api.app |
| interfaces/api/cli_serve.py | uvicorn (optional), clawtion.interfaces.mcp.server (optional) |
| claude_integration/installer.py | clawtion.config.loader, shutil, json |
| claude_integration/templates/subagent.md | （テンプレートファイル、実行依存なし） |
| claude_integration/templates/skill.md | （テンプレートファイル、実行依存なし） |

---

## PART 2: BEST PRACTICES & DESIGN EVOLUTION

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

---

## PART 3: PROJECT MANAGEMENT

### 現在のフェーズ: Phase 0→1 移行（基盤構築完了、インターフェース層実装中）

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

**未完了（次のアクション）:**
- [ ] コアDBレイヤー（connection.py, DatabaseManager実装）
- [ ] EmbeddingClient（Gemini Embedding 2統合）
- [ ] IndexingService（チャンカー、ファイル監視、キュー管理）
- [ ] SearchService（セマンティック、キーワード、ハイブリッド検索）
- [ ] NoteService（CRUD、ゴミ箱）
- [ ] TrashService（ゴミ箱操作）
- [ ] CLIインターフェース（Clickコマンド）
- [ ] MCPサーバー（MCPプロトコル実装）
- [ ] Test実装（単体テスト + 統合テスト）
