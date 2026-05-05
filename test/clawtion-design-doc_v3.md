# clawtion 設計書 / 要件定義書 / プロジェクト計画書

**バージョン:** 1.0
**作成日:** 2026年4月27日
**ステータス:** Phase 1 実装準備完了

---

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [全体アーキテクチャ](#2-全体アーキテクチャ)
3. [ストレージ設計](#3-ストレージ設計)
4. [チャンキング設計](#4-チャンキング設計)
5. [ファイル形式と取り込み](#5-ファイル形式と取り込み)
6. [Embedding設計](#6-embedding設計)
7. [Indexingパイプライン](#7-indexingパイプライン)
8. [検索設計](#8-検索設計)
9. [インターフェース層](#9-インターフェース層)
10. [Claude Code統合](#10-claude-code統合)
11. [ロギング・監視](#11-ロギング監視)
12. [国際化（i18n）](#12-国際化i18n)
13. [配布・運用](#13-配布運用)
14. [開発フェーズ](#14-開発フェーズ)
15. [設定ファイル仕様](#15-設定ファイル仕様)
16. [テスト戦略](#16-テスト戦略)
17. [将来の拡張](#17-将来の拡張)
18. [付録](#18-付録)

---

## 1. プロジェクト概要

### 1.1 プロジェクト名

**clawtion**

ロブスター（クロー = claw）+ Notion から派生した造語。Claude Codeから操作可能なローカル知識ベースであり、人間も使えるメモ帳アプリ。

### 1.2 目的・ビジョン

clawtionは、以下の2つの役割を1つのアプリケーションで実現する：

1. **AIのためのナレッジベース**: Claude Codeがエージェント的に検索・参照できるローカルRAG基盤
2. **人間のためのメモ帳**: Markdownノートを書き、検索し、整理できる軽量ノートアプリ

両者は同じデータ（ローカルの.mdファイル群とDB）を共有し、UIから書いたノートはAIから即座に検索可能になる。

### 1.3 ターゲットユーザー

- Claude Codeを日常的に使う開発者・知識労働者
- 個人のナレッジベースをローカルに持ちたいユーザー
- Obsidianのような既存メモ帳ツールにAI機能を追加したいユーザー
- データプライバシーを重視し、クラウドにノートを置きたくないユーザー

### 1.4 主要機能

#### Phase 1（最初のリリース）で実現する機能

- ローカルファイルベース（.md / .pdf / 画像）の知識ベース構築
- Postgres + pgvectorによるベクトル検索
- Hybrid Search（ベクトル + キーワード + メタデータフィルタ）
- Gemini Embedding 2による埋め込み生成（マルチモーダル）
- Claude Codeからの自動アクセス（MCP + サブエージェント + スキル）
- CLI経由のすべての操作
- REST APIによる外部アプリ統合
- 自動indexingパイプライン
- 中断・再開可能な処理

#### Phase 2以降で追加する機能

- Multi-resolution chunking（fine / coarse の追加）
- GraphRAG（オプション機能）
- Anthropic Contextual Retrieval（オプション機能）
- Tauriデスクトップアプリ（ノート編集UI）
- 複数Vault対応
- 音声・動画ファイル対応

### 1.5 非目標（やらないこと）

- クラウド同期機能（ローカル完結が原則）
- マルチユーザー・チーム機能（しかし、将来的に拡張する可能性あり）
- リアルタイム共同編集
- WYSIWYGリッチエディタ（Phase 1ではエディタは外部に委ねる）
- 自前のLLM推論（embeddingはAPI、エージェントはClaude Codeに委譲）

### 1.6 ライセンス

**MIT License**

商用利用、改変、配布、サブライセンス、すべて許可。クレジット表記のみ要求。

---

## 2. 全体アーキテクチャ

### 2.1 3層構造

clawtionは「コアロジック層」「インターフェース層」「外部統合層」の3層で構成される。各層は明確に分離されており、独立してテスト・拡張できる。

```
┌─────────────────────────────────────────────────────────┐
│ 外部統合層                                                │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ Claude Code      │  │ 他アプリ（REST API経由）   │    │
│  │  ├ Subagent      │  │                          │    │
│  │  ├ Skill         │  │                          │    │
│  │  └ MCP Client    │  │                          │    │
│  └──────────────────┘  └──────────────────────────┘    │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
┌──────────────▼──────────────────────▼───────────────────┐
│ インターフェース層                                         │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │   CLI    │  │ MCP Server │  │  REST API        │    │
│  │ clawtion │  │            │  │  (FastAPI)       │    │
│  └──────────┘  └────────────┘  └──────────────────┘    │
│                       │                                  │
│         全インターフェースが同じコアを呼ぶ                 │
└───────────────────────┼──────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────┐
│ コアロジック層                                             │
│  ┌────────────────────┐  ┌────────────────────────┐    │
│  │ IndexingService    │  │  SearchService          │    │
│  │  ├ FileWatcher     │  │  ├ SemanticSearch       │    │
│  │  ├ Chunker         │  │  ├ KeywordSearch        │    │
│  │  ├ EmbeddingClient │  │  ├ HybridSearch (RRF)   │    │
│  │  └ QueueManager    │  │  └ MetadataFilter       │    │
│  └────────────────────┘  └────────────────────────┘    │
│  ┌────────────────────┐  ┌────────────────────────┐    │
│  │ NoteService (CRUD) │  │  DBLayer (pgvector)     │    │
│  └────────────────────┘  └────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────┐
│ ストレージ層                                               │
│  ┌────────────────────┐  ┌────────────────────────┐    │
│  │ Vault (.md files)  │  │  Postgres + pgvector    │    │
│  │ ~/Documents/...    │  │  Docker container       │    │
│  └────────────────────┘  └────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### 2.2 技術スタック

| カテゴリ | 採用技術 | 理由 |
|---|---|---|
| 言語 | Python 3.11+ | エコシステム充実、async性能、型ヒント |
| DB | PostgreSQL 16 + pgvector 0.7+ | フルSQL + ベクトル検索、ACID、Hybrid Search |
| DBコンテナ | Docker + docker-compose | 環境差異吸収、再現性 |
| Embedding | Gemini Embedding 2 (preview) | マルチモーダル、8K context、MRL |
| Indexing | LlamaIndex 0.12+ | Markdown対応、pgvector統合 |
| 文分割 | pysbd | 多言語対応（日本語・英語ほか） |
| ファイル監視 | watchdog | クロスプラットフォーム |
| マイグレーション | Alembic | スキーマバージョン管理 |
| REST API | FastAPI | OpenAPI自動生成、型安全 |
| MCPサーバー | mcp Python SDK | 公式SDK |
| CLI | Click | 標準的、Pythonic |
| ロギング | structlog | 構造化ログ |
| パッケージ管理 | pip / pipx | OSS配布の標準 |
| テスト | pytest + pytest-asyncio | 業界標準 |
| CI | GitHub Actions | 無料、OSSで標準 |

### 2.3 データフロー

#### Indexingフロー

```
ファイル保存（外部エディタ or clawtion CLI）
        ↓
file watcher が変更検知
        ↓
content_hash 計算 → DB既存ハッシュと比較
        ↓
（ハッシュが同じ）→ スキップ
        ↓
（ハッシュが異なる）→ indexing_queue に追加
        ↓
worker がキューから取り出し
        ↓
ファイルをスナップショット（バッファリング）
        ↓
チャンク分割（粒度ごとに）
        ↓
チャンク単位の hash チェック → 同じチャンクは再利用
        ↓
新規/変更チャンクのみ embedding 生成（Batch API）
        ↓
DBにUPSERT（古いチャンクは削除、新しいチャンクを挿入）
        ↓
indexing_queue を completed に更新
```

#### 検索フロー

```
Claude Code（メイン）が「ユーザーノート検索」を判断
        ↓
clawtion-search Skill が起動
        ↓
clawtion-knowledge Subagent に委譲
        ↓
Subagent が検索戦略を決定
        ↓
MCP Tool 呼び出し（semantic_search / keyword_search / hybrid_search）
        ↓
clawtion MCPサーバーがコアロジックを呼ぶ
        ↓
SearchService がDBクエリ実行
        ↓
結果 + 診断情報 + suggestions_for_claude を返却
        ↓
Subagent が結果を整理・要約
        ↓
メインClaude に簡潔なサマリーだけ返す（コンテキスト汚染回避）
```

### 2.4 設計原則

clawtionのコードベース全体に適用する設計原則を以下に定める。Phase 1のバックエンド・CLI・API実装から適用し、Phase 3のUI実装時にも同じ原則を継承する。

#### 2.4.1 Separation of Concerns（関心の分離）

clawtionの3層アーキテクチャ（2.1節）は、関心の分離を構造的に実現している。この原則をコードレベルでも徹底する。

**層間の分離ルール:**

| 層 | 責務 | 触れてはいけないもの |
|---|---|---|
| コアロジック層 | ビジネスルール、データ処理 | HTTP、CLI引数、MCP protocol |
| インターフェース層 | 入出力の変換、プロトコル処理 | DB直接操作、embedding生成 |
| ストレージ層 | データ永続化、クエリ実行 | ビジネスルールの判断 |

**分離の検証テスト:** 「CLIをREST APIに置き換えたい」と思ったとき、コアロジック層のコードを一切触らずにできるか？ できるなら分離が正しく実現されている。clawtionでは CLI / MCP Server / REST API の3つがすべて同じコアロジックを呼ぶ設計（2.1節の図）により、この検証を満たす。

**モジュール内部の分離:**

各サービスクラス内でも、以下を混在させない。

- データアクセスロジック（DBクエリ）とビジネスロジック（チャンキング判定、スコア計算等）
- I/O処理（ファイル読み書き、API呼び出し）と純粋な変換処理（ハッシュ計算、テキスト分割等）

```python
# 悪い例：サービス内でDBクエリとビジネスロジックが混在
class SearchService:
    def hybrid_search(self, query: str) -> list:
        # DBクエリ（データアクセス）
        semantic = db.execute("SELECT ... ORDER BY embedding <=> %s", embed(query))
        keyword = db.execute("SELECT ... WHERE tsvector @@ %s", query)
        # RRFスコア計算（ビジネスロジック）
        for r in semantic:
            r.score = 1.0 / (60 + r.rank)
        ...

# 良い例：責務を分離
class SearchService:
    def __init__(self, db: DBLayer, embedder: EmbeddingClient):
        self._db = db
        self._embedder = embedder

    def hybrid_search(self, query: str) -> SearchResult:
        query_vec = self._embedder.embed_query(query)
        semantic_ranks = self._db.semantic_search(query_vec)
        keyword_ranks = self._db.keyword_search(query)
        return self._fuse_rrf(semantic_ranks, keyword_ranks)

    def _fuse_rrf(self, *rank_lists) -> SearchResult:
        """純粋なビジネスロジック。DB不要、テスト容易。"""
        ...
```

#### 2.4.2 オブジェクト指向設計とSOLID原則

clawtionのコアロジック層は、オブジェクト指向設計とSOLID原則に基づいて構築する。Pythonの型ヒント・抽象基底クラス・プロトコルを活用し、保守性・拡張性・テスト容易性を確保する。

**SOLID原則のclawtion適用:**

| 原則 | 内容 | clawtionでの適用 |
|---|---|---|
| **S** - Single Responsibility | 1クラス1責務 | `IndexingService`は indexing のみ、`SearchService`は検索のみ。チャンク分割は`Chunker`に委譲 |
| **O** - Open/Closed | 拡張に開き、修正に閉じる | 新しいファイル形式の追加は`FileProcessor`のサブクラス追加で対応。既存コード修正不要 |
| **L** - Liskov Substitution | サブクラスは親クラスと置換可能 | `GeminiEmbeddingClient`を`OllamaEmbeddingClient`に差し替えても呼び出し側に影響なし |
| **I** - Interface Segregation | クライアントが使わないメソッドに依存させない | MCPサーバーは検索系・CRUD系・ナビゲーション系のインターフェースを分離 |
| **D** - Dependency Inversion | 上位モジュールは下位モジュールに依存せず、抽象に依存 | `IndexingService`は具体的な`GeminiClient`ではなく`EmbeddingClient`プロトコルに依存 |

**抽象化の実装方針:**

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class EmbeddingClient(Protocol):
    """Embedding生成の抽象インターフェース。
    Phase 1: GeminiEmbeddingClient
    Phase 2: OpenAIEmbeddingClient, OllamaEmbeddingClient
    """
    async def embed_document(self, content: str) -> list[float]: ...
    async def embed_query(self, query: str) -> list[float]: ...
    async def embed_batch(self, contents: list[str]) -> list[list[float]]: ...

    @property
    def model_name(self) -> str: ...
    @property
    def dimensions(self) -> int: ...


class FileProcessor(Protocol):
    """ファイル形式ごとの処理の抽象インターフェース。"""
    def can_process(self, file_path: str) -> bool: ...
    def extract_content(self, file_path: str) -> ExtractedContent: ...
    def get_supported_extensions(self) -> list[str]: ...
```

**クラス設計のガイドライン:**

- 1クラス200行以内を目安とし、超えたら責務の分割を検討する
- コンストラクタで依存オブジェクトを注入する（Dependency Injection）。グローバル状態やシングルトンに依存しない
- 可変状態を最小化する。状態を持つ場合は、その変更箇所を明確に限定する
- `dataclass`や`NamedTuple`を活用し、データの構造を型で表現する

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Chunk:
    """イミュータブルなデータオブジェクト。"""
    level: ChunkLevel
    content: str
    content_with_context: str
    content_hash: str
    chunk_index: int
    chunk_total: int
    heading_path: str | None = None
    token_count: int = 0
    char_count: int = 0
```

**合成（Composition）を継承より優先する:**

```python
# 悪い例：深い継承階層
class BaseService:
    ...
class BaseSearchService(BaseService):
    ...
class HybridSearchService(BaseSearchService):
    ...

# 良い例：合成で組み立てる
class SearchService:
    def __init__(
        self,
        db: DBLayer,
        embedder: EmbeddingClient,
        scorer: RRFScorer,
    ):
        self._db = db
        self._embedder = embedder
        self._scorer = scorer
```

#### 2.4.3 API-First設計（契約駆動開発）

clawtionのREST APIは、API-First（Design-First）のアプローチで設計する。

**原則:**
- コードを書く前にAPI仕様（OpenAPI）を先に定義し、フロントエンド（Phase 3 UI）とバックエンドの共通契約とする
- FastAPIは型定義からOpenAPI 3.0仕様を自動生成する。この自動生成されたOpenAPI仕様を「契約書」として扱い、Phase 3でUIを実装する際にはこの契約に基づいてフロントエンドを構築する
- MCPツールのインターフェース定義（9.2節）も同様に契約として扱う。ツールの入出力型を先に定義し、実装はその型に従う

**RESTful設計のルール（clawtionに適用）:**

| 項目 | clawtionの設計 | 理由 |
|---|---|---|
| URL | 名詞中心（`/notes`, `/chunks`） | HTTP メソッドで操作を表現。動詞不要 |
| 命名 | 複数形統一（`/notes`, `/folders`） | 一貫性 |
| レスポンス | `{ data: [...], meta: {} }` 構造統一 | フロントエンドのコードがシンプルに |
| エラー | HTTPステータス + `{ error: { code, message, details } }` | クライアントが「なぜ失敗したか」を判定可能 |
| バージョニング | `/api/v1/` プレフィックス | 破壊的変更時に既存クライアントを守る |

**エラーレスポンスの統一フォーマット:**

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "指定されたドキュメントが見つかりません",
    "details": {
      "document_id": "uuid-xxx",
      "suggestion": "clawtion note list で一覧を確認してください"
    }
  }
}
```

**HTTPステータスコードの使い分け:**

| ステータス | 用途 | clawtionでの例 |
|---|---|---|
| 200 | 成功 | 検索結果返却、ノート取得 |
| 201 | リソース作成成功 | ノート作成 |
| 400 | クライアントエラー | 不正なクエリパラメータ |
| 401 | 認証エラー | APIキー未設定・無効 |
| 404 | リソース不在 | 存在しないdocument_id指定 |
| 409 | 競合 | 同じfile_pathのノートが既に存在 |
| 422 | バリデーションエラー | 必須フィールド欠落 |
| 429 | レートリミット | API呼び出し過多 |
| 500 | サーバーエラー | DB接続失敗、予期しないエラー |
| 503 | サービス利用不可 | Indexing処理中でDB負荷高 |

#### 2.4.4 型安全性の徹底

Pythonの型ヒントを全コードに適用し、mypyの`strict`モードで静的型チェックを強制する。

**必須ルール:**
- すべての関数・メソッドに引数と戻り値の型アノテーションを記述する
- `Any`型の使用は原則禁止。使用する場合はコメントで理由を明記する
- `TypedDict`、`Literal`、`TypeAlias`を活用し、JSONBフィールドやenum的な値にも型を付ける
- Pydanticモデルでバリデーションと型定義を統合する（FastAPIのリクエスト/レスポンスモデル）

```python
from typing import Literal, TypeAlias
from pydantic import BaseModel, Field

ChunkLevel: TypeAlias = Literal["file", "coarse", "fine"]
QueueStatus: TypeAlias = Literal["pending", "processing", "partial", "completed", "failed"]

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    granularity: ChunkLevel | Literal["all"] = "all"
    top_k: int = Field(default=10, ge=1, le=100)
    filter: MetadataFilter | None = None

class SearchResponse(BaseModel):
    results: list[ChunkResult]
    context: SearchContext
```

**静的解析ツールチェーン:**

| ツール | 役割 | 設定 |
|---|---|---|
| mypy | 静的型チェック | `strict = true` |
| ruff | リンター + フォーマッター | ruffのみで完結（black, isort, flake8を統合） |
| pyright | 型推論（エディタ連携用） | mypyと併用可 |

**CIでの強制:**
- `mypy --strict src/`が通らなければマージ不可
- `ruff check src/ tests/`が通らなければマージ不可
- pre-commitフックで開発者のローカルでも自動実行

#### 2.4.5 AI生成コードとの共存

clawtionの開発においてもAIコード生成ツール（Claude Code等）を積極的に活用するが、生成されたコードは必ず以下の基準でレビュー・修正する。

**AI生成コードの典型的な問題（Pythonバックエンド文脈）:**

- 関数・クラスが肥大化する（1関数100行超、1クラス500行超）
- 依存関係がハードコードされる（Dependency Injectionされない）
- エラーハンドリングが場当たり的（統一されたパターンがない）
- 型ヒントが不完全（`Any`多用、戻り値型の省略）
- テストコードが生成されない、または品質が低い

**Vibe & Verifyワークフロー（clawtion版）:**

1. AIでコードの土台を生成する（80%の速度向上）
2. 以下の観点でレビュー・修正する（20%の仕上げ）:
   - SOLID原則に準拠しているか
   - 型ヒントが完全か（mypy strictが通るか）
   - エラーハンドリングが統一パターンに従っているか
   - クラス・関数の責務が単一か（200行以内か）
   - 依存関係が注入されているか（テスト容易か）
   - ログ出力が3層構造（11節）に従っているか

---

## 3. ストレージ設計

### 3.1 ファイルシステム構造（Vault）

#### ユーザーのVault（任意のフォルダ）

```
~/Documents/my-vault/                ← ユーザーが指定
├── tech/
│   ├── rag.md
│   ├── pgvector.md
│   └── images/
│       └── architecture.png
├── personal/
│   └── diary.md
├── attachments/
│   ├── document.pdf
│   └── photo.jpg
└── .clawtion/                       ← Vault内のclawtion設定
    └── config.yaml                  ← Vault固有設定（オプション）
```

#### clawtionのデータ置き場

```
~/.clawtion/                         ← グローバル設定
├── config.yaml                      ← グローバル設定
├── secrets.enc                      ← 暗号化APIキー（keychain使えない場合のフォールバック）
├── pgdata/                          ← Postgres DBのデータディレクトリ
│   ├── base/
│   ├── pg_wal/
│   └── ...
├── logs/                            ← 構造化ログ
│   ├── clawtion.log
│   └── clawtion.log.2026-04-26.gz
├── trash/                           ← ゴミ箱（削除されたファイルの一時保管）
│   └── 2026-04-27/
│       └── deleted-note.md
└── i18n/                            ← 翻訳ファイル
    ├── en.json
    ├── ja.json
    └── ...
```

### 3.2 DBスキーマ詳細

#### documents テーブル（ファイル単位）

```sql
CREATE TABLE documents (
    -- 識別子
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ファイル情報
    file_path TEXT NOT NULL UNIQUE,           -- Vault相対パス（例: tech/rag.md）
    folder_path TEXT NOT NULL,                -- フォルダパス（例: tech/）
    title TEXT NOT NULL,                      -- ファイル名（拡張子なし）
    file_extension VARCHAR(10) NOT NULL,      -- md / pdf / png 等
    file_size_bytes BIGINT NOT NULL,

    -- 変更検知
    content_hash VARCHAR(64) NOT NULL,        -- ファイル全体のSHA-256

    -- メタデータ
    tags JSONB DEFAULT '[]'::jsonb,           -- ["rag", "tech"]
    wikilinks JSONB DEFAULT '[]'::jsonb,      -- [["other-note"], ["page#section"]]
    metadata JSONB DEFAULT '{}'::jsonb,       -- frontmatter等

    -- インデクシング状態
    total_chunks INTEGER DEFAULT 0,
    has_file_level BOOLEAN DEFAULT false,
    has_coarse_level BOOLEAN DEFAULT false,
    has_fine_level BOOLEAN DEFAULT false,
    last_indexed_at TIMESTAMPTZ,

    -- ライフサイクル
    is_deleted BOOLEAN DEFAULT false,         -- ゴミ箱フラグ
    deleted_at TIMESTAMPTZ,

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_documents_folder ON documents (folder_path);
CREATE INDEX idx_documents_extension ON documents (file_extension);
CREATE INDEX idx_documents_tags ON documents USING GIN (tags);
CREATE INDEX idx_documents_deleted ON documents (is_deleted, deleted_at);
CREATE INDEX idx_documents_updated ON documents (updated_at DESC);
```

#### document_chunks テーブル（チャンク単位）

```sql
CREATE TABLE document_chunks (
    -- 識別子
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,

    -- 粒度
    chunk_level VARCHAR(10) NOT NULL,         -- 'file' | 'coarse' | 'fine'
    chunk_index INTEGER NOT NULL,             -- 同レベル内での順序（0始まり）
    chunk_total INTEGER NOT NULL,             -- 同レベル内の総チャンク数（冗長コピー）

    -- 階層関係（Phase 2以降で活用、Phase 1ではNULL可）
    parent_chunk_id UUID REFERENCES document_chunks(chunk_id),

    -- 構造情報
    heading_path TEXT,                        -- "Section A > Subsection B"
    page_number INTEGER,                      -- PDFの場合

    -- コンテンツ
    content TEXT NOT NULL,                    -- 本文（ユーザー表示用）
    content_with_context TEXT NOT NULL,       -- コンテキスト注入版（embedding入力用）
    content_hash VARCHAR(64) NOT NULL,        -- チャンクのハッシュ（差分判定用）

    -- ベクトル
    embedding vector(768),                    -- Gemini Embedding 2の768次元
    embedding_model VARCHAR(50) NOT NULL,     -- 'gemini-embedding-2-preview'
    embedding_dimensions INTEGER NOT NULL,    -- 768
    embedded_at TIMESTAMPTZ,

    -- メトリクス
    token_count INTEGER NOT NULL,
    char_count INTEGER NOT NULL,

    -- キーワード検索用
    tsvector tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,

    -- メタデータ
    metadata JSONB DEFAULT '{}'::jsonb,

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT now(),

    -- 制約
    UNIQUE (document_id, chunk_level, chunk_index)
);

-- ベクトル検索用インデックス（HNSW）
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

-- キーワード検索用
CREATE INDEX idx_chunks_tsvector ON document_chunks USING GIN (tsvector);

-- 検索フィルタ用
CREATE INDEX idx_chunks_doc_level ON document_chunks (document_id, chunk_level, chunk_index);
CREATE INDEX idx_chunks_level ON document_chunks (chunk_level);
CREATE INDEX idx_chunks_parent ON document_chunks (parent_chunk_id);
CREATE INDEX idx_chunks_hash ON document_chunks (content_hash);
```

#### indexing_queue テーブル（処理キュー）

```sql
CREATE TABLE indexing_queue (
    queue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 対象
    document_id UUID REFERENCES documents(document_id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    operation VARCHAR(20) NOT NULL,           -- 'index' | 'reindex' | 'delete'

    -- ステータス
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 'pending' | 'processing' | 'partial' | 'completed' | 'failed'

    -- 進捗（中断・再開用）
    progress JSONB DEFAULT '{}'::jsonb,
    -- 例: {"chunks_total": 10, "chunks_done": 7, "current_level": "fine"}

    -- 制御
    priority INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- エラー
    last_error TEXT,
    error_history JSONB DEFAULT '[]'::jsonb,

    -- タイムスタンプ
    created_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_queue_status ON indexing_queue (status, priority DESC, created_at);
CREATE INDEX idx_queue_document ON indexing_queue (document_id);
```

#### trash テーブル（ゴミ箱）

```sql
CREATE TABLE trash (
    trash_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_document_id UUID NOT NULL,
    original_file_path TEXT NOT NULL,
    original_content TEXT NOT NULL,           -- ファイル本文をテキストで保管
    original_metadata JSONB,
    deleted_at TIMESTAMPTZ DEFAULT now(),
    auto_purge_at TIMESTAMPTZ NOT NULL        -- 自動削除予定日時（デフォルト+7日）
);

CREATE INDEX idx_trash_purge ON trash (auto_purge_at);
```

#### vault_settings テーブル（Vault固有設定）

```sql
CREATE TABLE vault_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 例: ('embedding_model', '"gemini-embedding-2-preview"')
-- 例: ('multi_resolution_enabled', 'false')
```

#### schema_version テーブル（Alembicマイグレーション）

```sql
-- Alembicが自動管理
CREATE TABLE alembic_version (
    version_num VARCHAR(32) PRIMARY KEY
);
```

### 3.3 マイグレーション戦略

**ツール:** Alembic（SQLAlchemyのマイグレーションライブラリ）

**ファイル構造:**
```
alembic/
├── versions/
│   ├── 001_initial_schema.py
│   ├── 002_add_chunk_levels.py
│   └── ...
├── alembic.ini
└── env.py
```

**動作:**
- `clawtion start` 時にDBバージョンをチェック
- 未適用のマイグレーションがあれば自動実行
- ダウングレードは原則サポートしない（バックアップから復元）

**マイグレーションの原則:**
- 既存データを壊さない（ALTER TABLE ADD COLUMN 主体）
- カラム削除は2段階（コードから参照を削除 → 次のリリースでカラム削除）
- リネームは「新カラム作成 → データコピー → 旧カラム削除」の3段階

### 3.4 .mdファイルとDBの関係

**プライマリストレージは .mdファイル（ファイルシステム）**

理由：
- ユーザーが直接見られる・編集できる（Obsidian、VSCodeなど任意のエディタ可）
- DBが壊れてもデータは消えない
- バージョン管理（Git）と相性が良い

**DBは.mdファイルのインデックス（検索用キャッシュ）**

役割：
- ベクトル検索・キーワード検索の高速実行
- メタデータの構造化保存
- 文書間リンク・タグの管理

**整合性の保証:**
- ファイル変更時、`content_hash` で変更検知
- 検出後、自動で再indexing
- ファイル削除時、対応するDB行も削除（ゴミ箱経由）

---

## 4. チャンキング設計

### 4.1 3粒度の仕様（最終版）

| 粒度 | 単位 | 切れ目 | 目安 | 上限 |
|---|---|---|---|---|
| **file** | ファイル全体 | ファイル境界 | 全体 | 1500トークン超ならスキップ |
| **coarse** | 見出しセクション | 見出し（H1/H2/H3） or 段落 | 800トークン | 1500トークン |
| **fine** | 文 | 句点・ピリオド・改行 | 100トークン | トークン数より構造優先 |

**重要原則:**
- すべて構造ベースで切る。トークン数は目安と上限の安全弁のみ
- 文の途中では絶対に切らない
- コードブロック・テーブル・リスト項目は分割しない

### 4.2 chunk_level の動作（Phase 1とPhase 2）

**Phase 1（デフォルト）:**
- `multi_resolution.enabled = false`
- file粒度のみ生成
- ファイルが1500トークン超の場合、緊急fallbackとしてcoarse相当の見出し分割を実施（chunk_level='coarse'として保存）

**Phase 2（オプション）:**
- 設定で `multi_resolution.enabled = true` に
- 各粒度を個別にON/OFF可能
- 有効化されたタイミングで未生成の粒度を自動生成（既存fileチャンクは保持）

### 4.3 アルゴリズム詳細

#### file粒度のアルゴリズム

```python
def chunk_file_level(file_content: str, max_tokens: int = 1500) -> Optional[Chunk]:
    """ファイル全体を1チャンクとして扱う。上限超過時はNoneを返す。"""
    token_count = count_tokens(file_content)
    if token_count > max_tokens:
        return None
    return Chunk(
        level='file',
        content=file_content,
        chunk_index=0,
        chunk_total=1
    )
```

#### coarse粒度のアルゴリズム

```python
def chunk_coarse_level(file_content: str, target: int = 800, max_tokens: int = 1500):
    """見出しベース分割。超過時は段落で再分割。"""

    # ステップ1: 見出しベースで分割
    sections = split_by_markdown_headings(file_content)
    # MarkdownNodeParser使用、H1/H2/H3で分割

    chunks = []
    for section in sections:
        if count_tokens(section.content) <= max_tokens:
            chunks.append(Chunk(
                level='coarse',
                content=section.content,
                heading_path=section.heading_path,
                ...
            ))
        else:
            # 段落で再分割
            paragraphs = split_by_paragraphs(section.content)
            sub_chunks = merge_paragraphs_to_target(paragraphs, target, max_tokens)
            chunks.extend(sub_chunks)

    # ステップ2: 短すぎる隣接セクションを結合
    chunks = merge_short_adjacent(chunks, target_min=200)

    # ステップ3: chunk_index, chunk_total を設定
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i
        chunk.chunk_total = len(chunks)

    return chunks
```

#### fine粒度のアルゴリズム

```python
def chunk_fine_level(file_content: str, target: int = 100):
    """文単位で分割。トークン数より文境界を優先。"""

    # 言語自動判定
    language = detect_language(file_content)  # ja / en / ...

    # 段落ごとに処理
    paragraphs = split_by_paragraphs(file_content)
    chunks = []

    for paragraph in paragraphs:
        # 構造保護対象なら分割しない
        if is_code_block(paragraph) or is_table(paragraph):
            chunks.append(make_chunk(paragraph))
            continue

        # 文単位で分割（pysbd使用）
        sentences = split_sentences(paragraph, language=language)

        # 隣接文を結合してtargetに近づける
        current_chunk = ""
        for sentence in sentences:
            tentative = current_chunk + sentence
            if count_tokens(tentative) <= target * 1.5:
                # まだ目安の1.5倍以内なら結合
                current_chunk = tentative
            else:
                # 超えるなら現在のchunkを確定し、新しいchunkを開始
                if current_chunk:
                    chunks.append(make_chunk(current_chunk))
                current_chunk = sentence

        if current_chunk:
            chunks.append(make_chunk(current_chunk))

    # chunk_index, chunk_total を設定
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i
        chunk.chunk_total = len(chunks)

    return chunks
```

### 4.4 構造保護ルール

以下の構造は粒度を問わず分割禁止：

- **コードブロック**: ```で囲まれた範囲（言語指定の有無問わず）
- **テーブル**: `|` で構成されたMarkdownテーブル
- **リスト項目**: `-` `*` `1.` で始まる単一項目（複数項目はセパレート可）
- **引用ブロック**: `>` で始まる範囲
- **画像参照**: `![alt](path)` は周辺テキストと一緒に保持

これらが上限トークンを超える場合：
- コードブロック・テーブル：そのまま1チャンク（上限超過を許容）
- 例外的に巨大な場合：警告ログを出して進める

### 4.5 言語別文分割

**ライブラリ:** pysbd（Python Sentence Boundary Disambiguation）

**サポート言語（pysbdが対応）:**
- 日本語、英語、中国語、韓国語、フランス語、ドイツ語、スペイン語、その他多数

**自動言語判定:** langdetect

**設定可能な動作:**
```yaml
chunking:
  language_detection: auto      # auto | manual
  fallback_language: ja         # 判定不能時のデフォルト
  manual_language: null         # auto時はnull、固定したい場合に指定
```

### 4.6 コンテキスト注入

すべての粒度で、embedding入力用テキストにコンテキストを前置する。

**フォーマット:**
```
folder: {folder_path} | file: {title} | section: {heading_path} | text: {content}
```

**具体例:**

ファイル: `tech/rag/agentic.md`、見出し: `Hybrid Search > RRF`、本文: `Reciprocal Rank Fusionは...`

```
folder: tech/rag | file: agentic | section: Hybrid Search > RRF | text: Reciprocal Rank Fusionは...
```

**注入されるフィールド:**
- `folder_path`: ファイルのVault内相対フォルダ
- `title`: ファイル名（拡張子除く）
- `heading_path`: チャンクが属する見出し階層（`>`で連結）
- `content`: チャンク本文

**注入対象:**
- `content_with_context` カラムに格納（embedding入力用）
- `content` カラムには本文のみ（ユーザー表示用）
- BM25インデックス（tsvector）も `content` のみ対象

ユーザーには常に元のテキストだけが見える。

---

## 5. ファイル形式と取り込み

### 5.1 Phase 1でサポートする形式

| 形式 | 拡張子 | 処理方法 |
|---|---|---|
| Markdown | `.md`, `.markdown` | テキストとしてチャンク分割 |
| プレーンテキスト | `.txt` | 段落単位でチャンク分割 |
| PDF | `.pdf` | Gemini Embedding 2のPDF直接埋め込み（最大6ページ、超過は分割） |
| 画像 | `.png`, `.jpg`, `.jpeg`, `.webp` | Gemini Embedding 2の画像埋め込み（1ファイル1チャンク） |

### 5.2 Phase 2で追加する形式

| 形式 | 拡張子 | 処理方法 |
|---|---|---|
| 音声 | `.mp3`, `.m4a`, `.wav` | Gemini Embedding 2の音声埋め込み（最大80秒、超過は分割） |
| 動画 | `.mp4`, `.mov` | Gemini Embedding 2の動画埋め込み（最大120秒、超過は分割） |

### 5.3 Markdown処理の詳細

**フロントマター:**
```yaml
---
title: タイトル
tags: [rag, tech]
created: 2026-04-27
---
```
これを抽出して `documents.metadata` JSONBに保存。

**Wikilink抽出:**
- `[[note-name]]` → `documents.wikilinks` に保存
- 双方向リンク（誰がこのノートを参照しているか）も検索可能

**見出し階層:**
- `#`, `##`, `###` を見出しとして認識
- `heading_path` カラムに `Parent > Child > Grandchild` 形式で保存

### 5.4 PDF処理の詳細

**ライブラリ:** Gemini Embedding 2の直接PDF対応 + フォールバックとしてpypdf

**処理フロー:**
1. PDF読み込み → ページ数チェック
2. 6ページ以下: そのまま1ファイルとしてGeminiに送信
3. 6ページ超: 6ページずつチャンクに分割、各チャンクを別embeddingとして保存
4. メタデータに `page_range` を記録（例: `{"start": 1, "end": 6}`）

**テキスト抽出（オプション、検索品質向上用）:**
- pypdfで本文テキストも抽出
- `content` カラムにテキスト保存（キーワード検索用）
- `embedding` はGeminiのPDF直接埋め込みを使用

### 5.5 画像処理の詳細

**処理フロー:**
1. 画像ファイル読み込み（最大20MB）
2. Gemini Embedding 2に画像として送信
3. 1画像1チャンクとして保存
4. `content` カラムには画像のメタ情報を記録（ファイル名、サイズ、Alt textなど）

**OCR/キャプション生成（Phase 1ではなし、Phase 3で検討）:**
- Gemini Vision APIで画像説明文生成
- キーワード検索もできるようになる
- Phase 1では画像のembedding検索のみ

### 5.6 ファイル形式判定

**判定方法:**
1. ファイル拡張子で第一判定
2. magic numberで第二判定（拡張子偽装対策）
3. 不明な拡張子は無視（indexingしない）

**インデックス対象外:**
- `.gitignore` などの設定ファイル
- 隠しファイル（`.` で始まる、ただし `.clawtion/` は別扱い）
- ユーザーが `exclude_folders` で除外したフォルダ内

---

## 6. Embedding設計

### 6.1 Gemini Embedding 2の使用方針

**モデルID:** `gemini-embedding-2-preview`

**確認済みスペック:**
- 入力上限: 8,192トークン（テキスト）
- 画像: 6枚/リクエスト、最大20MB
- 動画: 120秒
- 音声: 80秒
- PDF: 6ページ
- 出力次元: デフォルト3,072、MRLで768/1,536/3,072選択可
- マルチモーダル: テキスト・画像・動画・音声・PDFを同一空間に埋め込み

### 6.2 次元数の選択

**Phase 1のデフォルト: 768次元**

理由：
- Google公式が「production sweet spot」として推奨
- 3,072次元と比較して品質ほぼ同等
- ストレージ4分の1（1Mベクトルで12GB → 3GB）
- HNSWインデックスのメモリ効率も向上

**設定で変更可能:**
```yaml
embedding:
  output_dimensionality: 768  # 768 | 1536 | 3072
```

**注意:** 768未満（128, 256など）では手動正規化が必要になるため、サポート対象外。

### 6.3 task_typeとフォールバック

**Gemini Embedding 2のtask_type:**
- `RETRIEVAL_DOCUMENT`: ingest時（チャンク埋め込み）
- `RETRIEVAL_QUERY`: 検索時（クエリ埋め込み）

**preview段階でのバグ対応:**
2026年3月時点で「task_typeが効かない」報告あり（同じ入力で同じベクトルが返る）。

**フォールバック実装:**
```yaml
embedding:
  task_type:
    document: RETRIEVAL_DOCUMENT
    query: RETRIEVAL_QUERY
  use_manual_prefix_fallback: true
```

`use_manual_prefix_fallback = true` の場合、SDK経由のtask_type指定に加えて、テキストの先頭に明示的なプレフィックスを追加：

```
title: {title} | text: {content}                    # ドキュメント側
task: search result | query: {query}                # クエリ側
```

これによりGeminiの公式バグが解消されるまでの保険となる。バグ修正後は `false` に設定可能。

### 6.4 Batch API活用

**用途:** 大量indexing時のコスト削減（50%オフ）

**動作:**
- 通常API: $0.20 / 1M tokens、即時応答
- Batch API: $0.10 / 1M tokens、24時間以内に完了

**実装:**
```yaml
embedding:
  use_batch_api: true              # 大量indexing時
  batch_threshold: 100             # 100チャンク超で自動Batch化
  batch_max_wait_hours: 24
```

**動作ロジック:**
- 単発indexing（1ファイル更新）: 通常API（即時反映）
- 初回大量indexing（フォルダ一括登録）: Batch API（コスト最優先）
- ユーザーが `--batch` フラグ指定: 強制Batch API

### 6.5 同じチャンクのスキップ（コスト最適化）

**目的:** ファイルの一部編集時、変更がないチャンクは再embeddingしない

**仕組み:**
1. ファイル変更検知 → `content_hash` 比較
2. ハッシュ違う → ファイルを再チャンク化
3. 各新チャンクの `content_hash` を計算
4. DB内の同一ハッシュチャンクを検索
5. ヒットすれば既存embeddingを再利用（INSERTのみ、API呼ばない）
6. ヒットしなければ新規embedding生成

**効果:** ファイルの末尾に1段落追加した場合、最初の段落のembeddingは再生成されない

**実装:**
```python
def index_file_with_dedup(file_path: str):
    new_chunks = chunk_file(file_path)

    for new_chunk in new_chunks:
        existing = db.query(
            "SELECT chunk_id, embedding FROM document_chunks WHERE content_hash = %s",
            new_chunk.content_hash
        )
        if existing:
            # 既存embeddingを再利用
            new_chunk.embedding = existing.embedding
        else:
            # 新規生成
            new_chunk.embedding = embed(new_chunk.content_with_context)

    db.upsert(new_chunks)
```

### 6.6 APIエラーハンドリング

**エラー種別と対応:**

| エラー | 対応 |
|---|---|
| Rate limit (429) | 指数バックオフリトライ（最大5回） |
| Timeout | 3回リトライ後、queueに失敗ジョブとして記録 |
| Invalid API key (401) | 即座にユーザーに通知、ジョブ停止 |
| Quota exceeded | ユーザーに通知、24時間後に自動再開 |
| Network error | 1分後に自動リトライ |
| その他 | エラーログ記録、該当ジョブのみ失敗マーク |

**実装:**
```python
@retry(
    retry=retry_if_exception_type((RateLimitError, TimeoutError, NetworkError)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60)
)
def embed_with_retry(content: str) -> List[float]:
    return gemini_client.embed(content)
```

### 6.7 マルチモデル対応（将来）

DBスキーマで `embedding_model` カラムを最初から持つことで、将来のモデル切り替えに対応：

**現実的なシナリオ:**
- ユーザーがGemini → OpenAI text-embedding-3に変更したい
- ユーザーがローカルモデル（Ollama）に変更したい

**動作:**
1. 設定変更 → 警告メッセージ「次元数が違うため再indexing必要」
2. `clawtion reindex --confirm` で全件再生成
3. 新しいテーブル列（または別テーブル）に新モデルのembedding保存
4. 古いembeddingは保持（ロールバック用）

**Phase 1では Gemini Embedding 2 のみサポート。Phase 2でマルチモデル対応。**

---

## 7. Indexingパイプライン

### 7.1 ファイル監視

**ライブラリ:** watchdog（クロスプラットフォーム）

**監視対象:**
- ユーザーが指定したVaultフォルダ全体
- 再帰的に監視
- `exclude_folders` 設定で一部除外可能

**監視イベント:**
- ファイル作成 → indexingキューに追加（operation='index'）
- ファイル変更 → content_hashチェック → 変更ありなら再indexing
- ファイル削除 → DB削除 + ゴミ箱移動
- ファイル名変更 → DB更新（document_idは保持）

**動作タイミング:**
- アプリ起動中のみ動作
- アプリ未起動時の変更は、次回起動時にフォルダスキャンで検出

### 7.2 キュー管理

**スキーマ:** `indexing_queue` テーブル（前述）

**ステータス遷移:**
```
pending → processing → completed
              ↓
            partial (中断)
              ↓
          processing (再開)
              ↓
            completed

failed (リトライ上限超過)
```

**進捗保存（中断・再開対応）:**

`progress` JSONBフィールドに以下を記録：
```json
{
  "chunks_total": 12,
  "chunks_done": 7,
  "current_level": "fine",
  "level_progress": {
    "file": "completed",
    "coarse": "completed",
    "fine": {"done": 5, "total": 8}
  },
  "last_chunk_id": "uuid-of-last-completed-chunk"
}
```

**再開ロジック:**
```python
def resume_indexing(queue_item):
    progress = queue_item.progress

    # 完了済みのレベルはスキップ
    if progress['level_progress']['file'] == 'completed':
        skip_file_level()

    # 部分完了したレベルから再開
    if isinstance(progress['level_progress']['fine'], dict):
        start_from_chunk = progress['level_progress']['fine']['done']
        process_fine_level(start_from=start_from_chunk)
```

### 7.3 中断・再開の保証

**異常終了の検知:**

アプリ起動時、`status='processing'` のジョブをチェック：

```python
def on_startup_recover():
    """前回異常終了したジョブを再開可能状態に戻す"""
    db.execute("""
        UPDATE indexing_queue
        SET status = 'partial',
            last_error = 'Recovered from unexpected shutdown',
            error_history = error_history || %s::jsonb
        WHERE status = 'processing'
          AND started_at < now() - interval '5 minutes'
    """, json.dumps([{"timestamp": now(), "event": "shutdown_recovery"}]))
```

**チャンク単位のトランザクション:**

各チャンクのembedding生成・保存を独立したトランザクションで実行：

```python
for chunk in chunks_to_process:
    try:
        with db.transaction():
            embedding = embed(chunk.content_with_context)
            db.upsert_chunk(chunk_id=chunk.id, embedding=embedding)
            db.update_queue_progress(queue_id, chunks_done=current+1)
    except Exception as e:
        # このチャンクのみ失敗、他のチャンクは保存済み
        log.error(f"Chunk {chunk.id} failed: {e}")
        continue
```

**結果:** どのタイミングでクラッシュしても、最後に正常完了したチャンクまでは保存される。

### 7.4 自動indexingトリガー

**4つのトリガー（並行動作）:**

#### トリガー1: PC起動時チェック
- OSスケジューラに登録（macOS: launchd, Windows: タスクスケジューラ）
- ユーザーログイン時に `clawtion queue process` を実行
- pending/partialジョブがあれば処理開始

#### トリガー2: 1時間ごとチェック
- OSスケジューラに登録
- PC起動中のみ動作（PC停止中はトリガーなし）
- 1時間ごとに `clawtion queue process` を実行
- ファイル監視が動いていない時間帯（アプリ未起動時）に変更されたファイルも検出

#### トリガー3: アプリ起動時チェック
- clawtionアプリ（CLI/UI）起動時に自動実行
- フォルダ全体をスキャン → 変更検出 → キュー追加

#### トリガー4: 手動indexingボタン
- UIまたはCLIから `clawtion index now` で即実行
- ユーザーが「今すぐindex」したいときに使う

**設定:**
```yaml
indexing:
  triggers:
    on_pc_startup:
      enabled: true
    hourly_check:
      enabled: true
      interval_minutes: 60
    on_app_open:
      enabled: true
    manual_button:
      enabled: true   # 常に有効
```

### 7.5 サービス起動オプション

**ユーザーが選択できる動作モード:**

```bash
# モード1: マニュアル（デフォルト）
clawtion service install --mode manual
# アプリ起動時のみworker動作。最軽量。

# モード2: スケジュール
clawtion service install --mode scheduled
# PC起動時 + 1時間ごとチェック。OSスケジューラに登録。

# モード3: 常駐（ヘビーユーザー向け）
clawtion service install --mode background
# PC起動中ずっとworker常駐。ファイル変更を即時検知。
# Notion的な体験。

# アンインストール
clawtion service uninstall
```

**OS別実装:**

**macOS (launchd):**
```xml
<!-- ~/Library/LaunchAgents/com.clawtion.scheduler.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.clawtion.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/clawtion</string>
        <string>queue</string>
        <string>process</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>  <!-- 1時間ごと -->
    <key>RunAtLoad</key>
    <true/>  <!-- ログイン時実行 -->
</dict>
</plist>
```

**Windows (タスクスケジューラ):**
```powershell
# clawtion service install が内部で実行
schtasks /create /tn "ClawtionScheduler" /tr "clawtion queue process" /sc hourly /mo 1
schtasks /create /tn "ClawtionStartup" /tr "clawtion queue process" /sc onlogon
```

### 7.6 スナップショット方式（UIとIndexingの分離）

**目的:** ユーザーがファイルを編集している最中にindexingが走っても、編集体験をブロックしない

**仕組み:**

```
時刻 T0: ユーザーがファイルA編集中
時刻 T1: ファイルAがキューに登録される
時刻 T2: workerがファイルAを処理開始
        → この瞬間のファイルA内容を「スナップショット」としてメモリにコピー
        → indexingはスナップショットに対して走る
        → ユーザーは引き続きファイルAを編集可能（UIブロックなし）
時刻 T3: 編集が続く中、indexing完了（古い内容に対して）
        → 完了後、再度キューに「ファイルA」を追加
時刻 T4: 次回処理時に最新のファイルA内容で再indexing
```

**実装:**
```python
def process_file_with_snapshot(file_path):
    # スナップショット取得（ファイル全体をメモリに読み込み）
    with open(file_path, 'rb') as f:
        snapshot_content = f.read()
    snapshot_hash = sha256(snapshot_content)

    # スナップショットに対してindexing実行
    chunks = chunk_content(snapshot_content)
    embed_and_save(chunks)

    # 完了後、現在のファイルがスナップショットと違っていればキュー再登録
    current_hash = sha256(open(file_path, 'rb').read())
    if current_hash != snapshot_hash:
        queue.add(file_path, reason="changed_during_indexing")
```

**結果:**
- ユーザーは何も気にせず編集を続けられる
- 最終的にすべての変更が反映される（eventual consistency）
- indexingの一時的な「古さ」は許容（数分以内に追いつく）

### 7.7 アプリ終了時のUX

**indexing中にユーザーが終了しようとしたとき:**

```
┌─────────────────────────────────────┐
│ Indexing in progress                │
│                                     │
│ 3 notes are still being indexed.    │
│ Estimated time: 30 seconds          │
│                                     │
│ Closing now will pause indexing.    │
│ It will resume automatically:       │
│  • When you reopen this app         │
│  • At next hourly check (if         │
│    background service enabled)      │
│  • At next PC startup               │
│                                     │
│  [ Wait for completion ]            │
│  [ Close anyway ]                   │
└─────────────────────────────────────┘
```

「Close anyway」を選んでも：
- チャンク単位でセーブされているため、データは失われない
- 次回起動時に未完了ジョブから自動再開

### 7.8 削除とゴミ箱

**ファイル削除フロー:**

1. ユーザーがファイル削除
2. file watcherが検知
3. ファイルの内容を `trash` テーブルに保存（auto_purge_at = now + 7日）
4. `documents` テーブルの `is_deleted = true`、`deleted_at = now()`
5. `document_chunks` のembeddingは削除（再生成可能なので保管しない）

**自動パージ:**
- 1日1回（PC起動時 or hourly check時）にチェック
- `auto_purge_at < now()` のレコードを物理削除
- ファイル本文も削除

**復元:**
```bash
clawtion trash list           # ゴミ箱の中身表示
clawtion trash restore <id>   # ファイル復元（自動再indexing）
clawtion trash empty          # ゴミ箱を空にする（即時物理削除）
```

**設定:**
```yaml
trash:
  enabled: true
  auto_purge_after_days: 7
```

---

## 8. 検索設計

### 8.1 検索手法

#### Semantic Search（ベクトル検索）

**目的:** 意味的に近い内容を検索

**SQL:**
```sql
SELECT chunk_id, document_id, content, heading_path,
       embedding <=> %s::vector AS distance,
       1 - (embedding <=> %s::vector) AS similarity_score
FROM document_chunks
WHERE chunk_level = %s  -- granularity filter
  AND (metadata @> %s::jsonb OR %s::jsonb = '{}'::jsonb)  -- metadata filter
ORDER BY embedding <=> %s::vector
LIMIT %s;
```

**パラメータ:**
- `query_embedding`: クエリの埋め込みベクトル（768次元）
- `chunk_level`: 'file' / 'coarse' / 'fine' / null（全レベル）
- `metadata_filter`: JSONB条件（オプション）
- `top_k`: 返す件数（デフォルト10）

#### Keyword Search（BM25）

**目的:** 正確な単語・フレーズの一致

**SQL:**
```sql
SELECT chunk_id, document_id, content, heading_path,
       ts_rank_cd(tsvector, query, 32) AS keyword_score
FROM document_chunks,
     plainto_tsquery('simple', %s) query
WHERE tsvector @@ query
  AND chunk_level = %s
ORDER BY keyword_score DESC
LIMIT %s;
```

**注:** PostgreSQLの`ts_rank_cd`はBM25の近似実装。

#### Hybrid Search（RRF融合）

**目的:** ベクトル + キーワードの両方の利点を組み合わせ

**アルゴリズム:** Reciprocal Rank Fusion

```sql
WITH semantic_results AS (
    SELECT chunk_id, ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank_sem
    FROM document_chunks
    WHERE chunk_level = %s
    LIMIT 100
),
keyword_results AS (
    SELECT chunk_id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsvector, query, 32) DESC) AS rank_key
    FROM document_chunks, plainto_tsquery('simple', %s) query
    WHERE tsvector @@ query AND chunk_level = %s
    LIMIT 100
),
combined AS (
    SELECT
        COALESCE(s.chunk_id, k.chunk_id) AS chunk_id,
        COALESCE(1.0 / (60 + s.rank_sem), 0) + COALESCE(1.0 / (60 + k.rank_key), 0) AS rrf_score
    FROM semantic_results s
    FULL OUTER JOIN keyword_results k ON s.chunk_id = k.chunk_id
)
SELECT c.*, combined.rrf_score
FROM combined
JOIN document_chunks c ON c.chunk_id = combined.chunk_id
ORDER BY combined.rrf_score DESC
LIMIT %s;
```

**RRFの定数 k=60** は標準的な値（Cohereなどでも使用）。

### 8.2 メタデータフィルタ

**サポートする条件:**

| フィルタ | 例 |
|---|---|
| folder | `folder_path LIKE 'tech/%'` |
| tags | `tags @> '["rag"]'::jsonb` |
| date range | `updated_at BETWEEN ? AND ?` |
| extension | `file_extension = 'md'` |
| custom metadata | `metadata->>'author' = 'Claude'` |

**MCPツール例:**
```python
metadata_filter(
    folder="tech/rag",
    tags=["agentic"],
    date_from="2026-01-01",
    extension="md"
)
```

### 8.3 navigation情報

**目的:** Claude Codeが「同じファイルの他のチャンクを見たい」と判断できるようにする

**検索結果に含める情報:**

```json
{
  "chunk_id": "uuid",
  "content": "...",
  "score": 0.89,
  "document_id": "file_uuid",
  "chunk_level": "coarse",
  "chunk_index": 3,
  "chunk_total": 7,
  "heading_path": "Hybrid Search > RRF",
  "navigation": {
    "file_path": "tech/rag.md",
    "has_previous": true,
    "has_next": true,
    "previous_chunk_id": "uuid-prev",
    "next_chunk_id": "uuid-next",
    "all_chunks_in_file": ["uuid-0", "uuid-1", "uuid-2", ...]
  }
}
```

**追加MCPツール:**

```python
get_file_chunks(document_id, level="coarse")
# 指定ファイルの全チャンクを順序通り取得

get_neighbor_chunks(chunk_id, before=1, after=1)
# 前後N個のチャンクを取得（同一ファイル内）

get_parent_chunk(chunk_id)
# fine → coarse → file の順に上位レベルを取得（Phase 2用）
```

### 8.4 診断情報（suggestions_for_claude）

**目的:** Claude Codeが次の検索戦略を判断できる材料を提供

**検索結果のメタデータ部分:**

```json
{
  "results": [...],
  "context": {
    "tool": "semantic_search",
    "query": "RAGの利点",
    "embedding_model": "gemini-embedding-2-preview",
    "search_space": {
      "total_chunks": 1532,
      "filtered_by_metadata": 312,
      "filter_applied": {"folder": "tech/", "tags": ["rag"]}
    },
    "results_summary": {
      "count": 5,
      "score_range": [0.65, 0.92],
      "avg_score": 0.78
    },
    "execution_time_ms": 120,
    "suggestions_for_claude": [
      "If results seem insufficient, try keyword_search for exact term matching",
      "If too generic, try graph_search to traverse related entities (when GraphRAG enabled)",
      "Score range is healthy (>0.7), results likely relevant",
      "Multiple chunks from same file detected - consider get_file_chunks for full context"
    ]
  }
}
```

**suggestionsの生成ルール:**

| 条件 | suggestion |
|---|---|
| avg_score < 0.5 | "Low semantic match. Try keyword_search or broaden query" |
| count == 0 | "No results. Try broader query or check folder filter" |
| 同一document_idが3件以上 | "Multiple hits from same file. Consider get_file_chunks" |
| score_range広い | "Results vary in relevance. Consider top 2-3 only" |
| score_range狭い & 高い | "Strong consistent matches" |

### 8.5 検索粒度の指定（Phase 2以降）

```python
semantic_search(
    query="...",
    granularity="all"  # "all" | "file" | "coarse" | "fine"
)
```

**Phase 1ではfile粒度のみのため、`granularity` パラメータは事実上無視される。**

**Phase 2以降:** `granularity="all"` で3粒度すべてを検索し、粒度別に結果を返す（前述のmulti-resolution設計）。

---

## 9. インターフェース層

### 9.1 CLI仕様

**コマンド体系:**

```bash
# 初回セットアップ
clawtion init                            # 対話的セットアップ
clawtion init --vault ~/Documents/notes  # Vaultパス指定

# サービス管理
clawtion start                           # DB起動 + worker起動
clawtion stop                            # DB停止 + worker停止
clawtion status                          # 各サービスの状態表示
clawtion service install --mode <manual|scheduled|background>
clawtion service uninstall

# Indexing
clawtion index <path>                    # 指定パスをindex
clawtion index now                       # 現在のキューを処理
clawtion index --batch                   # Batch APIで一括処理
clawtion reindex                         # 全件再indexing（モデル変更時）

# キュー管理
clawtion queue status                    # キューの状態表示
clawtion queue list                      # 待機中ジョブ一覧
clawtion queue clear --failed            # 失敗ジョブをクリア
clawtion queue retry <queue_id>          # 失敗ジョブをリトライ

# 検索（Claude Code用、人間も使える）
clawtion search "query"                  # hybrid search
clawtion search --semantic "query"
clawtion search --keyword "query"
clawtion search --folder tech/ "query"

# ノート操作
clawtion note add "title" --content "..."
clawtion note get <id>
clawtion note update <id> --content "..."
clawtion note delete <id>
clawtion note list --folder tech/

# ゴミ箱
clawtion trash list
clawtion trash restore <id>
clawtion trash empty

# MCPサーバー（Claude Codeから呼ばれる）
clawtion mcp-serve                       # stdioでMCP server起動

# REST API
clawtion api-serve --port 8080           # FastAPI起動

# 診断
clawtion doctor                          # システム状態の総合診断
clawtion logs                            # ログ表示
clawtion logs --tail 100 --level error
clawtion config                          # 設定表示
clawtion config edit                     # 設定編集（$EDITORで開く）

# その他
clawtion --version
clawtion --help
```

### 9.2 MCPサーバー仕様

**起動:** `clawtion mcp-serve`（stdio経由）

**Claude Code側の設定:** `~/.claude.json` に自動追加（`clawtion init` 時）

```json
{
  "mcpServers": {
    "clawtion": {
      "command": "clawtion",
      "args": ["mcp-serve"],
      "env": {
        "CLAWTION_VAULT": "${VAULT_PATH}",
        "CLAWTION_DB_URL": "postgresql://localhost:5432/clawtion"
      }
    }
  }
}
```

**公開ツール一覧:**

#### 検索系

```typescript
semantic_search(
    query: string,
    granularity?: "all" | "file" | "coarse" | "fine",  // Phase 1では事実上"file"のみ
    top_k?: number = 10,
    filter?: MetadataFilter
): SearchResult

keyword_search(
    query: string,
    granularity?: string,
    top_k?: number = 10,
    filter?: MetadataFilter
): SearchResult

hybrid_search(
    query: string,
    granularity?: string,
    top_k?: number = 10,
    semantic_weight?: number = 0.5,
    filter?: MetadataFilter
): SearchResult

metadata_filter(
    folder?: string,
    tags?: string[],
    date_from?: string,
    date_to?: string,
    extension?: string,
    custom?: object
): NoteList
```

#### ナビゲーション系

```typescript
get_file_chunks(
    document_id: string,
    level?: string = "file"
): ChunkList

get_neighbor_chunks(
    chunk_id: string,
    before?: number = 1,
    after?: number = 1
): ChunkList

get_parent_chunk(chunk_id: string): Chunk | null  // Phase 2用
```

#### CRUD系

```typescript
add_note(
    title: string,
    content: string,
    folder?: string,
    tags?: string[]
): { document_id: string, file_path: string }

get_note(document_id: string): Note

update_note(
    document_id: string,
    content: string
): { success: boolean }

delete_note(
    document_id: string,
    permanent?: boolean = false
): { success: boolean, in_trash: boolean }

list_notes(
    folder?: string,
    limit?: number = 50,
    offset?: number = 0
): NoteList

list_folders(): string[]
```

**型定義:**

```typescript
interface SearchResult {
  results: ChunkResult[]
  context: SearchContext
}

interface ChunkResult {
  chunk_id: string
  document_id: string
  content: string
  score: number
  chunk_level: string
  chunk_index: number
  chunk_total: number
  heading_path?: string
  page_number?: number
  navigation: NavigationInfo
  metadata: object
}

interface NavigationInfo {
  file_path: string
  has_previous: boolean
  has_next: boolean
  previous_chunk_id?: string
  next_chunk_id?: string
  all_chunks_in_file: string[]
}

interface SearchContext {
  tool: string
  query: string
  embedding_model: string
  search_space: {
    total_chunks: number
    filtered_by_metadata: number
    filter_applied: object
  }
  results_summary: {
    count: number
    score_range: [number, number]
    avg_score: number
  }
  execution_time_ms: number
  suggestions_for_claude: string[]
}
```

### 9.3 REST API仕様（FastAPI）

**起動:** `clawtion api-serve --port 8080`

**自動生成ドキュメント:** `http://localhost:8080/docs`（Swagger UI）

**認証:** APIキー方式（`Authorization: Bearer <api-key>`）

**エンドポイント:**

```
# 検索
POST /search/semantic
POST /search/keyword
POST /search/hybrid
GET  /search/metadata-filter

# ナビゲーション
GET  /chunks/{document_id}/all
GET  /chunks/{chunk_id}/neighbors
GET  /chunks/{chunk_id}/parent

# CRUD
POST   /notes
GET    /notes/{document_id}
PUT    /notes/{document_id}
DELETE /notes/{document_id}
GET    /notes
GET    /folders

# キュー
GET  /queue/status
POST /queue/process
POST /queue/retry/{queue_id}

# システム
GET  /health
GET  /version
GET  /metrics
```

**OpenAPI 3.0仕様で完全に文書化される。FastAPIが自動生成。**

**REST API設計原則（2.4.3節の適用）:**

FastAPIのレスポンスモデルで統一フォーマットを強制する。

```python
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """全APIレスポンスの統一ラッパー。"""
    data: T
    meta: dict | None = None

class APIError(BaseModel):
    """全APIエラーの統一フォーマット。"""
    code: str           # "DOCUMENT_NOT_FOUND" 等
    message: str        # ユーザー向けメッセージ（i18n対応）
    details: dict | None = None

# 使用例
@app.get("/notes/{document_id}", response_model=APIResponse[Note])
async def get_note(document_id: UUID):
    note = await note_service.get(document_id)
    if not note:
        raise ClawtionAPIError(
            status_code=404,
            code="DOCUMENT_NOT_FOUND",
            message=t("api.errors.document_not_found"),
        )
    return APIResponse(data=note)
```

**全エンドポイントでバージョニングを適用:**

```
/api/v1/search/semantic
/api/v1/notes
/api/v1/queue/status
```

Phase 2以降でAPIの破壊的変更が必要になった場合、`/api/v2/`として新エンドポイントを追加し、`/api/v1/`は非推奨期間を設けて維持する。

### 9.4 UI仕様（Phase 3、概要のみ）

**技術:** Tauri + React + TipTap

**機能（Phase 3）:**
- ノート一覧（サイドバー）
- Markdownエディタ（リアルタイムプレビュー）
- 検索バー（hybrid_search内部呼び出し）
- バックグラウンドindexing状態表示
- 設定UI
- APIキー入力
- ゴミ箱操作

**Phase 1ではUIなし。** ユーザーは外部エディタ（VSCode、Obsidian等）でVaultを編集する。

---

## 10. Claude Code統合

### 10.1 全体像

3層構造でコンテキスト汚染を防ぐ：

```
[Claude Code メインエージェント]  ← ユーザーとの会話
        ↓ Skill検知 → Subagent委譲
[clawtion-knowledge サブエージェント]  ← 専用コンテキスト
        ↓ MCPツール呼び出し
[clawtion MCPサーバー]  ← 生のデータ操作
        ↓
[Postgres + pgvector DB]
```

### 10.2 サブエージェント定義

**ファイル:** `~/.claude/agents/clawtion-knowledge.md`（`clawtion init` で自動配置）

```markdown
---
name: clawtion-knowledge
description: |
  User's personal knowledge base search agent.
  Use when the user asks about their own notes, documents, past records,
  or anything stored in their clawtion vault.
  Examples: "what did I write about RAG?", "find my notes on X",
  "what do I know about Y?"
tools:
  - mcp__clawtion__semantic_search
  - mcp__clawtion__keyword_search
  - mcp__clawtion__hybrid_search
  - mcp__clawtion__metadata_filter
  - mcp__clawtion__get_file_chunks
  - mcp__clawtion__get_neighbor_chunks
  - mcp__clawtion__list_folders
  - mcp__clawtion__list_notes
  - mcp__clawtion__get_note
model: sonnet
memory: project
---

You are clawtion-knowledge, a specialized agent for searching the user's
personal knowledge base stored in their clawtion vault.

# Your Role

The main agent has delegated a knowledge retrieval task to you. Your job:
1. Understand what the user is looking for
2. Choose appropriate search strategy
3. Execute search using clawtion MCP tools
4. Return a clean, organized summary to the main agent

# Decision Framework

## Choose search method based on query type

- **Specific terms, names, exact phrases** → keyword_search first
- **Conceptual, abstract questions** → semantic_search
- **Mixed queries (most common)** → hybrid_search
- **Filtered by folder/tag/date** → metadata_filter + above

## Multi-step strategy

If first search returns few results or low scores:
1. Try alternative search method
2. Broaden query terms
3. Use list_folders to understand vault structure
4. Re-search with refined terms

## Result Synthesis

DO return to main agent:
- A concise summary of what was found
- Direct quotes only when essential
- File paths and chunk references for citation
- Structured info: "Found N notes across M files. Key themes: [...]"

DO NOT return to main agent:
- Raw search result JSON
- Diagnostic metadata (scores, embedding model info, execution time)
- Failed search attempts
- Full chunk contents unless the user explicitly needs them

# Output Format

## Summary
[2-3 sentence overview of findings]

## Key Findings
- [Finding 1] (source: `folder/file.md`)
- [Finding 2] (source: `folder/file.md`)

## Relevant Files
1. `path/to/file.md` - [brief description]
2. `path/to/file2.md` - [brief description]

## Suggested Next Steps
[If appropriate: "User might want to read X for full context"]
```

### 10.3 スキル定義

**ファイル:** `~/.claude/skills/clawtion-search/SKILL.md`

```markdown
---
name: clawtion-search
description: |
  User has a personal knowledge base in clawtion.
  When the user asks about their own notes, past writings, personal documents,
  or "what do I know about X", "what did I write about Y", "find my note on Z" -
  delegate to the clawtion-knowledge subagent rather than answering from
  general knowledge.
---

# clawtion Knowledge Search

The user has a personal knowledge base managed by clawtion (stored locally
with vector + keyword search capabilities).

## When to invoke clawtion-knowledge subagent

Trigger: any question that references the user's personal knowledge or notes:
- "what did I write about..."
- "find my notes on..."
- "what do I know about..."
- "search my notes for..."
- Reference to past discussions, learnings, or saved information
- Any time the user asks about their own thinking, decisions, or records

## How to invoke

Use the Task tool with subagent_type='clawtion-knowledge'. The subagent will:
1. Search the vault with appropriate strategy
2. Return organized results to you
3. Keep raw search noise out of your context

## What NOT to do

- Do NOT call clawtion MCP tools directly. Always delegate to the subagent.
- Do NOT try to answer from general knowledge if the question is about user's
  personal notes.
- Do NOT bypass the subagent even for "simple" lookups - the context isolation
  matters.
```

### 10.4 自動セットアップ（clawtion init）

**コマンド:** `clawtion init`

**実行内容:**

```
1. ようこそメッセージ表示

2. Vault パスの選択
   - デフォルト: ~/Documents/clawtion-vault
   - ユーザー入力可能

3. APIキーの入力
   - Gemini API key (必須)
   - OS keychainに保存（フォールバックで暗号化ファイル）

4. Docker Desktop チェック
   - 未インストールならエラー + インストールガイド表示
   - 起動していなければ自動起動を試みる

5. DB起動
   - docker-compose up -d
   - DB接続確認

6. Alembic マイグレーション実行
   - 初期スキーマ作成

7. Claude Code統合ファイル配置
   - ~/.claude/agents/clawtion-knowledge.md を作成
   - ~/.claude/skills/clawtion-search/SKILL.md を作成
   - 既存ファイルがある場合はバックアップ後上書き

8. MCP設定の自動更新
   - ~/.claude.json の mcpServers セクションに clawtion を追加
   - 既存設定をマージ（破壊しない）

9. Vault フォルダの初回スキャン
   - 既存の.md/.pdf/画像ファイルをキューに追加
   - "Background indexing will start. You can use Claude Code immediately."

10. サービスモード選択（オプション）
    - manual / scheduled / background から選択
    - スケジューラへの登録を実行

11. 完了メッセージ
    - "✓ clawtion is ready!"
    - "Try: ask Claude Code 'find my notes about X'"
```

### 10.5 アンインストール

**コマンド:** `clawtion uninstall`

**実行内容:**

```
1. 確認プロンプト
   "This will remove clawtion. Your notes (.md files) will NOT be deleted."

2. サービス停止
   - clawtion service uninstall (スケジューラから削除)
   - docker-compose down (DB停止)

3. Claude Code統合ファイル削除
   - ~/.claude/agents/clawtion-knowledge.md
   - ~/.claude/skills/clawtion-search/SKILL.md

4. MCP設定の更新
   - ~/.claude.json から clawtion セクションのみ削除
   - 他のMCPサーバー設定は保持

5. 確認
   "Delete database? [y/N]"
   - Yes: ~/.clawtion/pgdata/ 削除
   - No: 保持（再インストール時に再利用可）

6. 確認
   "Delete config and logs? [y/N]"
   - Yes: ~/.clawtion/ 削除（pgdata以外）
   - No: 保持

7. APIキー削除
   - OS keychainから削除

8. 完了メッセージ
```

### 10.6 コンテキスト分離戦略

**MCPツール側の実装:**

すべての検索ツールの戻り値を2つに分離：

```python
{
  "results": [...],       // メインの結果（必要最小限）
  "context": {            // 診断情報（subagentが解釈）
    ...
    "suggestions_for_claude": [...]
  }
}
```

**サブエージェントのプロンプトで明確に指示:**

「context フィールドは検索戦略の判断に使うが、メインエージェントへの応答には含めない」

**結果:**
- メインエージェントには整理されたサマリーのみ届く
- 検索失敗、リトライ、診断情報はsubagentで完結
- メインのコンテキストウィンドウが圧迫されない

---

## 11. ロギング・監視

### 11.1 3層ログ構造

#### 層1: ユーザー向け表示ログ

**出力先:** UI のステータスバー、CLIの標準出力

**例:**
- "Indexing 3 files... (1/3)"
- "Search complete: 5 results in 120ms"
- "Error: Invalid API key. Run 'clawtion config edit' to update."

**特徴:**
- 簡潔、人間が読める
- エラー時は対処法も含める
- 言語: i18nで翻訳済み

#### 層2: 開発者向け詳細ログ

**出力先:** `~/.clawtion/logs/clawtion.log`

**フォーマット:** 構造化JSON

**例:**
```json
{
  "timestamp": "2026-04-27T14:32:15.123Z",
  "level": "INFO",
  "logger": "clawtion.indexing",
  "event": "chunk_embedded",
  "data": {
    "document_id": "uuid",
    "chunk_id": "uuid",
    "chunk_level": "file",
    "tokens": 245,
    "embedding_model": "gemini-embedding-2-preview",
    "duration_ms": 412
  }
}
```

**ログ項目:**
- すべてのAPI呼び出し（Gemini、Claude）
  - 入力サイズ、出力サイズ、レイテンシ、エラー
  - APIキーは伏せる
- すべてのDB操作
  - クエリ、実行時間、結果件数
- ファイル監視イベント
- indexing処理（ファイルパス、チャンク数、所要時間）
- エラー時はスタックトレース全文

**ローテーション:**
- 日次ローテーション
- 30日後に自動削除
- gzip圧縮

#### 層3: Claude向けコンテキストログ

**出力先:** MCPツールの戻り値の `context` フィールド

**目的:** Claudeが検索戦略を判断する材料

**前述の `suggestions_for_claude` 仕様参照**

### 11.2 ログレベル設定

```yaml
logging:
  level: INFO              # DEBUG | INFO | WARN | ERROR
  file_path: ~/.clawtion/logs/
  rotation: daily
  retention_days: 30
  format: json             # json | text
  claude_context_verbosity: high  # low | medium | high
```

### 11.3 clawtion doctor

**コマンド:** `clawtion doctor`

**チェック項目:**

```
clawtion doctor
================

✓ Docker Desktop: running
✓ DB connection: ok (postgresql://localhost:5432/clawtion)
✓ DB schema version: 005 (latest)
✓ Gemini API key: valid
✓ Claude Code config: clawtion MCP server detected
✓ Subagent installed: ~/.claude/agents/clawtion-knowledge.md
✓ Skill installed: ~/.claude/skills/clawtion-search/SKILL.md
✓ Vault accessible: ~/Documents/notes (1234 files)
✓ Disk space: 12.5 GB free
⚠ Indexing queue: 5 pending, 0 failed
✓ Last successful indexing: 2 minutes ago
✓ Service mode: scheduled (hourly + on PC startup)

Overall: HEALTHY

Recent errors (last 24h): 0

Run 'clawtion logs --tail 50' for detailed logs.
```

**役割:** トラブル発生時の最初の手段。何が機能していて何が壊れているかを一目で把握。

### 11.4 メトリクス（Phase 2以降）

REST APIに `/metrics` エンドポイント追加：

```
total_documents: 1234
total_chunks: 5678
indexing_queue_pending: 5
indexing_queue_failed: 0
embedding_api_calls_today: 234
average_search_latency_ms: 145
db_size_mb: 234
```

Prometheus形式でも出力可能。

### 11.5 エラー処理の統一パターン

2.4.3節で定義したエラーレスポンスの統一フォーマットを、バックエンド内部のエラー処理パターンとして実装する。

**バックエンド側（コアロジック層）:**

コアロジック層では、ビジネスロジック固有の例外クラス階層を定義する。インターフェース層（CLI / MCP / REST API）がこれをキャッチし、各プロトコルに適した形式に変換する。

```python
class ClawtionError(Exception):
    """clawtionの全例外の基底クラス。"""
    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

class DocumentNotFoundError(ClawtionError):
    def __init__(self, document_id: str):
        super().__init__(
            code="DOCUMENT_NOT_FOUND",
            message=f"Document not found: {document_id}",
            details={"document_id": document_id},
        )

class EmbeddingError(ClawtionError):
    """Embedding API呼び出しの失敗。"""
    ...

class IndexingError(ClawtionError):
    """Indexing処理中のエラー。"""
    ...

class VaultError(ClawtionError):
    """Vault関連のエラー（ファイル不在、権限不足等）。"""
    ...
```

**インターフェース層での変換:**

| インターフェース | ClawtionError の変換先 |
|---|---|
| REST API | HTTPステータス + JSON `{ error: { code, message, details } }` |
| CLI | ユーザー向けメッセージ（i18n翻訳済み）+ 対処法ヒント |
| MCP Server | MCPプロトコルのエラーレスポンス |

```python
# REST API での統一エラーハンドラー
@app.exception_handler(ClawtionError)
async def clawtion_error_handler(request: Request, exc: ClawtionError):
    status_map = {
        "DOCUMENT_NOT_FOUND": 404,
        "VALIDATION_ERROR": 422,
        "EMBEDDING_API_ERROR": 502,
        "QUEUE_FULL": 429,
    }
    return JSONResponse(
        status_code=status_map.get(exc.code, 500),
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )
```

### 11.6 可観測性のロードマップ

Phase 1ではstructlogベースの構造化ログ（11.1〜11.3節）を基盤とする。Phase 2以降で可観測性の3本柱（Metrics、Logs、Traces）を段階的に拡充する。

**Phase 1（現行）:**
- Logs: structlogによる構造化JSONログ（11.2節）
- Metrics: `clawtion doctor`による簡易ヘルスチェック（11.3節）
- Traces: なし（単一プロセスのため不要）

**Phase 2以降の拡張方針:**
- Metrics: `/metrics`エンドポイント（11.4節）でPrometheus形式出力
- Traces: REST API → コアロジック → DB の呼び出しチェーンにリクエストIDを付与し、1リクエストの処理経路を追跡可能にする
- ツール: OpenTelemetry（OTel）のPython SDKを導入し、ベンダーニュートラルなテレメトリ収集基盤を構築する。これにより将来的なモニタリングツールの変更がコード変更なしで可能になる

**リクエストID（Phase 1から準備）:**

REST APIの全リクエストに一意のリクエストIDを付与し、ログに含める。Phase 1時点ではログ追跡のみに使用するが、Phase 2のトレーシング導入時にそのままtrace IDとして活用できる。

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

---

## 12. 国際化（i18n）

### 12.1 設計方針

**多言語対応を最初から組み込む。**

すべてのユーザー向け文字列を変数化し、言語別の辞書ファイルから読み込む。

### 12.2 翻訳ファイル構造

**場所:** `~/.clawtion/i18n/`（または配布物に同梱）

**フォーマット:** JSON（簡潔、編集しやすい）

```
i18n/
├── en.json
├── ja.json
└── (community contributions...)
```

**ファイル例（en.json）:**

```json
{
  "cli": {
    "init": {
      "welcome": "Welcome to clawtion!",
      "vault_prompt": "Where should your vault be located?",
      "vault_default": "Default: {path}",
      "api_key_prompt": "Enter your Gemini API key:",
      "api_key_saved": "API key saved securely.",
      "setup_complete": "✓ clawtion is ready!"
    },
    "indexing": {
      "queue_status": "{pending} pending, {processing} processing, {completed} completed",
      "indexing_file": "Indexing: {filename}",
      "complete": "Indexed {count} files in {duration}"
    },
    "errors": {
      "invalid_api_key": "Invalid API key. Run 'clawtion config edit' to update.",
      "db_connection_failed": "Cannot connect to database. Is Docker running?",
      "vault_not_found": "Vault folder not found: {path}"
    }
  },
  "ui": {
    "search": {
      "placeholder": "Search your notes...",
      "no_results": "No results found",
      "results_count": "{count} results"
    }
  }
}
```

**ファイル例（ja.json）:**

```json
{
  "cli": {
    "init": {
      "welcome": "clawtionへようこそ!",
      "vault_prompt": "Vaultをどこに配置しますか?",
      "vault_default": "デフォルト: {path}",
      "api_key_prompt": "Gemini APIキーを入力してください:",
      "api_key_saved": "APIキーを安全に保存しました。",
      "setup_complete": "✓ clawtionの準備ができました!"
    },
    "indexing": {
      "queue_status": "待機中: {pending}、処理中: {processing}、完了: {completed}",
      "indexing_file": "インデックス処理中: {filename}",
      "complete": "{count}件のファイルを{duration}で処理しました"
    },
    "errors": {
      "invalid_api_key": "APIキーが無効です。'clawtion config edit'で更新してください。",
      "db_connection_failed": "データベースに接続できません。Dockerは起動していますか?",
      "vault_not_found": "Vaultフォルダが見つかりません: {path}"
    }
  },
  "ui": {
    "search": {
      "placeholder": "ノートを検索...",
      "no_results": "結果が見つかりません",
      "results_count": "{count}件の結果"
    }
  }
}
```

### 12.3 実装

**ライブラリ:** Python標準の `gettext` または独自実装（軽量）

**使用例:**

```python
from clawtion.i18n import t

# どこからでも呼び出し可能
print(t("cli.init.welcome"))
print(t("cli.indexing.queue_status", pending=5, processing=1, completed=100))
```

**言語自動判定:**
1. 環境変数 `LANG` をチェック
2. なければOS設定をチェック
3. 対応言語がなければ英語フォールバック

**手動切り替え:**
```yaml
ui:
  language: ja  # auto | en | ja | ...
```

### 12.4 Phase別の対応言語

**Phase 1:**
- 英語（必須）
- 日本語（必須）
- i18n機構は最初から組み込み

**Phase 2以降:**
- コミュニティ翻訳の受け入れ
- フランス語、ドイツ語、中国語、韓国語など順次追加

### 12.5 翻訳の管理

**翻訳キーの変更:**
- 既存キーは原則削除しない
- 新キー追加 → 全言語ファイルに追加（未翻訳は英語にフォールバック）
- 古いキーの使用箇所を全て新キーに移行 → 古いキー削除

**翻訳の検証:**
- CIで全言語ファイルのキー一致をチェック
- 翻訳漏れがあれば警告（エラーにはしない、英語フォールバック）

---

## 13. 配布・運用

### 13.1 配布形態

**Phase 1:**
- **PyPIパッケージ**（`pip install clawtion`）
- pipxを推奨（独立した仮想環境で実行）

**Phase 3以降:**
- **Tauriデスクトップアプリ**（バイナリ配布）
- macOS: `.dmg`
- Windows: `.exe` インストーラ

### 13.2 サポートOS

**Phase 1で対応:**
- macOS 12+ (Apple Silicon / Intel)
- Windows 10/11

**Phase 2以降で検討:**
- Linux (Ubuntu 22.04+, Fedora 38+)

### 13.3 必要な依存

**ユーザー側で必要なもの:**
- Python 3.11以上
- Docker Desktop（pgvector運用のため）
- Gemini APIキー（Google AI Studioで無料取得可能）
- Claude Code（オプション、AI機能を使う場合）

**自動インストールされるもの:**
- すべてのPythonパッケージ（pip install時）
- Postgresイメージ（docker-compose初回起動時）

### 13.4 インストール手順（ユーザー視点）

```bash
# ステップ1: pipxインストール（未導入の場合）
brew install pipx        # macOS
pip install --user pipx  # Windows
pipx ensurepath

# ステップ2: clawtion インストール
pipx install clawtion

# ステップ3: 初期セットアップ
clawtion init
# → Vault パス選択、APIキー入力、Docker起動、DB初期化、Claude Code統合
# → 完了

# ステップ4: 動作確認
clawtion doctor

# ステップ5: 使用開始
# Claude Codeで「what's in my notes about X?」と聞く
# または: clawtion search "..."
```

### 13.5 アップデート

```bash
pipx upgrade clawtion
clawtion start  # マイグレーション自動実行
```

**マイグレーション自動化:**
- 起動時にAlembicバージョンチェック
- 未適用マイグレーションがあれば自動実行
- 大きな変更（破壊的変更）はバージョン番号で警告

### 13.6 APIキー管理

**保存先（優先順位順）:**

1. **OS Keychain（推奨）**
   - macOS: Keychain Access
   - Windows: Credential Manager
   - ライブラリ: `keyring` (Python)

2. **暗号化ファイル（フォールバック）**
   - `~/.clawtion/secrets.enc`
   - 暗号化キーはOSのユーザー認証情報から導出
   - ライブラリ: `cryptography`

3. **環境変数（CI/CD用）**
   - `CLAWTION_GEMINI_API_KEY`
   - 環境変数があれば最優先

**入力方法:**

**初回:** `clawtion init` 中の対話プロンプト

**変更:** `clawtion config set-key gemini`（プロンプト）

**Phase 3 UI:** 設定画面のテキストフィールド（`type=password`、保存ボタンで暗号化保存）

### 13.7 バックアップ戦略

**ユーザーデータの保護:**

**プライマリデータ（.mdファイル）:**
- ユーザーの責任（Git, Time Machine, Dropbox等）
- clawtionは触らない

**DBバックアップ（オプション）:**
```bash
clawtion backup create        # 手動バックアップ
clawtion backup list
clawtion backup restore <id>
```

- pg_dumpでDBダンプ作成
- `~/.clawtion/backups/` に保存
- 設定で自動バックアップ（毎日、最大7日分）

**重要:** .mdファイルが本体なので、最悪DB全損してもreindexで復元可能

---

## 14. 開発フェーズ

### 14.1 Phase 0: 基盤構築（1-2週間）

**ゴール:** 開発環境が整い、最小のend-to-endテストが通る

**タスク:**
- リポジトリ初期化（GitHub、MIT LICENSE、README）
- プロジェクト構造（`src/clawtion/`, `tests/`, `alembic/`, etc.）
- pyproject.toml + 依存定義
- docker-compose.yml（Postgres + pgvector）
- 初期Alembicマイグレーション（documents, document_chunks, indexing_queue, trash, vault_settings）
- 基本CLI（`clawtion --version`, `clawtion start/stop`）
- GitHub Actions CI（lint, type check, basic tests）

**成果物:**
- `clawtion start` でDB起動 → `clawtion stop` で停止
- 空のテーブルが作成されている

### 14.2 Phase 1: コア機能（4-6週間）

**ゴール:** Claude Codeから使える「AIナレッジベース」として完成

**タスク:**

**14.2.1 IndexingService**
- ファイル監視（watchdog）
- file粒度のチャンキング（1ファイル1チャンク、大きいファイルは見出し分割fallback）
- Gemini Embedding 2クライアント（task_type、Batch API、エラーハンドリング）
- content_hashによる差分更新
- チャンク単位のhash dedup
- indexing_queue管理
- 中断・再開機構（スナップショット方式）
- スケジューラ統合（PC起動時、1時間ごと）
- ファイル形式対応（.md, .pdf, 画像）

**14.2.2 SearchService**
- semantic_search
- keyword_search
- hybrid_search（RRF）
- metadata_filter
- navigation情報の生成
- suggestions_for_claudeの生成

**14.2.3 NoteService**
- CRUD操作
- ゴミ箱管理
- 自動パージ

**14.2.4 インターフェース層**
- CLI完全実装
- MCPサーバー実装
- REST API実装（FastAPI）

**14.2.5 Claude Code統合**
- subagent定義ファイル
- skill定義ファイル
- `clawtion init` 自動セットアップ
- `clawtion uninstall`

**14.2.6 ロギング**
- 3層ログ構造
- structlog統合
- `clawtion logs`, `clawtion doctor`

**14.2.7 i18n**
- en.json, ja.json
- 翻訳機構

**14.2.8 テスト**
- 単体テスト（コアロジック）
- 統合テスト（DB含む）
- E2Eテスト（CLI〜DB）

**14.2.9 ドキュメント**
- README
- Quick Start guide
- CLI reference
- MCP tools reference
- Architecture overview

**成果物:**
- `pip install clawtion` でインストール可能
- `clawtion init` で5分でセットアップ完了
- Claude Codeから「私のノートのRAGについて教えて」で検索が動く

### 14.3 Phase 2: 拡張機能（2-3週間）

**タスク:**

**14.3.1 Multi-resolution chunking**
- coarse粒度のチャンキング実装
- fine粒度のチャンキング実装
- 設定で粒度ごとON/OFF
- 既存ファイルに対する遡及indexing

**14.3.2 検索の粒度別対応**
- granularity パラメータ
- 結果の粒度別表示
- get_parent_chunkツール

**14.3.3 マルチVault対応**
- 複数Vaultの登録・切り替え
- Vault間の独立性

**14.3.4 マルチモデル対応**
- OpenAI Embedding対応
- ローカルモデル（Ollama）対応

**14.3.5 GraphRAG（オプション）**
- entitiesテーブル、relationsテーブル追加
- LLMによるEntity/Relation抽出
- graph_searchツール
- SQL再帰CTEによるトラバース

**14.3.6 Anthropic Contextual Retrieval（オプション）**
- Claude Haikuによるチャンクコンテキスト生成
- prompt cachingでコスト削減

**14.3.7 音声・動画対応**
- .mp3, .m4a, .mp4, .mov のindexing
- 長尺ファイルのチャンク分割

### 14.4 Phase 3: UIアプリ（4-6週間）

**タスク:**
- Tauri環境構築
- Reactフロントエンド
- TipTapエディタ統合
- ノート一覧・検索・編集UI
- 設定UI
- バックグラウンドindexing状態表示
- macOS/Windows ビルド・配布

### 14.5 Phase 4: 高度な機能（継続的）

**候補:**
- Reranking（Cohere Rerank等）
- セマンティックチャンキング（オプション）
- バージョン履歴
- Obsidian Plugin互換
- VS Code Extension
- ブラウザ拡張（Web記事の取り込み）

---

## 15. 設定ファイル仕様

### 15.1 設定の優先順位

1. 環境変数（最優先）
2. Vault固有設定（`<vault>/.clawtion/config.yaml`）
3. グローバル設定（`~/.clawtion/config.yaml`）
4. デフォルト値

### 15.2 完全リファレンス

**`~/.clawtion/config.yaml` のサンプル（全項目）:**

```yaml
# ===== Vault設定 =====
vault:
  path: ~/Documents/clawtion-vault
  watch_folders:
    - "."  # Vault全体を監視（デフォルト）
  exclude_folders:
    - ".trash"
    - "drafts"  # 下書きフォルダはindexしない
    - "private"

# ===== UI言語 =====
ui:
  language: auto  # auto | en | ja

# ===== Embedding設定 =====
embedding:
  provider: gemini
  model: gemini-embedding-2-preview
  output_dimensionality: 768  # 768 | 1536 | 3072

  task_type:
    document: RETRIEVAL_DOCUMENT
    query: RETRIEVAL_QUERY
  use_manual_prefix_fallback: true

  use_batch_api: true
  batch_threshold: 100      # 100チャンク超で自動Batch化
  batch_max_wait_hours: 24

  retry:
    max_attempts: 5
    initial_wait_seconds: 4
    max_wait_seconds: 60

# ===== チャンキング設定 =====
chunking:
  multi_resolution:
    enabled: false  # Phase 1ではfalse、Phase 2でtrueに

  levels:
    file:
      enabled: true
      max_tokens: 1500

    coarse:
      enabled: false  # Phase 2で有効化
      strategy: heading-based
      target_tokens: 800
      max_tokens: 1500
      merge_short_sections: true

    fine:
      enabled: false  # Phase 2で有効化
      strategy: sentence-based
      target_tokens: 100
      respect_paragraph_boundary: true

  preserve:
    code_blocks: true
    tables: true
    list_items: true

  language_detection: auto
  fallback_language: ja

  context_format: "folder: {folder_path} | file: {title} | section: {heading_path} | text: {content}"

# ===== Indexing設定 =====
indexing:
  triggers:
    on_pc_startup:
      enabled: true
    hourly_check:
      enabled: true
      interval_minutes: 60
    on_app_open:
      enabled: true

  worker:
    max_concurrent_jobs: 4
    queue_polling_interval_seconds: 5

  snapshot:
    enabled: true  # UIブロック回避のため常にON

# ===== ゴミ箱設定 =====
trash:
  enabled: true
  auto_purge_after_days: 7

# ===== ロギング設定 =====
logging:
  level: INFO  # DEBUG | INFO | WARN | ERROR
  file_path: ~/.clawtion/logs/
  rotation: daily
  retention_days: 30
  format: json
  claude_context_verbosity: high  # low | medium | high

# ===== サービス設定 =====
service:
  mode: manual  # manual | scheduled | background

# ===== バックアップ設定 =====
backup:
  enabled: false
  schedule: daily
  retention_days: 7
  path: ~/.clawtion/backups/

# ===== Phase 2以降のオプション機能 =====
graphrag:
  enabled: false
  llm_model: claude-haiku-4-5
  extract_on_index: true

contextual_retrieval:
  enabled: false
  llm_model: claude-haiku-4-5
  use_prompt_caching: true
```

### 15.3 環境変数

| 変数 | 説明 |
|---|---|
| `CLAWTION_VAULT` | Vaultパス（設定ファイルより優先） |
| `CLAWTION_DB_URL` | DB接続URL |
| `CLAWTION_GEMINI_API_KEY` | Gemini APIキー |
| `CLAWTION_CLAUDE_API_KEY` | Claude APIキー（Phase 2のCR用） |
| `CLAWTION_LOG_LEVEL` | ログレベル |
| `CLAWTION_CONFIG` | カスタム設定ファイルパス |

### 15.4 設定編集

**CLI:**
```bash
clawtion config              # 現在の設定を表示
clawtion config edit         # $EDITORで開く
clawtion config get vault.path
clawtion config set vault.path /new/path
clawtion config set-key gemini  # APIキー設定
```

---

## 16. テスト戦略

### 16.1 テストレベル

#### 単体テスト（Unit Tests）

**対象:** コアロジック層の各クラス・関数

**ツール:** pytest

**カバレッジ目標:** 80%以上

**例:**
```python
# tests/unit/test_chunker.py
def test_file_level_chunk_within_limit():
    content = "短いノート。" * 100  # 約1000トークン
    chunks = chunk_file_level(content, max_tokens=1500)
    assert chunks is not None
    assert chunks.chunk_index == 0
    assert chunks.chunk_total == 1

def test_file_level_chunk_exceeds_limit():
    content = "長いノート。" * 1000  # 約10000トークン
    chunks = chunk_file_level(content, max_tokens=1500)
    assert chunks is None  # スキップされる
```

#### 統合テスト（Integration Tests）

**対象:** 複数コンポーネントの連携、特にDBが絡む処理

**ツール:** pytest + testcontainers（テスト用Postgresを自動起動）

**例:**
```python
# tests/integration/test_indexing_pipeline.py
@pytest.fixture
def db_container():
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        run_migrations(pg.connection_url)
        yield pg

def test_full_indexing_flow(db_container, sample_md_file):
    service = IndexingService(db_container.connection_url)
    service.index_file(sample_md_file)

    # DBにチャンクが作成されたか確認
    chunks = db.query("SELECT * FROM document_chunks WHERE file_path = %s", sample_md_file)
    assert len(chunks) > 0
    assert chunks[0].embedding is not None
```

#### E2Eテスト（End-to-End Tests）

**対象:** CLI/MCP/REST APIのインターフェース全体

**ツール:** pytest + subprocess + Docker

**例:**
```python
def test_cli_search_after_index():
    # Vaultに.mdファイルを配置
    create_test_vault()

    # clawtion init
    subprocess.run(["clawtion", "init", "--vault", TEST_VAULT, "--non-interactive"])

    # clawtion index
    subprocess.run(["clawtion", "index", TEST_VAULT])

    # 検索
    result = subprocess.run(
        ["clawtion", "search", "テストクエリ"],
        capture_output=True,
        text=True
    )
    assert "テストファイル.md" in result.stdout
```

### 16.2 CI/CD（GitHub Actions）

**ファイル:** `.github/workflows/ci.yml`

**実行内容:**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install ruff black mypy
      - run: ruff check src/ tests/
      - run: black --check src/ tests/
      - run: mypy src/

  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ['3.11', '3.12', '3.13']
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit
      - run: pytest tests/integration

  e2e:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d
      - run: pytest tests/e2e
```

**ブランチ保護:**
- `main` への直接push禁止
- PR必須、CI通過必須
- レビュー1人以上承認

### 16.3 リリース前テスト

**手動チェックリスト:**

- [ ] `pipx install clawtion` でクリーンインストール成功
- [ ] `clawtion init` で対話セットアップ完了
- [ ] Claude Codeが「私のノートのXについて」で検索成功
- [ ] 100ファイル一括indexing成功
- [ ] indexing中のアプリ強制終了 → 再起動 → 続きから再開
- [ ] ファイル削除 → ゴミ箱移動 → 復元
- [ ] APIキー無効時のエラーメッセージ確認
- [ ] `clawtion uninstall` で完全削除
- [ ] macOS / Windows 両方で動作確認

### 16.4 パフォーマンステスト

**ベンチマーク項目:**

- 1,000チャンクの初回indexing時間
- 10,000チャンクの検索レイテンシ
- メモリ使用量（idle / active）
- DB容量増加率

**目標値（Phase 1）:**
- 100ファイル（平均1500トークン）のindexing: 10分以内（Batch API使用）
- 検索レイテンシ: p95 < 200ms（10,000チャンク規模）
- アイドル時メモリ: < 200MB
- アクティブ時メモリ: < 1GB

### 16.5 型安全性の強制（2.4.4節の実施）

**mypy設定（pyproject.toml）:**

```toml
[tool.mypy]
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false  # テストコードは緩和
```

**ruff設定（pyproject.toml）:**

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "RUF",  # ruff-specific rules
]
```

**pre-commitフック（.pre-commit-config.yaml）:**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        args: [--strict, src/]
        additional_dependencies: [pydantic, ...]
```

### 16.6 AI生成コードのレビューチェックリスト

Claude Code等でコード生成した場合、以下の観点でレビューする。2.4.5節のVibe & Verifyワークフローの具体的なチェック項目である。

**構造:**
- [ ] 1クラス200行以内、1関数50行以内を守っているか
- [ ] SOLID原則に違反していないか（特にSingle Responsibility）
- [ ] 依存関係がコンストラクタで注入されているか（ハードコードされていないか）
- [ ] 合成（Composition）を使っているか（不要な継承階層がないか）

**型安全性:**
- [ ] すべての関数・メソッドに型アノテーションがあるか
- [ ] `Any`型が使われていないか
- [ ] `mypy --strict`が通るか
- [ ] Pydanticモデルでリクエスト/レスポンスが定義されているか

**エラー処理:**
- [ ] `ClawtionError`階層の例外クラスを使っているか
- [ ] bare `except:`や`except Exception`で握りつぶしていないか
- [ ] エラー時のログ出力が構造化されているか

**テスト:**
- [ ] 生成されたコードに対応するテストが存在するか
- [ ] テストがビジネスロジックを検証しているか（実装の詳細ではなく）
- [ ] モックが適切に使われているか（DBやAPI呼び出しの分離）

---

## 17. 将来の拡張

### 17.1 Multi-resolution chunking詳細（Phase 2）

設計はPhase 1から準備済み（`chunk_level`カラム、`parent_chunk_id`カラム）。

**有効化フロー:**
```bash
clawtion config set chunking.multi_resolution.enabled true
clawtion config set chunking.levels.coarse.enabled true
clawtion config set chunking.levels.fine.enabled true
clawtion reindex --confirm  # 全件再indexing
```

**3粒度同時検索:**
```python
semantic_search(query="...", granularity="all")
# 戻り値: {"results_by_granularity": {"file": [...], "coarse": [...], "fine": [...]}}
```

### 17.2 GraphRAG詳細（Phase 2）

**追加テーブル:**
```sql
CREATE TABLE entities (
    entity_id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    entity_type VARCHAR(50),
    description TEXT,
    embedding vector(768),
    UNIQUE (name, entity_type)
);

CREATE TABLE relations (
    relation_id UUID PRIMARY KEY,
    source_entity_id UUID REFERENCES entities,
    target_entity_id UUID REFERENCES entities,
    relation_type VARCHAR(100),
    weight FLOAT,
    source_chunk_id UUID REFERENCES document_chunks
);
```

**Entity抽出:** Claude Haikuでチャンクごとに自動抽出（indexing時）

**graph_searchツール:**
```python
graph_search(
    starting_entity: str,
    max_hops: int = 2,
    relation_types: List[str] = None
)
# SQL再帰CTEで関連エンティティをN-hopトラバース
```

### 17.3 Anthropic Contextual Retrieval（Phase 2）

**仕組み:**
- 各チャンクに対してClaude Haikuで「このチャンクは文書のどこに位置するか」のコンテキストを生成
- そのコンテキストをチャンクに前置してembedding
- Anthropic公式: retrieval failure rate 49%削減

**コスト最適化:**
- prompt cachingで87%コスト削減
- 1000ドキュメントあたり約$12

**有効化:**
```yaml
contextual_retrieval:
  enabled: true
```

### 17.4 マルチモーダル拡張（Phase 1〜Phase 2）

**Phase 1で対応:**
- .md, .txt: テキストembedding
- .pdf: ページ単位でGemini PDF embedding
- .png, .jpg, .jpeg, .webp: 画像embedding

**Phase 2で追加:**
- .mp3, .m4a: 音声embedding（80秒制限、超過は分割）
- .mp4, .mov: 動画embedding（120秒制限、超過は分割）

**Phase 3で検討:**
- Whisper連携（長尺音声の文字起こし）
- 動画キーフレーム抽出 + キャプション生成

### 17.5 Obsidian Plugin（Phase 4）

ObsidianからclawtionのRESTAPIを呼ぶプラグイン。

機能：
- Obsidian内で「AI search」コマンド
- バックリンクの強化（embedding類似度ベース）
- ノート間の意外な繋がりを表示

### 17.6 Reranking（Phase 4）

**ライブラリ:** Cohere Rerank または BGE Reranker

**動作:**
1. hybrid_searchでtop 30取得
2. Rerankerでクエリと各チャンクを再評価
3. top 10に絞って返す

**期待効果:** Anthropic公式実験で失敗率67%削減

### 17.7 マルチフォーマットローダー（Phase 2）

PowerPoint、HTML、Word、Excel等の多様なファイル形式をVaultに取り込み可能にする。

**方針:**
- LangChain Unstructured Loader（または同等ライブラリ）を活用し、各形式からテキスト・構造情報を抽出
- 対応予定形式: `.pptx`, `.docx`, `.xlsx`, `.html`, `.epub`, `.rst`, `.csv`, `.json`
- 抽出後は既存のチャンキング・embeddingパイプラインに統合（FileProcessorプロトコル（2.4.2節）のサブクラスとして実装）
- 元ファイルはVaultにそのまま保存し、抽出テキストをindexingする

### 17.8 Gitローダー（Phase 2）

GitHubリポジトリからファイルを読み込み、ナレッジベースに取り込む。

**想定ユースケース:**
- 自分のリポジトリのREADME、ドキュメント、コメント付きコードをナレッジとして蓄積
- 参照用OSSリポジトリのドキュメントを取り込み

**方針:**
- `git clone --depth 1`（shallow clone）でローカルにクローン後、既存のファイル監視・indexingパイプラインに乗せる
- 対象ファイルのフィルタリング: `.gitignore`準拠 + 拡張子フィルタ（デフォルトで`.md`, `.txt`, `.rst`, `.py`, `.ts`等のテキスト系のみ）
- 定期的な`git pull`で差分更新（スケジューラ統合）
- CLIコマンド: `clawtion git add <repo-url> [--branch main] [--path docs/]`
- メタデータにリポジトリURL、ブランチ、コミットハッシュを付与し、検索結果からソースを辿れるようにする

### 17.9 ノート編集MCPツール（Phase 2）

Claude Codeがノートの特定箇所を検索・特定し、情報を更新できるMCPツール。

**追加MCPツール:**

```typescript
update_note_section(
    document_id: string,
    target_heading: string,       // 更新対象の見出し（heading_pathで特定）
    new_content: string,          // 新しい内容
    match_context?: string        // 対象箇所を特定するための周辺テキスト（見出しが重複する場合）
): { success: boolean, updated_section: string, diff_preview: string }

append_to_note(
    document_id: string,
    content: string,
    position?: "end" | "after_heading",
    target_heading?: string
): { success: boolean }
```

**動作フロー:**
1. Claude Codeが検索で関連ノートを発見
2. `get_file_chunks`で対象ファイルの構造を把握
3. `update_note_section`で特定箇所のみ更新
4. 更新前のdiffプレビューをユーザーに提示し、確認後に書き込み

### 17.10 矛盾検出・解決機構（Phase 3）

Vault内で相反する情報が発見された場合に、ユーザーに確認を求める仕組み。

**検出タイミング:**
- 検索結果に同一トピックで矛盾する記述が含まれる場合（サブエージェントが判定）
- ノート更新時に、既存の他ノートと矛盾が生じる場合

**サブエージェントのSkillに追加する判定ルール:**
- 同一エンティティについて異なる属性値が記述されている（例: 「Xのバージョンは3.0」vs「Xのバージョンは2.8」）
- 時系列的に古い情報と新しい情報が混在している
- 明示的に否定・訂正している記述がある

**ユーザーへの提示フォーマット:**

```
⚠ 矛盾する情報が見つかりました:

  1. tech/rag.md (更新: 2026-03-15):
     「RRFの定数k=60が最適」

  2. tech/search-tuning.md (更新: 2026-04-20):
     「k=40に変更したところ精度が向上した」

→ どちらを正とすべきですか？ または両方保持しますか？
```

**解決アクション:**
- ユーザーが一方を選択 → 古い方に「※ 訂正済み。最新情報は [リンク] を参照」を自動追記
- 両方保持 → メタデータに`conflicting_with: [document_id]`を付与し、今後の検索で注記表示

### 17.11 高度な検索戦略（Skill拡充）（Phase 2）

サブエージェント（clawtion-knowledge）のSkill定義を拡充し、検索の質を大幅に向上させる。

**追加する検索戦略:**

**HyDE（Hypothetical Document Embeddings）:**
- ユーザーのクエリに対して、LLMが「理想的な回答ドキュメント」を仮説的に生成
- その仮説ドキュメントをembeddingしてベクトル検索に使用
- ユーザーの短い質問よりも、仮説ドキュメントの方がVault内の関連チャンクとベクトル空間上で近くなるため、検索精度が向上する

**クエリ精査（Query Refinement）:**
- ユーザーの曖昧なクエリをそのまま検索せず、LLMが「何を探しているのか」を言語化・分解してから検索する
- 例: 「RAGのあれ」→ LLMが「RAGのチャンキング戦略」「RAGの検索手法比較」等に分解し、複数クエリで検索

**再帰的検索（Iterative Retrieval）:**
- 初回検索の結果が不十分（スコアが低い、件数が少ない）場合、LLMが自動的にクエリを修正して再検索
- 最大3回まで再帰し、十分な結果が得られるまで繰り返す
- 各イテレーションの判断基準: `suggestions_for_claude`（8.4節）の情報を活用

**Skill定義への追記（`clawtion-knowledge.md`に追加）:**

```markdown
## Advanced Search Strategies

### Query Preparation (ALWAYS do this first)
Before searching, analyze the user's query:
1. Identify the core information need
2. Extract key entities and concepts
3. Determine if the query is specific (→ keyword_search) or conceptual (→ semantic_search)
4. If ambiguous, decompose into 2-3 sub-queries

### HyDE Strategy (for conceptual/abstract queries)
When the query is abstract or the user is asking "what do I know about X":
1. Generate a hypothetical 2-3 sentence passage that would answer the query
2. Use that passage as the search query for semantic_search
3. Compare results with a direct query search and merge

### Iterative Refinement
If search results are insufficient (avg_score < 0.5 or count < 2):
1. Analyze WHY results are poor (wrong terms? too specific? wrong search method?)
2. Reformulate query based on analysis
3. Try alternative search method
4. Use list_folders to understand vault structure and narrow scope
5. Maximum 3 iterations before reporting to user

### Multi-Query Fusion
For complex questions, search with multiple reformulations:
1. Original query
2. Synonym-expanded query
3. HyDE-generated query
Merge results using RRF across all queries
```

### 17.12 名前空間（Namespace / Collection）（Phase 2）

1つのVault内で複数の検索空間（名前空間）を構築し、検索範囲をピンポイントで指定できるようにする。

**既存のマルチVault（14.3.3節）との違い:**
- マルチVault: 完全に独立したDB・ファイルシステム。プロジェクト単位の大きな分離
- 名前空間: 1つのVault・1つのDB内での論理的な分割。テーマ・分野単位の軽い分離

**データモデル:**

```sql
CREATE TABLE namespaces (
    namespace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,    -- 例: "machine-learning", "cooking", "work"
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- document_chunks に namespace_id を追加
ALTER TABLE document_chunks ADD COLUMN namespace_id UUID REFERENCES namespaces;
CREATE INDEX idx_chunks_namespace ON document_chunks(namespace_id);
```

**MCPツール拡張:**

```typescript
// 名前空間管理
create_namespace(name: string, description?: string): Namespace
list_namespaces(): Namespace[]
assign_to_namespace(document_id: string, namespace_id: string): void

// 検索時の名前空間指定
semantic_search(
    query: string,
    namespace?: string | string[],  // 指定なしで全空間検索
    ...
): SearchResult
```

**ユースケース例:**
- `clawtion namespace create "machine-learning" --description "ML関連の学習ノート"`
- `clawtion search --namespace machine-learning "transformerの仕組み"`
- Claude Code: `semantic_search(query="attention mechanism", namespace="machine-learning")`
- 複数指定: `semantic_search(query="...", namespace=["ml", "math"])` で横断検索

---

## 18. 付録

### 18.1 用語集

| 用語 | 意味 |
|---|---|
| Vault | ユーザーの.mdファイルが入っているフォルダ |
| chunk | 文書を分割した1単位 |
| chunk_level | チャンクの粒度（file / coarse / fine） |
| embedding | テキスト・画像等を数値ベクトルに変換したもの |
| HNSW | 近似最近傍探索アルゴリズム（pgvectorの高速インデックス） |
| BM25 | キーワード検索の標準的なランキングアルゴリズム |
| RRF | Reciprocal Rank Fusion、複数のランキングを融合する手法 |
| MCP | Model Context Protocol、Claude Codeとツール連携のプロトコル |
| MRL | Matryoshka Representation Learning、次元数を可変にする埋め込み技術 |
| Subagent | Claude Codeから委譲される専用コンテキストのエージェント |
| Skill | Claude Codeで自動発動する指示テンプレート |
| Batch API | Geminiの非同期一括処理API（コスト50%減） |

### 18.2 参考文献・一次情報

**Gemini Embedding 2:**
- https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-embedding-2/
- https://ai.google.dev/gemini-api/docs/embeddings
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/embedding-2

**pgvector:**
- https://github.com/pgvector/pgvector

**LlamaIndex:**
- https://docs.llamaindex.ai/

**Claude Code:**
- https://code.claude.com/docs/en/sub-agents
- https://platform.claude.com/docs/en/agent-sdk/skills

**チャンキング研究:**
- Chroma Research: "Evaluating Chunking Strategies"
- arXiv:2410.13070 (Vectara, NAACL 2025)
- arXiv "Chunk Twice, Embed Once" (2025)
- Anthropic Contextual Retrieval: https://www.anthropic.com/news/contextual-retrieval

**設計原則（セクション2.4の根拠）:**
- OpenAPI Initiative: https://www.openapis.org/
- Postman State of the API Report 2025: https://www.postman.com/state-of-api/
- Martin, Robert C. "Clean Architecture" (2017) — SOLID原則、Dependency Inversion
- Gamma et al. "Design Patterns" (1994) — Composition over Inheritance
- OpenTelemetry: https://opentelemetry.io/docs/

### 18.3 ライセンス

clawtion本体: **MIT License**

依存ライブラリのライセンス（主要なもの）:
- PostgreSQL: PostgreSQL License
- pgvector: PostgreSQL License
- LlamaIndex: MIT
- FastAPI: MIT
- Click: BSD-3-Clause
- watchdog: Apache 2.0
- pysbd: MIT
- structlog: Apache 2.0 / MIT

すべてMIT配布と互換。

### 18.4 ディレクトリ構造（プロジェクト本体）

```
clawtion/
├── README.md
├── LICENSE
├── pyproject.toml
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── ci.yml
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── src/
│   └── clawtion/
│       ├── __init__.py
│       ├── __main__.py
│       ├── core/
│       │   ├── indexing/
│       │   │   ├── service.py
│       │   │   ├── chunker.py
│       │   │   ├── watcher.py
│       │   │   ├── queue.py
│       │   │   └── snapshot.py
│       │   ├── search/
│       │   │   ├── service.py
│       │   │   ├── semantic.py
│       │   │   ├── keyword.py
│       │   │   ├── hybrid.py
│       │   │   └── filter.py
│       │   ├── note/
│       │   │   └── service.py
│       │   ├── embedding/
│       │   │   ├── client.py
│       │   │   ├── gemini.py
│       │   │   └── batch.py
│       │   ├── trash/
│       │   │   └── service.py
│       │   └── db/
│       │       ├── connection.py
│       │       ├── models.py
│       │       └── migrations.py
│       ├── interfaces/
│       │   ├── cli/
│       │   │   ├── main.py
│       │   │   ├── init.py
│       │   │   ├── service.py
│       │   │   ├── index.py
│       │   │   ├── search.py
│       │   │   ├── note.py
│       │   │   ├── trash.py
│       │   │   ├── doctor.py
│       │   │   └── config.py
│       │   ├── mcp/
│       │   │   ├── server.py
│       │   │   └── tools.py
│       │   └── api/
│       │       ├── app.py
│       │       └── routes/
│       │           ├── search.py
│       │           ├── notes.py
│       │           └── queue.py
│       ├── claude_integration/
│       │   ├── installer.py
│       │   └── templates/
│       │       ├── subagent.md
│       │       └── skill.md
│       ├── i18n/
│       │   ├── translator.py
│       │   └── locales/
│       │       ├── en.json
│       │       └── ja.json
│       ├── config/
│       │   ├── loader.py
│       │   ├── secrets.py
│       │   └── defaults.py
│       └── utils/
│           ├── logging.py
│           ├── tokens.py
│           ├── language.py
│           └── retry.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── docs/
    ├── architecture.md
    ├── quickstart.md
    ├── cli-reference.md
    ├── mcp-reference.md
    └── api-reference.md
```

### 18.5 リスクと緩和策

| リスク | 影響度 | 緩和策 |
|---|---|---|
| Gemini Embedding 2 preview仕様変更 | 高 | task_typeフォールバック実装、001モデルへの切り替え可能設計 |
| Docker Desktop有償化拡大 | 中 | Podman/Rancher Desktopなど代替を検討 |
| pgvector スケール限界（1億超） | 低 | Phase 1ターゲットでは到達せず。将来Qdrant/Milvus移行可能な抽象化 |
| Claude Code APIの破壊的変更 | 中 | 公式SDKを使用、変更時はサブエージェント定義を更新 |
| ユーザーの.mdファイル破損 | 高 | clawtionは読み取り基本、書き込みは限定的、バックアップ推奨 |
| APIキー漏洩 | 高 | OS keychain使用、ログにキーを書かない、CI環境変数でマスク |

### 18.6 開発者向けクイックスタート

```bash
# リポジトリ取得
git clone https://github.com/yourusername/clawtion.git
cd clawtion

# 開発環境セットアップ
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# DB起動
docker compose up -d

# マイグレーション
alembic upgrade head

# テスト
pytest tests/unit
pytest tests/integration

# ローカルでCLI動作確認
clawtion --help

# コミット前チェック
ruff check src/ tests/
black src/ tests/
mypy src/
```

### 18.7 コントリビュートガイドライン（OSSとして）

**Issue:**
- バグ報告: 再現手順、期待動作、実際の動作、環境（OS、Pythonバージョン、clawtionバージョン）
- 機能要望: 動機、ユースケース、提案する解決策

**Pull Request:**
- Issue連携必須（Issue番号をPR説明に記載）
- テスト追加必須
- ドキュメント更新必須
- コミットメッセージは Conventional Commits に従う（feat:, fix:, docs:, etc.）

**コードレビュー:**
- 1人以上の承認必須
- CI通過必須
- セキュリティ・プライバシーに関わる変更は2人以上の承認

**翻訳貢献:**
- `src/clawtion/i18n/locales/` に新言語ファイル追加
- 既存の en.json をベースにキーを翻訳
- PRで提出

---

## 文書終了

本設計書はclawtionプロジェクトの完全な設計仕様である。Phase 1の実装に必要なすべての要件、設計判断、技術選定、API仕様を含む。

実装者は本書を参照することで、プロジェクトの全体像を把握し、各コンポーネントの役割と相互作用を理解した上で、実装作業に取り掛かることができる。

不明点や追加の設計判断が必要になった場合は、本書のメンテナーに確認すること。

**メンテナー:** プロジェクトオーナー
**最終更新:** 2026年4月27日
**次回レビュー:** Phase 1実装開始前
