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

**国際化:**
- `i18n/translator.py`: JSONファイルベースの翻訳エンジン
  - `t(key, **kwargs)`: ドット区切りキー解決 + 変数補間
  - `set_language(lang)`, `get_current_language()`, `reload_locales()`
  - 自動検出（CLAWTION_LANG → LANG → OSロケール → "en"）
- `i18n/locales/en.json`: 完全な英語翻訳（cli全コマンド + ui）
- `i18n/locales/ja.json`: 完全な日本語翻訳

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

[Claude Code / 人間] ←→ [インターフェース層] ←→ [コアロジック層] ←→ [ストレージ層]
                            CLI / MCP / REST API      Indexing/Search/Note     Postgres+pgvector / Vault

設定層:
  defaults.py → ~/.clawtion/config.yaml → vault/.clawtion/config.yaml → CLAWTION_* env vars
                                                                              ↓
                                                                       secrets.py
                                                                    (keychain/enc/env)
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

---

## PART 3: PROJECT MANAGEMENT

### 現在のフェーズ: Phase 0（基盤構築）

**完了タスク:**
- [x] プロジェクト構造の確立（src/clawtion/ パッケージ構成）
- [x] pyproject.toml（依存関係、mypy strict、ruff設定）
- [x] docker-compose.yml（PostgreSQL + pgvector）
- [x] 設定システム（defaults → loader → secrets）
- [x] ユーティリティ（例外、ロギング、リトライ、トークン、言語）
- [x] 国際化（en.json, ja.json, 翻訳エンジン）
- [x] 初期Alembicマイグレーション（全5テーブル + インデックス）

**未完了（次のアクション）:**
- [ ] コアDBレイヤー（connection.py, models.py, migrations.py）
- [ ] EmbeddingClient（Gemini Embedding 2統合）
- [ ] IndexingService（チャンカー、ファイル監視、キュー管理）
- [ ] SearchService（セマンティック、キーワード、ハイブリッド検索）
- [ ] NoteService（CRUD、ゴミ箱）
- [ ] CLIインターフェース（Clickコマンド）
- [ ] MCPサーバー
- [ ] REST API（FastAPI）
- [ ] Claude Code統合（サブエージェント、スキル）
- [ ] Test実装
