# clawtion プロジェクト完全仕様書

> **最終更新**: 2026-05-06  
> **バージョン**: 0.2.0  
> **対象読者**: 開発者（初学者〜上級者）・OSSコントリビューター・将来のメンテナー

---

## 目次

1. [プロジェクトとは](#1-プロジェクトとは)
2. [システム全体像](#2-システム全体像)
3. [Dockerコンテナの中身](#3-dockerコンテナの中身)
4. [データの保存場所一覧](#4-データの保存場所一覧)
5. [リポジトリとGit管理](#5-リポジトリとgit管理)
6. [OSSとして配布するには](#6-ossとして配布するには)
7. [全ディレクトリ・ファイル詳細](#7-全ディレクトリファイル詳細)
8. [データフロー](#8-データフロー)
9. [開発環境セットアップ手順](#9-開発環境セットアップ手順)

---

## 1. プロジェクトとは

clawtion（クローション）は **「AIのためのナレッジベース」** と **「人間のためのメモ帳」** を統合したローカル知識ベースアプリケーションです。

### 1.1 できること

- Markdownノートの作成・編集・削除
- ノートの全文検索（キーワード検索）
- ノートの意味検索（AIによるベクトル類似度検索）
- ノートのハイブリッド検索（上記2つの組み合わせ）
- ノートのフォルダ分類・タグ付け
- ダークモード対応のモダンUI

### 1.2 技術スタック

| 層 | 技術 | 役割 |
|----|------|------|
| デスクトップシェル | Tauri 2.x（Rust） | アプリのウィンドウ枠（現在はViteブラウザモード） |
| フロントエンド | React 19 + TypeScript + Tailwind CSS 4 | 画面表示 |
| エディタ | TipTap 3（ProseMirror） | Markdownエディタ |
| 通信 | TanStack Query + REST API | フロント⇔バックエンド通信 |
| バックエンド | Python 3.13 + FastAPI | APIサーバー・ビジネスロジック |
| ベクトル検索 | pgvector（PostgreSQL拡張） | 意味検索のためのベクトル演算 |
| Embedding生成 | Google Gemini Embedding 2 API | テキスト→ベクトル変換 |
| データベース | PostgreSQL 16（Dockerコンテナ） | メタデータ・チャンク・ベクトル保存 |
| ファイルストレージ | ローカルファイルシステム | ノート.mdファイルの保存 |

---

## 2. システム全体像

clawtionは **4層構造** で動いています。この4層は物理的に異なる場所に存在します。

```
┌──────────────────────────────────────────────────────────────────┐
│ ① フロントエンド (React)                                          │
│    場所: C:\...\clawtion\clawtion-ui\                             │
│    実行: npm run dev → http://localhost:5173                      │
│    役割: 画面描画・ユーザー操作受付                                │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP (http://127.0.0.1:8000)
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│ ② バックエンド (FastAPI)                                          │
│    場所: C:\...\clawtion\src\clawtion\                            │
│    実行: python -m uvicorn ...                                    │
│    役割: ビジネスロジック・API・Embedding生成                     │
└──────┬────────────────────┬──────────────────────────────────────┘
       │ ファイル読み書き     │ SQL (asyncpg)
       ▼                    ▼
┌──────────────────┐  ┌──────────────────────────────────────────┐
│ ③ ノートファイル   │  │ ④ PostgreSQL + pgvector (Docker)         │
│    (Vault)        │  │    イメージ: pgvector/pgvector:pg16       │
│ 場所:              │  │    Dockerボリューム: clawtion_pgdata      │
│ ~/Documents/       │  │    コンテナ名: clawtion-db                │
│ clawtion-vault/    │  │    ポート: localhost:5432                 │
│                    │  │    役割: メタデータ・チャンク・           │
│ *.md ファイル       │  │          Embeddingベクトル保存           │
└──────────────────┘  └──────────────────────────────────────────┘
```

### 2.1 重要なこと：フロントエンドとバックエンドは同じマシン内で通信している

```
ブラウザ (localhost:5173)
    │
    │ http://127.0.0.1:8000/api/v1/notes
    │ （完全にローカル。インターネットに出ない）
    ▼
FastAPI (127.0.0.1:8000)
```

外部のサーバーにデータが送られることは**一切ありません**。（唯一の例外は、Embedding生成のためのGoogle Gemini API呼び出しです。これはテキストをベクトルに変換するために必要で、APIキーがないと検索機能が動きません）

---

## 3. Dockerコンテナの中身

### 3.1 なぜDockerが必要か

clawtionの検索機能は **pgvector**（PostgreSQLのベクトル検索拡張）に依存しています。pgvectorは通常のPostgreSQLに追加でインストールが必要な拡張機能です。

Dockerを使う理由：
1. **セットアップの自動化**: `docker compose up -d` の1コマンドでPostgreSQL+pgvectorが即座に使える
2. **環境の統一**: 開発者全員が同じバージョンのPostgreSQL+pgvectorを使える
3. **Windows/Mac/Linux対応**: OSを問わず同じ環境が動く
4. **アンインストールが簡単**: `docker compose down` で綺麗に消せる

### 3.2 コンテナの技術仕様

```
Dockerイメージ: pgvector/pgvector:pg16
    └── ベース: PostgreSQL 16.13
    └── 拡張: pgvector (ベクトル検索用)
    └── サイズ: 約 621MB

起動設定 (docker-compose.yml):
    コンテナ名:  clawtion-db
    イメージ:    pgvector/pgvector:pg16
    ポート:      5432 → 5432 (ホストに公開)
    ユーザー:    clawtion
    パスワード:  clawtion
    データベース: clawtion
    ヘルスチェック: pg_isready -U clawtion -d clawtion (5秒間隔)
    再起動ポリシー: unless-stopped (PC再起動時に自動起動)

データ保存先:
    Dockerボリューム名: clawtion_pgdata
    WSL内パス: /var/lib/docker/volumes/clawtion_pgdata/_data
    Windowsパス: \\wsl$\docker-desktop\...\clawtion_pgdata\_data
```

### 3.3 コンテナ内で動いているもの

```
PostgreSQL 16 プロセス
    ├── データベース "clawtion"
    │   ├── documents テーブル          ← ノートのメタデータ
    │   ├── document_chunks テーブル     ← チャンク + Embeddingベクトル
    │   ├── indexing_queue テーブル     ← バルクindexingジョブ管理
    │   ├── trash テーブル              ← 削除ノートのゴミ箱
    │   ├── vault_settings テーブル     ← Vault設定（Key-Value）
    │   ├── namespaces テーブル         ← 名前空間（論理パーティション）
    │   ├── entities テーブル           ← GraphRAG用エンティティ
    │   ├── relations テーブル          ← GraphRAG用リレーション
    │   └── alembic_version テーブル    ← マイグレーション管理
    │
    ├── pgvector 拡張機能
    │   ├── vector 型                   ← Embeddingベクトルを格納する型
    │   ├── HNSW インデックス            ← 高速ベクトル検索用
    │   └── ベクトル演算子 (<=>, <->)    ← コサイン距離・ユークリッド距離計算
    │
    └── pg_trgm 拡張機能
        └── 全文検索（キーワード検索）用のトライグラムインデックス
```

### 3.4 Dockerがないとどうなるか

Dockerを使わない場合の手動手順（非推奨）：
1. PostgreSQL 16を公式サイトからインストール
2. pgvector拡張をソースコードからビルド（Cコンパイラが必要）
3. PostgreSQLの設定ファイルを編集してpgvectorを有効化
4. `CREATE EXTENSION vector;` を手動実行
5. データベース・ユーザーを手動作成

Dockerなら上記が `docker compose up -d` の1行で完了します。

---

## 4. データの保存場所一覧

clawtionのデータは **5つの場所** に分散しています。これは設計上の意図的な分離です。

### 4.1 全体マップ

```
このPC (C:\Users\mahim\)
│
├── 📁 .claude\実行場\clawtion\          ← 【Git管理】プロジェクト本体
│   ├── docker-compose.yml               ← Dockerコンテナ定義
│   ├── .env                             ← 環境変数（Git非管理）
│   ├── src/clawtion/                    ← バックエンド全ソースコード
│   ├── clawtion-ui/                     ← フロントエンド全ソースコード
│   ├── alembic/                         ← DBマイグレーション定義
│   └── FRONTEND_DESIGN_SPEC.md          ← 設計書
│
├── 📁 Documents\clawtion-vault\         ← 【ユーザーデータ】ノートファイル
│   ├── *.md                             ← 全ノート（Markdown）
│   └── */                               ← フォルダ
│
├── 📁 .clawtion\                         ← 【ユーザー設定】
│   ├── config.yaml                      ← Vaultパス・Chunking設定等
│   └── logs\clawtion.log               ← アプリログ
│
├── 📁 .claude\skills\                   ← 【Claude Code統合】
│   ├── design-md\                       ← DESIGN.md検証スキル
│   ├── agent-browser\                   ← ブラウザ自動化スキル
│   └── ...                              ← その他のスキル
│
├── 🐳 Docker (WSL2内)                   ← 【仮想環境】データベース
│   ├── コンテナ: clawtion-db
│   │   └── PostgreSQL 16 + pgvector
│   └── ボリューム: clawtion_pgdata
│       └── /var/lib/postgresql/data/    ← DB実データ
│
└── �📦 Google Cloud (外部API)           ← 【リモート】Embedding生成のみ
    └── models/gemini-embedding-2        ← Gemini Embedding 2 API
```

### 4.2 各場所の詳細

#### A. プロジェクト本体 (`clawtion/`)
| 内容 | 説明 |
|------|------|
| Gitで管理 | ✅ はい |
| ユーザーが触る | 開発者のみ |
| 別PCに移行 | `git clone` で再現 |

#### B. Vault (`Documents/clawtion-vault/`)
| 内容 | 説明 |
|------|------|
| Gitで管理 | ❌ いいえ（ユーザーデータのため） |
| ユーザーが触る | ✅ はい（ノートを直接編集可能） |
| 別PCに移行 | 手動コピーまたはバックアップ |

#### C. 設定 (`~/.clawtion/`)
| 内容 | 説明 |
|------|------|
| Gitで管理 | ❌ いいえ |
| ユーザーが触る | `clawtion config` コマンド経由 |
| 別PCに移行 | 手動コピー（config.yaml）または再生成 |

#### D. Claude Code統合 (`~/.claude/`)
| 内容 | 説明 |
|------|------|
| Gitで管理 | ❌ いいえ（Claude Codeの管理下） |
| ユーザーが触る | Claude Codeが自動管理 |
| 別PCに移行 | `clawtion install-claude` で再生成 |

#### E. Docker (WSL2仮想マシン内)
| 内容 | 説明 |
|------|------|
| Gitで管理 | ❌ いいえ（Dockerボリューム） |
| ユーザーが触る | 通常は触らない（DBはAPI経由で操作） |
| 別PCに移行 | `docker compose up -d` で空DBから再作成 |

---

## 5. リポジトリとGit管理

### 5.1 Git管理されるもの（リポジトリに含める）

```
clawtion/ （このディレクトリ全体がGitリポジトリ）
│
├── ✅ src/clawtion/        ← バックエンドコード
├── ✅ clawtion-ui/src/     ← フロントエンドコード
├── ✅ clawtion-ui/package.json ← 依存関係定義
├── ✅ clawtion-ui/vite.config.ts ← ビルド設定
├── ✅ alembic/             ← DBマイグレーション
├── ✅ docker-compose.yml   ← Docker定義
├── ✅ pyproject.toml       ← Python依存関係
├── ✅ DESIGN.md            ← デザインシステム
├── ✅ FRONTEND_DESIGN_SPEC.md ← 設計書
├── ✅ .github/workflows/   ← CI/CD設定
│
├── ❌ .env                 ← APIキー含むため除外
├── ❌ node_modules/        ← npm installで復元可能
├── ❌ __pycache__/         ← Pythonキャッシュ
├── ❌ dist/                ← ビルド成果物
└── ❌ clawtion-ui/.env     ← 同上
```

### 5.2 Git管理されないもの（自動生成・インストール時に作成）

| 場所 | 内容 | 作成方法 |
|------|------|---------|
| `Documents/clawtion-vault/` | ノートファイル | `clawtion init` で自動作成 |
| `~/.clawtion/` | 設定・ログ | `clawtion init` で自動作成 |
| `~/.claude/` | Claude Code統合 | `clawtion install-claude` で作成 |
| Dockerボリューム | PostgreSQLデータ | `docker compose up -d` で自動作成 |
| `clawtion-ui/node_modules/` | npm依存パッケージ | `npm install` で復元 |

### 5.3 別のPCで再現する手順

```bash
# 1. リポジトリをクローン
git clone <repo-url>
cd clawtion

# 2. Python依存関係をインストール
pip install -e ".[dev]"

# 3. フロントエンド依存関係をインストール
cd clawtion-ui
npm install
cd ..

# 4. DockerでDBを起動（自動的に空のDB + pgvectorが作成される）
docker compose up -d

# 5. DBマイグレーションを実行（テーブルを作成）
clawtion db migrate

# 6. Vaultを初期化
clawtion init

# 7. バックエンド起動
python -m uvicorn clawtion.interfaces.api.app:create_app --factory --port 8000

# 8. フロントエンド起動（別ターミナル）
cd clawtion-ui
npm run dev

# → http://localhost:5173 でアクセス
```

これで **完全に同じ環境** が別のPCで再現されます。

---

## 6. OSSとして配布するには

### 6.1 現在のリポジトリ構成で配布可能か

**はい、可能です。** clawtionディレクトリをGitHubにプッシュするだけで、他の開発者は上記の手順で完全に同じ環境を再現できます。

不足しているもの：
- [ ] `CONTRIBUTING.md`（コントリビューションガイド）
- [ ] `LICENSE`（既存）
- [ ] `.env.example`（APIキーの説明用、既存）
- [ ] `README.md` の更新（既存だが簡素）

### 6.2 ユーザーが自分で用意する必要があるもの

| 項目 | 理由 | 取得方法 |
|------|------|---------|
| Gemini API キー | Embedding生成に必要 | https://aistudio.google.com/ で無料取得 |
| Docker Desktop | PostgreSQL+pgvector実行用 | https://docker.com から無料ダウンロード |
| Python 3.11+ | バックエンド実行用 | https://python.org |
| Node.js 22+ | フロントエンド実行用 | https://nodejs.org |

### 6.3 理想的な配布形態（将来的）

```
フェーズ1（現在）: ソースコード配布
    git clone → pip install → npm install → docker compose up → 起動

フェーズ2（計画中）: pipパッケージ配布
    pip install clawtion → clawtion init → 起動

フェーズ3（計画中）: デスクトップアプリ配布
    clawtion-setup.exe をダウンロード → インストール → 起動
    （Tauriバンドル。Rustのセットアップが必要）
```

---

## 7. 全ディレクトリ・ファイル詳細

### 7.1 プロジェクトルート (`clawtion/`)

```
clawtion/
│
├── .env                          # 環境変数 (DB_URL, API_KEY, VAULT_PATH)
├── .gitignore                    # Git除外設定
├── .pre-commit-config.yaml       # pre-commit フック設定
├── LICENSE                       # MIT License
├── README.md                     # プロジェクト概要
├── PROJECT.md                    # このファイル（完全仕様書）
├── DESIGN.md                     # デザインシステム定義
├── FRONTEND_DESIGN_SPEC.md       # フロントエンド設計指示書
├── clawtion-design-doc_v3.md     # 全体設計ドキュメント
├── ソフトウェア開発における設計思想.md  # 設計哲学（19原則）
│
├── pyproject.toml                # Pythonパッケージ定義・依存関係
├── docker-compose.yml            # Docker (PostgreSQL+pgvector) 定義
├── alembic.ini                   # DBマイグレーション設定
│
├── src/clawtion/                 # ★ バックエンド全ソースコード
│   ├── __init__.py
│   ├── __main__.py               # エントリーポイント
│   │
│   ├── config/                   # 設定管理
│   │   ├── defaults.py           # デフォルト設定値
│   │   ├── loader.py             # 設定読み込み（4層オーバーライド）
│   │   └── secrets.py            # APIキー管理（env→keychain→暗号化ファイル）
│   │
│   ├── utils/                    # ユーティリティ
│   │   ├── exceptions.py         # カスタム例外クラス
│   │   ├── logging.py            # ロギング設定
│   │   ├── retry.py              # 指数バックオフ リトライ
│   │   ├── tokens.py             # トークン計算
│   │   └── language.py           # 言語検出
│   │
│   ├── i18n/                     # 国際化
│   │   ├── translator.py
│   │   └── locales/              # ja.json, en.json
│   │
│   ├── core/                     # ★ コアビジネスロジック
│   │   ├── db/
│   │   │   ├── connection.py     # DB接続管理
│   │   │   ├── models.py         # ORMモデル（全7テーブル）
│   │   │   └── migrations.py     # マイグレーション実行
│   │   │
│   │   ├── embedding/
│   │   │   ├── client.py         # Embedding基底クラス
│   │   │   ├── gemini.py         # Gemini Embedding 2実装
│   │   │   ├── openai.py         # OpenAI Embedding実装
│   │   │   ├── ollama.py         # Ollama (ローカル) Embedding実装
│   │   │   ├── factory.py        # Provider自動選択
│   │   │   └── batch.py          # バッチEmbedding
│   │   │
│   │   ├── indexing/
│   │   │   ├── service.py        # IndexingService（本文修正あり）
│   │   │   ├── chunker.py        # チャンク分割エンジン
│   │   │   ├── queue.py          # キュー管理
│   │   │   ├── watcher.py        # ファイル監視
│   │   │   ├── snapshot.py       # ファイルスナップショット
│   │   │   └── loaders.py        # マルチフォーマットローダー
│   │   │
│   │   ├── search/
│   │   │   ├── service.py        # 検索統合サービス
│   │   │   ├── semantic.py       # ベクトル検索
│   │   │   ├── keyword.py        # キーワード検索
│   │   │   ├── hybrid.py         # ハイブリッド検索（RRF融合）
│   │   │   └── filter.py         # メタデータフィルタ
│   │   │
│   │   ├── note/
│   │   │   ├── service.py        # ノートCRUDサービス（本文修正あり）
│   │   │   └── editor.py         # セクション編集
│   │   │
│   │   ├── trash/service.py      # ゴミ箱管理
│   │   ├── namespace/service.py  # 名前空間管理
│   │   └── graph/service.py      # GraphRAG
│   │
│   ├── interfaces/
│   │   ├── api/                  # ★ REST API
│   │   │   ├── app.py            # FastAPIアプリケーション（本文修正あり）
│   │   │   ├── cli_serve.py      # CLI起動
│   │   │   └── routes/
│   │   │       ├── notes.py      # ノートCRUD API（本文修正あり）
│   │   │       ├── search.py     # 検索API（本文修正あり）
│   │   │       └── queue.py      # キュー管理API（本文修正あり）
│   │   │
│   │   ├── cli/                  # CLIツール
│   │   │   ├── main.py           # CLIエントリーポイント
│   │   │   ├── init.py           # clawtion init
│   │   │   ├── index.py          # clawtion index
│   │   │   ├── search.py         # clawtion search
│   │   │   ├── note.py           # clawtion note
│   │   │   ├── config.py         # clawtion config
│   │   │   ├── doctor.py         # clawtion doctor
│   │   │   ├── trash.py          # clawtion trash
│   │   │   ├── namespace.py      # clawtion namespace
│   │   │   ├── service.py        # CLI共通サービス
│   │   │   └── git_cmd.py        # Gitローダー
│   │   │
│   │   └── mcp/                  # MCPサーバー（Claude Code統合）
│   │       ├── server.py
│   │       └── tools.py
│   │
│   └── claude_integration/       # Claude Code連携
│       ├── installer.py
│       └── templates/
│           ├── subagent.md
│           └── skill.md
│
├── alembic/                      # DBマイグレーション定義
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py # 初期テーブル作成
│       ├── 002_namespace_support.py
│       └── 003_graph_rag.py
│
├── clawtion-ui/                  # ★ フロントエンド全ソースコード
│   ├── package.json              # npm依存関係
│   ├── vite.config.ts            # Viteビルド設定
│   ├── vitest.config.ts          # テスト設定
│   ├── playwright.config.ts      # E2Eテスト設定
│   ├── tsconfig.json             # TypeScript設定
│   ├── index.html                # HTMLエントリーポイント
│   ├── .env                      # フロントエンド環境変数
│   ├── .env.example              # 同上のサンプル
│   │
│   ├── src-tauri/                # Tauriデスクトップ設定（将来用）
│   │   ├── Cargo.toml
│   │   ├── tauri.conf.json
│   │   └── src/main.rs
│   │
│   ├── src/                      # ★ フロントエンド ソースコード
│   │   ├── main.tsx              # Reactエントリーポイント
│   │   ├── App.tsx               # ルートコンポーネント
│   │   ├── router.tsx            # ルーティング定義
│   │   ├── index.css             # グローバルCSS + Tailwind v4テーマ
│   │   │
│   │   ├── types/api.ts          # バックエンドAPIとの型契約
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts            # APIクライアント（全17エンドポイント）
│   │   │   └── utils.ts          # 汎用ユーティリティ
│   │   │
│   │   ├── stores/               # クライアント状態管理（Zustand）
│   │   │   ├── uiStore.ts        # サイドバー・トースト
│   │   │   ├── noteStore.ts      # ノートフィルタ・ページネーション
│   │   │   ├── searchStore.ts    # 検索クエリ・フィルタ
│   │   │   ├── settingsStore.ts  # 設定（localStorage永続化）
│   │   │   └── queueStore.ts     # ポーリング設定
│   │   │
│   │   ├── hooks/                # サーバー状態管理（TanStack Query）
│   │   │   ├── useNotes.ts       # ノートCRUD操作
│   │   │   ├── useSearch.ts      # 検索・チャンク操作
│   │   │   ├── useQueue.ts       # キュー管理・ポーリング
│   │   │   └── useSettings.ts    # 設定・フォルダ一覧・メトリクス
│   │   │
│   │   ├── components/
│   │   │   ├── ui/               # デザインシステム部品
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   ├── Badge.tsx
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── Toast.tsx
│   │   │   │   ├── Spinner.tsx
│   │   │   │   └── Skeleton.tsx
│   │   │   │
│   │   │   ├── layout/           # 画面レイアウト
│   │   │   │   ├── AppLayout.tsx # 全体シェル
│   │   │   │   ├── Sidebar.tsx   # サイドバー
│   │   │   │   └── StatusBar.tsx # ステータスバー
│   │   │   │
│   │   │   ├── notes/            # ノート関連部品
│   │   │   │   ├── TipTapEditor.tsx # Markdownエディタ
│   │   │   │   ├── NoteTable.tsx
│   │   │   │   ├── FolderTree.tsx
│   │   │   │   └── TagInput.tsx
│   │   │   │
│   │   │   └── search/           # 検索関連部品
│   │   │       ├── SearchBar.tsx
│   │   │       ├── SearchResultCard.tsx
│   │   │       ├── SearchFilters.tsx
│   │   │       └── ChunkNavigator.tsx
│   │   │
│   │   └── pages/                # 画面（9画面）
│   │       ├── NoteListPage.tsx
│   │       ├── NoteCreatePage.tsx
│   │       ├── NoteEditPage.tsx
│   │       ├── SearchPage.tsx
│   │       ├── ChunkDetailPage.tsx
│   │       ├── SettingsPage.tsx
│   │       ├── QueuePage.tsx
│   │       ├── TrashPage.tsx
│   │       └── SystemPage.tsx
│   │
│   └── tests/                    # テスト
│       ├── setup.ts
│       ├── unit/
│       │   ├── stores.test.ts
│       │   └── api.test.ts
│       ├── components/
│       │   └── SearchBar.test.tsx
│       └── e2e/
│           └── app.spec.ts
│
├── tests/                        # Pythonバックエンドテスト
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── design-doc-chapters/          # 設計ドキュメント（章別）
│   ├── 01_プロジェクト概要.md 〜 18_付録.md
│
└── .github/workflows/
    └── ci.yml                    # GitHub Actions CI設定
```

### 7.2 プロジェクト外の関連ファイル・ディレクトリ

```
C:\Users\mahim\
│
├── 📁 Documents\clawtion-vault\     ← 【Vault】ノートファイル保存先
│   ├── *.md                          ← ユーザーが作成したノート
│   └── {folder}/                     ← フォルダ（test/, ui-test/, debug-folder/）
│       パス設定: .env の CLAWTION_VAULT または ~/.clawtion/config.yaml
│
├── 📁 .clawtion\                     ← 【ユーザー設定ディレクトリ】
│   ├── config.yaml                   ← 設定ファイル
│   │   内容: vault.path, chunking設定, embedding設定, UI設定
│   │   作成: clawtion init で自動生成
│   │
│   ├── secrets.enc                   ← APIキー暗号化ファイル
│   │   内容: gemini_api_key, openai_api_key
│   │   作成: clawtion config set-key で生成（存在しない場合は作成されない）
│   │   暗号化: cryptography.fernet（マシン固有キー）
│   │
│   └── logs\clawtion.log             ← アプリログ
│
├── 📁 .claude\                        ← 【Claude Code 設定】
│   ├── settings.json                  ← Claude Code設定
│   ├── CLAUDE.md                     ← ユーザーグローバル指示
│   ├── skills\                        ← スキル定義
│   │   ├── design-md\
│   │   ├── agent-browser\
│   │   └── ...
│   │
│   └── 実行場\clawtion\              ← ★ このプロジェクトの作業ディレクトリ
│       └── (上記 7.1 の全ファイル)
│
└── 🐳 WSL2 (\\wsl$\docker-desktop\)  ← 【Docker仮想マシン】
    └── data\docker\volumes\
        └── clawtion_pgdata\_data\     ← PostgreSQL実データファイル
            ├── base/                  ← テーブルデータ
            ├── pg_wal/                ← WAL（先行書き込みログ）
            ├── pg_stat/               ← 統計情報
            └── postgresql.conf        ← PostgreSQL設定
```

### 7.3 DBテーブル一覧

| テーブル名 | 役割 | 主なカラム |
|-----------|------|-----------|
| `documents` | ノートのメタデータ | document_id, file_path, title, tags, total_chunks, is_deleted |
| `document_chunks` | チャンク + Embeddingベクトル | chunk_id, document_id, content, embedding(vector), chunk_level |
| `indexing_queue` | バルクindexingジョブ管理 | queue_id, document_id, operation, status, priority, retry_count |
| `trash` | 削除ノートのゴミ箱 | trash_id, original_document_id, original_content, auto_purge_at |
| `vault_settings` | Key-Value設定 | key, value(JSON), updated_at |
| `namespaces` | 論理パーティション | namespace_id, name |
| `entities` | GraphRAGエンティティ | entity_id, name, entity_type, embedding(vector(768)) |
| `relations` | GraphRAGリレーション | source_entity_id → target_entity_id, relation_type, weight |

---

## 8. データフロー

### 8.1 ノート作成時のデータの流れ

```
ユーザーがUIでノート作成
    │
    ▼
[1] React (localhost:5173)
    │ POST /api/v1/notes
    │ {title, content, folder, tags}
    ▼
[2] FastAPI (127.0.0.1:8000)
    │ NoteService.create()
    │
    ├──▶ [3] ファイルシステム
    │    ~/Documents/clawtion-vault/{title}.md を作成
    │
    ├──▶ [4] PostgreSQL (Docker)
    │    documentsテーブルにINSERT
    │
    ├──▶ [5] IndexingService.index_file()
    │    │
    │    ├── ファイルを読み込み
    │    ├── チャンク分割 (file/coarse/fine の3粒度)
    │    ├── 各チャンクのテキスト → Gemini Embedding 2 API に送信
    │    │   ※ この通信だけ外部（Google）に出る
    │    ├── Embeddingベクトルを受信
    │    └── PostgreSQL document_chunksテーブルにINSERT
    │        (content, embedding(vector), chunk_level, ...)
    │
    └──▶ [6] レスポンス
         200 OK {document_id, total_chunks, ...}
         ↓
         フロントエンドが編集画面に遷移
```

### 8.2 検索時のデータの流れ

```
ユーザーが検索クエリを入力
    │
    ▼
[1] React → POST /api/v1/search/hybrid {query: "...", top_k: 10}
    │
    ▼
[2] FastAPI → SearchService.hybrid_search()
    │
    ├── [3a] クエリテキスト → Gemini Embedding 2 API → クエリベクトル
    │        ※ 外部通信
    │
    ├── [3b] PostgreSQL: キーワード全文検索 (tsvector/tsquery)
    │        ※ ローカル
    │
    ├── [3c] PostgreSQL: ベクトル類似度検索 (pgvector <=> 演算子)
    │        ※ ローカル
    │
    └── [4] RRF (Reciprocal Rank Fusion) で結果を融合
           k=60 でスコア正規化
           ↓
           検索結果を返却
```

---

## 9. 開発環境セットアップ手順

### 9.1 前提条件

| ツール | 最低バージョン | 確認コマンド |
|--------|-------------|------------|
| Python | 3.11+ | `python --version` |
| Node.js | 22+ | `node --version` |
| npm | 10+ | `npm --version` |
| Docker Desktop | 最新 | `docker --version` |
| Git | 最新 | `git --version` |
| Rust（任意） | 1.80+（Tauri用） | `rustc --version` |

### 9.2 初回セットアップ

```bash
# 1. クローン
git clone https://github.com/clawtion/clawtion.git
cd clawtion

# 2. Pythonバックエンド
pip install -e ".[dev]"

# 3. フロントエンド
cd clawtion-ui
npm install
cd ..

# 4. DockerでDB起動
docker compose up -d

# 5. DBマイグレーション
python -m clawtion db migrate

# 6. Vault初期化（オプション）
python -m clawtion init

# 7. .envファイルを作成
# clawtion/ディレクトリに.envを作成し、以下を記述:
#   CLAWTION_DB_URL=postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion
#   CLAWTION_GEMINI_API_KEY=あなたのAPIキー
#   CLAWTION_VAULT=~/Documents/clawtion-vault
#   CLAWTION_LOG_LEVEL=DEBUG
```

### 9.3 起動

```bash
# ターミナル1: バックエンド
cd clawtion
python -m uvicorn clawtion.interfaces.api.app:create_app --factory --host 127.0.0.1 --port 8000

# ターミナル2: フロントエンド
cd clawtion/clawtion-ui
npm run dev

# → ブラウザで http://localhost:5173 を開く
```

### 9.4 テスト実行

```bash
# Pythonテスト
cd clawtion
pytest

# フロントエンド ユニットテスト
cd clawtion-ui
npm test

# フロントエンド E2Eテスト
npx playwright test
```

### 9.5 停止

```bash
# フロントエンド: Ctrl+C
# バックエンド: Ctrl+C
# DB: docker compose down  （データはボリュームに残る）
# DB完全削除: docker compose down -v  （データも削除）
```

---

## 付録: 修正履歴（主要バグ）

| # | 日付 | ファイル | 問題 | 修正 |
|---|------|---------|------|------|
| 1 | 2026-05-05 | app.py | QueueManagerインポートパス誤り | `clawtion.indexing.queue` → `clawtion.core.indexing.queue` |
| 2 | 2026-05-05 | note/service.py | update()がtitle/folder/tags未対応 | オプションパラメータ追加 |
| 3 | 2026-05-05 | app.py | indexing_service=None | IndexingService適切に初期化 |
| 4 | 2026-05-06 | logging.py | Python 3.13 basicConfig競合 | stream+handlers同時指定を修正 |
| 5 | 2026-05-06 | config/loader.py | CLAWTION_DB_URLマッピング欠落 | env overrideに追加 |
| 6 | 2026-05-06 | gemini.py | 存在しないモデル名(text-embedding-004) | models/gemini-embedding-2 に修正 |
| 7 | 2026-05-06 | indexing/service.py | DBにupdated_atカラム不在 | ON CONFLICT句から削除 |
| 8 | 2026-05-06 | routes/search.py | metadata_filter→filter不一致 | パラメータ名修正 |
| 9 | 2026-05-06 | routes/search.py | SearchResultオブジェクト未展開 | .results抽出を追加 |
| 10 | 2026-05-06 | routes/search.py | UUID→str変換漏れ | _serialize_search_item追加 |
| 11 | 2026-05-06 | routes/queue.py | metricsがlimit=0で空リスト | 直接COUNTクエリに修正 |
| 12 | 2026-05-06 | routes/notes.py | _serialize_noteのorバグ | None判定に修正 |
| 13 | 2026-05-06 | app.py | .env自動読み込みなし | _load_dotenv追加 |
| 14 | 2026-05-06 | indexing/service.py | json.dumpsでpgvector形式不一致 | ベクトルリテラル形式に修正 |
