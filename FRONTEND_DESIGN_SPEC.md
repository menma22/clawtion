# clawtion フロントエンド設計指示書

**バージョン:** 1.0
**作成日:** 2026-05-05
**対象:** フロントエンドエンジニア（バックエンド知識不要で着手可能）

---

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [技術スタック](#2-技術スタック)
3. [バックエンドAPI完全仕様](#3-バックエンドapi完全仕様)
4. [TypeScript型定義](#4-typescript型定義)
5. [UI画面設計](#5-ui画面設計)
6. [ルーティング設計](#6-ルーティング設計)
7. [状態管理設計](#7-状態管理設計)
8. [コンポーネントツリー](#8-コンポーネントツリー)
9. [ユーザーフロー](#9-ユーザーフロー)
10. [開発環境セットアップ](#10-開発環境セットアップ)
11. [テスト戦略](#11-テスト戦略)
12. [配布・ビルド](#12-配布ビルド)

---

## 1. プロジェクト概要

### 1.1 clawtionとは

clawtionは「AIのためのナレッジベース」と「人間のためのメモ帳」を統合したローカル知識ベースアプリケーション。バックエンドはPython/FastAPIで構築済み。本ドキュメントはそのフロントエンド（デスクトップアプリ）の設計指示書である。

### 1.2 フロントエンドの役割

- ユーザーがMarkdownノートを作成・編集・削除できるGUI
- ナレッジベース内を検索できる検索UI
- Indexing（ファイルのベクトル化処理）の状態を表示
- 設定（APIキー、Vaultパス、Embeddingモデル等）の管理
- ゴミ箱管理（削除したノートの復元・完全削除）

### 1.3 バックエンドとの関係

```
┌──────────────────────┐
│  Tauriデスクトップアプリ │  ← 今回構築するもの
│  (React + TipTap)     │
└──────────┬───────────┘
           │ HTTP (REST API)
           │ http://127.0.0.1:8000/api/v1/
┌──────────▼───────────┐
│  FastAPIサーバー       │  ← 構築済み
│  (clawtion api-serve) │
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  PostgreSQL + pgvector │  ← 構築済み
└──────────────────────┘
```

**重要なポイント:**
- フロントエンドは必ずバックエンドAPIを通じてデータを操作する
- ファイルシステムを直接触らない（ノートの保存・読み取りはすべてAPI経由）
- APIが起動していない場合はアプリ起動時に `clawtion api-serve` を自動実行する

---

## 2. 技術スタック

| 層 | 技術 | バージョン | 理由 |
|---|---|---|---|
| フレームワーク | Tauri | 2.x | Rust製、軽量バイナリ、クロスプラットフォーム |
| UI | React | 19.x | エコシステム充実、コンポーネント指向 |
| 言語 | TypeScript | 5.x | 型安全、API型定義と相性良好 |
| エディタ | TipTap | 2.x | ProseMirrorベース、Markdown対応、拡張性 |
| スタイリング | Tailwind CSS | 4.x | ユーティリティファースト、ダークモード容易 |
| HTTP通信 | TanStack Query (React Query) | 5.x | キャッシュ・再取得・楽観的更新 |
| ルーティング | React Router | 7.x | 標準的SPAルーティング |
| 状態管理 | Zustand | 5.x | 軽量、ボイラープレート最小 |
| ビルド | Vite | 6.x | 高速HMR、Tauriとの統合 |
| テスト | Vitest + React Testing Library | 最新 | Vite統合、高速 |
| E2E | Playwright | 最新 | TauriアプリのE2Eテスト |

---

## 3. バックエンドAPI完全仕様

### 3.1 基本情報

| 項目 | 値 |
|---|---|
| ベースURL | `http://127.0.0.1:8000/api/v1` |
| APIドキュメント | `http://127.0.0.1:8000/docs` (Swagger UI) |
| OpenAPI仕様 | `http://127.0.0.1:8000/openapi.json` |
| 認証方式 | なし（ローカルアプリのため。将来的にAPIキー認証追加可能） |
| CORS | 全オリジン許可（開発用。本番は制限推奨） |
| リクエストID | 全レスポンスに `X-Request-ID` ヘッダー付与 |

### 3.2 統一レスポンスフォーマット

**成功レスポンス:**
```json
{
  "data": <T>,           // エンドポイント固有のデータ
  "meta": {              // メタデータ（常に存在）
    "execution_time_ms": 12.5,
    // ... エンドポイント固有のメタ情報
  }
}
```

**エラーレスポンス:**
```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",   // 機械可読エラーコード
    "message": "Document not found: xxx",  // 人間可読メッセージ
    "details": {                    // 追加情報（オプション）
      "document_id": "xxx"
    }
  }
}
```

**HTTPステータスコード:**

| コード | 意味 | 発生条件 |
|---|---|---|
| 200 | 成功 | 検索結果、ノート取得、更新 |
| 201 | 作成成功 | ノート作成 |
| 400 | 不正リクエスト | パラメータ不足/不正 |
| 404 | 未検出 | 存在しないdocument_id |
| 422 | バリデーションエラー | 必須フィールド欠落 |
| 429 | レート制限 | キュー満杯 |
| 500 | サーバーエラー | DB接続失敗、予期せぬエラー |
| 502 | 外部APIエラー | Embedding API失敗 |
| 503 | サービス不可 | Indexing処理中で高負荷 |

---

### 3.3 API全エンドポイント一覧

#### 3.3.1 システム

**GET /health**
サーバー死活確認。

レスポンス:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "connected"
}
```

**GET /version**
バージョン情報。

レスポンス: `{ "version": "0.1.0" }`

---

#### 3.3.2 検索

**POST /search/semantic** — ベクトル類似度検索
```typescript
// Request Body
{
  "query": string,           // 必須, 1-1000文字
  "granularity"?: string,    // "file" | "coarse" | "fine" | "all", デフォルト "file"
  "top_k"?: number,          // 1-100, デフォルト 10
  "metadata_filter"?: {      // オプションのフィルタ
    "folder"?: string,
    "tags"?: string[],
    "date_from"?: string,    // ISO 8601
    "date_to"?: string,      // ISO 8601
    "extension"?: string,
    "namespace"?: string | string[]  // 名前空間UUID
  }
}

// Response
{
  "data": [
    {
      "document_id": "uuid",
      "chunk_id": "uuid",
      "file_path": "notes/example.md",
      "title": "Example Note",
      "folder_path": "notes/",
      "content": "マッチしたテキスト...",
      "content_with_context": "folder: notes | file: example | text: ...",
      "score": 0.89,
      "chunk_level": "file",
      "chunk_index": 0,
      "heading_path": "Section > Subsection"
    }
  ],
  "meta": {
    "query": "検索クエリ",
    "total_results": 5,
    "granularity": "file",
    "search_type": "semantic",
    "execution_time_ms": 45.2,
    "cached": false
  }
}
```

**POST /search/keyword** — 全文キーワード検索

リクエスト・レスポンス形式は `/search/semantic` と同一。`search_type` が `"keyword"` になる。

**POST /search/hybrid** — ハイブリッド検索（ベクトル＋キーワードのRRF融合）

リクエスト・レスポンス形式は `/search/semantic` と同一。`search_type` が `"hybrid"` になる。内部で Reciprocal Rank Fusion (k=60) を使用。

---

#### 3.3.3 チャンクナビゲーション

**GET /chunks/{document_id}/all** — ドキュメントの全チャンク取得

クエリパラメータ: `level` = `"file"` | `"coarse"` | `"fine"`

```json
// Response
{
  "data": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "chunk_level": "coarse",
      "chunk_index": 0,
      "chunk_total": 5,
      "parent_chunk_id": null,
      "heading_path": "Introduction",
      "content": "チャンクテキスト...",
      "content_with_context": "folder: notes | file: example | section: Introduction | text: ...",
      "token_count": 150,
      "char_count": 600,
      "created_at": "2026-05-05T12:00:00+00:00"
    }
  ],
  "meta": {
    "document_id": "uuid",
    "level": "coarse",
    "total_chunks": 5,
    "execution_time_ms": 12.3
  }
}
```

**GET /chunks/{chunk_id}/neighbors** — 前後チャンク取得

クエリパラメータ: `before` (0-10, デフォルト1), `after` (0-10, デフォルト1)

**GET /chunks/{chunk_id}/parent** — 親チャンク取得（マルチレゾリューション用）

---

#### 3.3.4 ノートCRUD

**POST /notes** — ノート作成 (201 Created)

```typescript
// Request Body
{
  "title": string,        // 必須, 1-500文字
  "content": string,      // 必須, 1文字以上 (Markdown)
  "folder"?: string,      // Vault内フォルダパス, 例: "tech/rag"
  "tags"?: string[]       // タグリスト
}

// Response
{
  "data": {
    "document_id": "uuid",
    "title": "My Note",
    "content": "# Hello\n\nWorld",
    "folder_path": "tech/",
    "tags": ["tech", "tutorial"],
    "file_path": "tech/My Note.md",
    "file_extension": ".md",
    "file_size_bytes": 1234,
    "total_chunks": 1,
    "last_indexed_at": "2026-05-05T12:00:00+00:00",
    "created_at": "2026-05-05T12:00:00+00:00",
    "updated_at": "2026-05-05T12:00:00+00:00"
  },
  "meta": { "execution_time_ms": 23.1 }
}
```

**GET /notes/{document_id}** — ノート取得（本文含む）

レスポンス形式は `POST /notes` と同じ。

**PUT /notes/{document_id}** — ノート更新

```typescript
// Request Body
{
  "content": string,      // 必須, 新しい本文 (Markdown)
  "title"?: string,       // オプション: タイトル変更
  "folder"?: string,      // オプション: フォルダ移動
  "tags"?: string[]       // オプション: タグ更新
}
```

**DELETE /notes/{document_id}** — ノート削除

クエリパラメータ: `permanent` = `true` | `false` (デフォルト false = ゴミ箱へ)

```json
// Response
{
  "data": {
    "document_id": "uuid",
    "deleted": true,
    "permanent": false
  }
}
```

**GET /notes** — ノート一覧（本文なし）

クエリパラメータ:
- `folder`?: string — フォルダフィルタ
- `limit`: number (1-500, デフォルト50)
- `offset`: number (0以上, デフォルト0)

```json
// Response
{
  "data": [
    {
      "document_id": "uuid",
      "title": "My Note",
      "folder_path": "notes/",
      "tags": ["tech"],
      "file_path": "notes/My Note.md",
      "total_chunks": 1,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "meta": {
    "folder": null,
    "limit": 50,
    "offset": 0,
    "total": 42,
    "execution_time_ms": 8.2
  }
}
```

**GET /folders** — フォルダ一覧

```json
// Response
{
  "data": [
    {
      "folder_path": "tech/",
      "note_count": 15
    },
    {
      "folder_path": "personal/",
      "note_count": 8
    }
  ],
  "meta": {
    "total_folders": 2,
    "execution_time_ms": 5.1
  }
}
```

---

#### 3.3.5 キュー管理

**GET /queue/status** — キュー統計

```json
{
  "data": {
    "total": 100,
    "pending": 5,
    "processing": 2,
    "completed": 90,
    "failed": 3,
    "cancelled": 0
  }
}
```

**GET /queue/pending** — 保留中ジョブ一覧
**GET /queue/failed** — 失敗ジョブ一覧

クエリパラメータ: `limit` (デフォルト50), `offset` (デフォルト0)

```json
{
  "data": [
    {
      "queue_id": "uuid",
      "document_id": "uuid",
      "file_path": "notes/test.md",
      "operation": "index",
      "status": "pending",
      "priority": 0,
      "retry_count": 0,
      "max_retries": 3,
      "last_error": null,
      "created_at": "...",
      "started_at": null,
      "completed_at": null
    }
  ]
}
```

**POST /queue/process** — キュー処理トリガー
**POST /queue/retry/{queue_id}** — 失敗ジョブ再試行
**POST /queue/clear-failed** — 失敗ジョブ全削除

**GET /metrics** — システムメトリクス

```json
{
  "data": {
    "total_documents": 1234,
    "total_chunks": 5678,
    "indexing_queue_pending": 5,
    "indexing_queue_failed": 0,
    "total_queue_items": 100,
    "db_size_mb": null,
    "vault_path": "/home/user/Documents/clawtion-vault",
    "version": "0.1.0"
  }
}
```

---

## 4. TypeScript型定義

以下を `src/types/api.ts` として実装すること。

```typescript
// ============================================================
// 共通型
// ============================================================

/** API成功レスポンスのラッパー */
interface APIResponse<T> {
  data: T;
  meta: Record<string, unknown> & {
    execution_time_ms: number;
  };
}

/** APIエラーレスポンス */
interface APIError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

/** チャンク粒度 */
type ChunkLevel = 'file' | 'coarse' | 'fine' | 'all';

/** キュー操作タイプ */
type QueueOperation = 'index' | 'reindex' | 'delete';

/** キューステータス */
type QueueStatus = 'pending' | 'processing' | 'partial' | 'completed' | 'failed';

// ============================================================
// 検索
// ============================================================

interface SearchRequest {
  query: string;
  granularity?: ChunkLevel;
  top_k?: number;          // 1-100, default 10
  metadata_filter?: {
    folder?: string;
    tags?: string[];
    date_from?: string;    // ISO 8601
    date_to?: string;      // ISO 8601
    extension?: string;
    namespace?: string | string[];
  };
}

interface SearchResultItem {
  document_id: string;
  chunk_id: string | null;
  file_path: string;
  title: string | null;
  folder_path: string | null;
  content: string;
  content_with_context: string | null;
  score: number;
  chunk_level: ChunkLevel | null;
  chunk_index: number | null;
  heading_path: string | null;
}

interface SearchMeta {
  query: string;
  total_results: number;
  granularity: string;
  search_type: 'semantic' | 'keyword' | 'hybrid';
  execution_time_ms: number;
  cached: boolean;
}

// ============================================================
// チャンク
// ============================================================

interface ChunkItem {
  chunk_id: string;
  document_id: string;
  chunk_level: ChunkLevel;
  chunk_index: number;
  chunk_total: number;
  parent_chunk_id: string | null;
  heading_path: string | null;
  content: string;
  content_with_context: string | null;
  token_count: number | null;
  char_count: number | null;
  created_at: string | null;
}

// ============================================================
// ノート
// ============================================================

interface CreateNoteRequest {
  title: string;           // 1-500 chars
  content: string;         // Markdown, 1+ chars
  folder?: string;
  tags?: string[];
}

interface UpdateNoteRequest {
  content: string;         // Markdown, 1+ chars
  title?: string;
  folder?: string;
  tags?: string[];
}

interface NoteResponse {
  document_id: string;
  title: string;
  content: string;
  folder_path: string;
  tags: string[];
  file_path: string;
  file_extension: string | null;
  file_size_bytes: number | null;
  total_chunks: number;
  last_indexed_at: string | null;
  created_at: string;
  updated_at: string;
}

interface NoteListItem {
  document_id: string;
  title: string;
  folder_path: string;
  tags: string[];
  file_path: string;
  total_chunks: number;
  created_at: string;
  updated_at: string;
}

interface FolderItem {
  folder_path: string;
  note_count: number;
}

// ============================================================
// キュー
// ============================================================

interface QueueStats {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  cancelled: number;
}

interface QueueItem {
  queue_id: string;
  document_id: string;
  file_path: string;
  operation: QueueOperation;
  status: QueueStatus;
  priority: number;
  retry_count: number;
  max_retries: number;
  last_error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

interface SystemMetrics {
  total_documents: number;
  total_chunks: number;
  indexing_queue_pending: number;
  indexing_queue_failed: number;
  total_queue_items: number;
  db_size_mb: number | null;
  vault_path: string;
  version: string;
}
```

---

## 5. UI画面設計

### 5.1 画面一覧

| 画面 | ルート | 説明 |
|---|---|---|
| ノート一覧（サイドバー常駐） | `/notes` | フォルダツリー＋ノート一覧 |
| ノート編集 | `/notes/:id` | Markdownエディタ＋プレビュー |
| ノート新規作成 | `/notes/new` | 新規ノート作成 |
| 検索 | `/search` | 検索バー＋結果一覧＋フィルタ |
| 検索結果詳細 | `/search/:chunkId` | チャンク詳細＋前後ナビ |
| 設定 | `/settings` | APIキー、Vaultパス、モデル選択 |
| キュー管理 | `/queue` | Indexing状態・ジョブ一覧 |
| ゴミ箱 | `/trash` | 削除ノート一覧・復元 |
| システム情報 | `/system` | メトリクス、バージョン情報 |

### 5.2 画面詳細仕様

#### 5.2.1 ノート一覧（メイン画面）

```
┌──────────────┬──────────────────────────────────┐
│ サイドバー    │           メインエリア             │
│              │                                  │
│ 📁 tech/     │  ← フォルダ選択で絞り込み         │
│   📄 rag.md  │                                  │
│   📄 vec.md  │  [ノート一覧テーブル]              │
│ 📁 personal/ │  ┌──────┬────────┬──────────┐   │
│   📄 diary   │  │ タイトル │ フォルダ │ 更新日  │   │
│              │  ├──────┼────────┼──────────┤   │
│ [+新規ノート] │  │ RAG   │ tech/  │ 05/05   │   │
│              │  │ Diary │ person │ 05/04   │   │
│              │  └──────┴────────┴──────────┘   │
│              │                                  │
│              │  [ページネーション: ← 1 2 3 →]   │
└──────────────┴──────────────────────────────────┘
```

**機能:**
- サイドバー: フォルダツリー表示（`GET /folders` で取得）
- メイン: ノート一覧テーブル（`GET /notes?folder=...` で取得）
- クリックで編集画面へ遷移
- 「+新規ノート」ボタンで作成ダイアログ
- ページネーション（limit/offset）

#### 5.2.2 ノート編集画面

```
┌─────────────────────────────────────────────────┐
│ ← 戻る    [保存] [削除]    Indexing: ✅ 完了     │
├─────────────────────────────────────────────────┤
│ タイトル: [RAGについて________________________] │
│ フォルダ: [tech/____________________________]   │
│ タグ:     [rag] [ai] [vector] [+追加]           │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─ Markdownエディタ (TipTap) ──────────────┐  │
│  │                                           │  │
│  │  # RAGについて                            │  │
│  │                                           │  │
│  │  Retrieval Augmented Generation (RAG)は   │  │
│  │  大規模言語モデルの...                     │  │
│  │                                           │  │
│  │  ## チャンキング戦略                       │  │
│  │  ...                                      │  │
│  │                                           │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  [編集] | [プレビュー] 切替タブ                  │
└─────────────────────────────────────────────────┘
```

**機能:**
- タイトル・フォルダ・タグのインライン編集
- TipTapエディタ（Markdownモード）
- プレビュータブ（レンダリング表示）
- 保存: `PUT /notes/:id` → 成功トースト
- 削除: 確認ダイアログ → `DELETE /notes/:id`
- Indexing状態表示（`GET /queue/status` ポーリング）

#### 5.2.3 検索画面

```
┌─────────────────────────────────────────────────┐
│ 🔍 [検索クエリ___________________] [検索]       │
│ 検索タイプ: ○ ハイブリッド  ○ セマンティック  ○ キーワード │
│ 粒度: [file ▾]  フォルダ: [すべて ▾]           │
│ 件数: [10 ▾]                                    │
├─────────────────────────────────────────────────┤
│ 検索結果 (5件, 45ms)                            │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ 📄 tech/rag.md — RAGについて                │ │
│ │ スコア: 0.92  | 粒度: file                  │ │
│ │ Retrieval Augmented Generation (RAG)は...   │ │
│ │ [全文を表示]                                 │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ 📄 tech/vector.md — ベクトル検索             │ │
│ │ スコア: 0.85  | 粒度: coarse                │ │
│ │ pgvectorは近似最近傍探索を...                │ │
│ │ [全文を表示]                                 │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ページネーション: [← 前へ | 次へ →]             │
└─────────────────────────────────────────────────┘
```

**機能:**
- 検索バー（Enterで検索）
- 検索タイプ切替（hybrid/semantic/keyword）
- 粒度フィルタ（file/coarse/fine/all）
- フォルダフィルタ
- 結果カード一覧（スコア、ファイルパス、スニペット表示）
- 「全文を表示」でチャンク詳細＋前後ナビゲーション
- `GET /chunks/:id/neighbors` で前後チャンク取得

#### 5.2.4 設定画面

```
┌─────────────────────────────────────────────────┐
│ 設定                                            │
├─────────────────────────────────────────────────┤
│                                                 │
│ Vault（ノート保存先）                           │
│ [~/Documents/clawtion-vault____________] [参照] │
│                                                 │
│ ───────────────                                 │
│                                                 │
│ Embedding プロバイダ                            │
│ ○ Gemini  ○ OpenAI  ○ Ollama (ローカル)        │
│                                                 │
│ APIキー                                         │
│ Gemini: [••••••••••••••••____________] [表示]   │
│ OpenAI: [••••••••••••••••____________] [表示]   │
│                                                 │
│ モデル設定                                      │
│ Gemini次元数: [768 ▾] (768/1536/3072)          │
│ OpenAI モデル: [text-embedding-3-small ▾]       │
│ Ollama URL:    [http://localhost:11434_______]  │
│                                                 │
│ ───────────────                                 │
│                                                 │
│ チャンキング                                    │
│ ☑ マルチレゾリューション有効                    │
│ ☑ file 粒度 (上限 1500 token)                   │
│ ☑ coarse 粒度 (目安 800 token)                  │
│ ☑ fine 粒度 (目安 100 token)                    │
│                                                 │
│ ───────────────                                 │
│                                                 │
│ UI                                              │
│ 言語: [日本語 ▾]                                │
│ テーマ: ○ ライト  ○ ダーク  ○ システム         │
│                                                 │
│ [保存]                                          │
└─────────────────────────────────────────────────┘
```

**機能:**
- Vaultパス選択（ディレクトリピッカー）
- APIキー設定（マスク表示、クリップボードコピー不可）
- Embeddingプロバイダ切替
- チャンキング設定
- UI言語・テーマ設定
- 保存: `POST /api/v1/config`（将来的に設定API追加）

#### 5.2.5 ゴミ箱画面

```
┌─────────────────────────────────────────────────┐
│ ゴミ箱                                  [空にする]│
├─────────────────────────────────────────────────┤
│ ┌──────┬──────────────┬───────────┬───────────┐ │
│ │ 選択  │ ファイル名    │ 削除日     │ 自動削除予定│ │
│ ├──────┼──────────────┼───────────┼───────────┤ │
│ │ ☐    │ old-note.md  │ 05/01     │ 05/08    │ │
│ │ ☐    │ draft.md     │ 05/03     │ 05/10    │ │
│ └──────┴──────────────┴───────────┴───────────┘ │
│                                                 │
│ [選択したものを復元]  [選択したものを完全削除]     │
└─────────────────────────────────────────────────┘
```

**機能:**
- CLIの `clawtion trash` コマンドに対応するAPIが整備され次第実装
- 当面はCLI経由でゴミ箱操作（`clawtion trash list/restore/empty`）

---

## 6. ルーティング設計

```typescript
// src/router.tsx
import { createBrowserRouter } from 'react-router-dom';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,  // サイドバー＋メインエリアの共通レイアウト
    children: [
      {
        index: true,
        element: <Navigate to="/notes" replace />,
      },
      {
        path: 'notes',
        element: <NoteListPage />,
      },
      {
        path: 'notes/new',
        element: <NoteCreatePage />,
      },
      {
        path: 'notes/:documentId',
        element: <NoteEditPage />,
      },
      {
        path: 'search',
        element: <SearchPage />,
      },
      {
        path: 'search/chunks/:chunkId',
        element: <ChunkDetailPage />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
      {
        path: 'queue',
        element: <QueuePage />,
      },
      {
        path: 'trash',
        element: <TrashPage />,
      },
      {
        path: 'system',
        element: <SystemPage />,
      },
    ],
  },
]);
```

---

## 7. 状態管理設計

### 7.1 Zustandストア設計

```typescript
// src/stores/noteStore.ts
interface NoteStore {
  notes: NoteListItem[];
  currentNote: NoteResponse | null;
  isLoading: boolean;
  error: string | null;
  folderFilter: string | null;

  fetchNotes: (folder?: string, limit?: number, offset?: number) => Promise<void>;
  fetchNote: (id: string) => Promise<void>;
  createNote: (data: CreateNoteRequest) => Promise<string>; // returns doc id
  updateNote: (id: string, data: UpdateNoteRequest) => Promise<void>;
  deleteNote: (id: string, permanent?: boolean) => Promise<void>;
  setFolderFilter: (folder: string | null) => void;
}

// src/stores/searchStore.ts
interface SearchStore {
  query: string;
  results: SearchResultItem[];
  searchType: 'semantic' | 'keyword' | 'hybrid';
  granularity: ChunkLevel;
  topK: number;
  isLoading: boolean;
  meta: SearchMeta | null;

  setQuery: (q: string) => void;
  setSearchType: (t: SearchStore['searchType']) => void;
  search: () => Promise<void>;
}

// src/stores/settingsStore.ts
interface SettingsStore {
  vaultPath: string;
  embeddingProvider: 'gemini' | 'openai' | 'ollama';
  language: 'ja' | 'en';
  theme: 'light' | 'dark' | 'system';
  multiResolution: boolean;
  enabledLevels: { file: boolean; coarse: boolean; fine: boolean };

  setVaultPath: (path: string) => void;
  setProvider: (p: SettingsStore['embeddingProvider']) => void;
  // ...
}

// src/stores/queueStore.ts
interface QueueStore {
  stats: QueueStats | null;
  pendingItems: QueueItem[];
  failedItems: QueueItem[];

  fetchStatus: () => Promise<void>;
  fetchPending: () => Promise<void>;
  fetchFailed: () => Promise<void>;
  retryItem: (id: string) => Promise<void>;
  clearFailed: () => Promise<void>;
}
```

### 7.2 TanStack Queryの使用方針

- ノート一覧・検索結果: `useQuery` で自動キャッシュ
- ノート詳細: `useQuery` + staleTime: 30秒
- ノート作成・更新・削除: `useMutation` + `onSuccess` でキャッシュ無効化
- キュー状態: `useQuery` + refetchInterval: 10秒（ポーリング）
- フォルダ一覧: `useQuery` + staleTime: 5分

```typescript
// 使用例
function useNotes(folder?: string, page?: number) {
  return useQuery({
    queryKey: ['notes', folder, page],
    queryFn: () => api.listNotes({ folder, limit: 50, offset: (page ?? 0) * 50 }),
    staleTime: 30_000,
  });
}
```

---

## 8. コンポーネントツリー

```
<App>
├── <AppLayout>
│   ├── <Sidebar>
│   │   ├── <FolderTree />          // GET /folders → 再帰ツリー
│   │   ├── <NavItem to="/search" icon="🔍" />
│   │   ├── <NavItem to="/queue" icon="📊" badge={pendingCount} />
│   │   ├── <NavItem to="/trash" icon="🗑️" />
│   │   └── <NavItem to="/settings" icon="⚙️" />
│   │
│   ├── <MainContent>
│   │   └── <Outlet />  // React Router
│   │
│   └── <StatusBar>
│       ├── <IndexingStatus />       // GET /queue/status ポーリング
│       ├── <VaultInfo />            // vaultパス＋ノート数
│       └── <VersionBadge />
│
├── <NoteListPage>
│   ├── <NoteTable />
│   │   └── <NoteRow /> (×N)
│   └── <Pagination />
│
├── <NoteEditPage>
│   ├── <NoteHeader />
│   │   ├── <TitleInput />
│   │   ├── <FolderSelect />
│   │   └── <TagInput />
│   ├── <TipTapEditor />
│   │   ├── <MenuBar /> (Bold, Italic, Heading, Code, Link, Image)
│   │   └── <EditorContent />
│   ├── <PreviewPane /> (切替表示)
│   └── <NoteActions /> (保存, 削除)
│
├── <SearchPage>
│   ├── <SearchBar />
│   │   ├── <SearchInput />
│   │   ├── <SearchTypeToggle />
│   │   └── <FilterBar /> (granularity, folder, top_k)
│   └── <SearchResults>
│       └── <SearchResultCard /> (×N)
│           ├── <ScoreBadge />
│           ├── <ContentSnippet />
│           └── <ExpandButton />
│
├── <ChunkDetailPage>
│   ├── <ChunkContent />
│   ├── <NeighborChunks />  // 前後チャンク
│   └── <BackToSearchLink />
│
├── <SettingsPage>
│   ├── <VaultSettings />
│   ├── <ProviderSettings />
│   ├── <ApiKeySettings />
│   ├── <ChunkingSettings />
│   └── <UISettings />
│
├── <QueuePage>
│   ├── <QueueStatsCards />
│   ├── <PendingJobsTable />
│   └── <FailedJobsTable />
│
├── <TrashPage>
│   └── <TrashTable />
│
└── <SystemPage>
    └── <MetricsDisplay />
```

---

## 9. ユーザーフロー

### 9.1 ノート作成フロー
```
ユーザーが [+新規ノート] をクリック
→ 作成ダイアログ表示（タイトル、フォルダ、タグ入力）
→ ユーザーが [作成] をクリック
→ POST /notes → 201 Created
→ /notes/:newId に遷移（編集画面）
→ ユーザーがMarkdown入力
→ [保存] or Ctrl+S → PUT /notes/:id
→ 成功トースト「保存しました」
→ バックグラウンドで indexing 開始（ステータスバーに表示）
```

### 9.2 検索フロー
```
ユーザーが /search に移動
→ 検索バーにクエリ入力 → Enter
→ POST /search/hybrid (デフォルト)
→ 結果ローディング表示
→ 結果カード一覧表示
→ ユーザーが結果をクリック
→ チャンク詳細＋前後ナビゲーション表示
→ ユーザーがノートタイトルをクリック
→ /notes/:documentId に遷移（ノート全体を表示）
```

### 9.3 ノート削除・復元フロー
```
ユーザーがノート編集画面で [削除] をクリック
→ 確認ダイアログ「ゴミ箱に移動しますか？○完全削除」
→ DELETE /notes/:id?permanent=false
→ /notes に戻る
→ ゴミ箱画面 (/trash) で一覧表示
→ [復元] でノートが元のフォルダに戻る
→ 7日後に自動完全削除
```

---

## 10. 開発環境セットアップ

### 10.1 前提条件

```bash
# 必要なツール
node --version    # >= 22.x
npm --version     # >= 10.x
rustc --version   # >= 1.80 (Tauriのビルド用)
cargo --version   # Tauri CLI

# バックエンド
python --version  # >= 3.11
docker --version  # PostgreSQL+pgvector用
```

### 10.2 プロジェクト初期化

```bash
# 1. リポジトリクローン
git clone <repo-url>
cd clawtion

# 2. フロントエンドのセットアップ
npm create tauri-app@latest clawtion-ui -- --template react-ts
cd clawtion-ui

# 3. 依存インストール
npm install
npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-markdown
npm install @tiptap/extension-code-block @tiptap/extension-link
npm install @tiptap/extension-image @tiptap/extension-table
npm install @tanstack/react-query zustand react-router-dom
npm install tailwindcss @tailwindcss/typography
npm install lucide-react   # アイコン

# 4. 開発用依存
npm install -D vitest @testing-library/react @testing-library/jest-dom
npm install -D @playwright/test
npm install -D prettier eslint @typescript-eslint/parser

# 5. バックエンド起動
cd ..
pip install -e ".[dev]"
docker compose up -d          # DB起動
clawtion api-serve --port 8000  # API起動
```

### 10.3 開発サーバー起動

```bash
# フロントエンド開発サーバー（Vite HMR）
cd clawtion-ui
npm run dev
# → http://localhost:5173

# APIプロキシ設定 (vite.config.ts)
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
});

# Tauriアプリとして起動（バックエンド＋フロント統合）
npm run tauri dev
```

### 10.4 環境変数

```bash
# .env (フロントエンド)
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1

# バックエンド (別途 .env で設定済み)
CLAWTION_DB_URL=postgresql+asyncpg://clawtion:clawtion@localhost:5432/clawtion
CLAWTION_GEMINI_API_KEY=your_key_here
CLAWTION_VAULT=~/Documents/clawtion-vault
```

---

## 11. テスト戦略

### 11.1 ユニットテスト (Vitest)

```typescript
// 例: 検索ストアのテスト
import { describe, it, expect } from 'vitest';
import { useSearchStore } from '@/stores/searchStore';

describe('SearchStore', () => {
  it('should update query', () => {
    const store = useSearchStore.getState();
    store.setQuery('RAG');
    expect(store.query).toBe('RAG');
  });

  it('should change search type', () => {
    const store = useSearchStore.getState();
    store.setSearchType('semantic');
    expect(store.searchType).toBe('semantic');
  });
});
```

### 11.2 コンポーネントテスト

```typescript
// 例: 検索バーのテスト
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchBar } from '@/components/SearchBar';

test('search input triggers search on Enter', async () => {
  const user = userEvent.setup();
  render(<SearchBar />);

  const input = screen.getByPlaceholderText('ノートを検索...');
  await user.type(input, 'RAG{enter}');

  // 検索が実行されたことを確認
  expect(screen.getByText('検索中...')).toBeInTheDocument();
});
```

### 11.3 E2Eテスト (Playwright)

```typescript
// tests/e2e/note-create.spec.ts
import { test, expect } from '@playwright/test';

test('create a new note', async ({ page }) => {
  await page.goto('/notes');
  await page.click('[data-testid="new-note-button"]');

  // タイトル入力
  await page.fill('[data-testid="note-title"]', 'E2E Test Note');
  await page.fill('[data-testid="note-content"]', '# Hello\n\nWorld');

  // 保存
  await page.click('[data-testid="save-note"]');

  // 成功確認
  await expect(page.locator('[data-testid="toast-success"]')).toBeVisible();
});
```

### 11.4 テストカバレッジ目標

| レベル | 目標 |
|---|---|
| ユニットテスト（ストア・ユーティリティ） | 90%以上 |
| コンポーネントテスト | 80%以上 |
| E2Eテスト（主要フロー） | 全クリティカルパス |

---

## 12. 配布・ビルド

### 12.1 ビルドコマンド

```bash
# フロントエンドのみのビルド
npm run build

# Tauriデスクトップアプリのビルド
npm run tauri build

# macOS
npm run tauri build -- --target universal-apple-darwin
# → clawtion_0.2.0_universal.dmg

# Windows
npm run tauri build -- --target x86_64-pc-windows-msvc
# → clawtion_0.2.0_x64-setup.exe (インストーラ)
# → clawtion_0.2.0_x64_en-US.msi
```

### 12.2 Tauriバンドル設定

```json
// src-tauri/tauri.conf.json (抜粋)
{
  "build": {
    "beforeBuildCommand": "npm run build",
    "beforeDevCommand": "npm run dev",
    "devPath": "http://localhost:5173",
    "distDir": "../dist"
  },
  "package": {
    "productName": "clawtion",
    "version": "0.2.0"
  },
  "tauri": {
    "bundle": {
      "active": true,
      "targets": "all",
      "identifier": "com.clawtion.app",
      "icon": ["icons/32x32.png", "icons/128x128.png", "icons/icon.icns", "icons/icon.ico"],
      "resources": [],
      "copyright": "MIT License",
      "category": "DeveloperTool",
      "shortDescription": "AI Knowledge Base + Notes",
      "longDescription": "clawtion - Local knowledge base with AI-powered search and note-taking"
    },
    "allowlist": {
      "shell": {
        "open": true
      }
    },
    "security": {
      "csp": "default-src 'self'; connect-src http://127.0.0.1:8000"
    }
  }
}
```

### 12.3 バックエンド同梱戦略

Tauriアプリ起動時にバックエンドAPIが自動起動するよう、Tauriのサイドカー（sidecar）機能を使用する：

```rust
// src-tauri/src/main.rs
use tauri::api::process::Command;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // バックエンドAPIをサイドカーとして起動
            let (mut rx, child) = Command::new_sidecar("clawtion-api")
                .expect("failed to create sidecar")
                .args(["api-serve", "--port", "8000"])
                .spawn()
                .expect("failed to spawn API server");

            // 起動待ち（ヘルスチェック）
            // ...
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running clawtion");
}
```

---

## 付録A: APIクライアント実装例

```typescript
// src/lib/api.ts
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

class ApiClient {
  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    params?: Record<string, string | number | boolean | undefined>
  ): Promise<APIResponse<T>> {
    const url = new URL(`${BASE_URL}${path}`);

    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined) url.searchParams.set(k, String(v));
      });
    }

    const res = await fetch(url.toString(), {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      const err: APIError = await res.json();
      throw new ApiRequestError(err.error.code, err.error.message, res.status);
    }

    return res.json();
  }

  // ---- ノート ----
  listNotes(params?: { folder?: string; limit?: number; offset?: number }) {
    return this.request<NoteListItem[]>('GET', '/notes', undefined, params);
  }

  getNote(id: string) {
    return this.request<NoteResponse>('GET', `/notes/${id}`);
  }

  createNote(data: CreateNoteRequest) {
    return this.request<NoteResponse>('POST', '/notes', data);
  }

  updateNote(id: string, data: UpdateNoteRequest) {
    return this.request<NoteResponse>('PUT', `/notes/${id}`, data);
  }

  deleteNote(id: string, permanent = false) {
    return this.request<{ deleted: boolean }>('DELETE', `/notes/${id}`, undefined, { permanent });
  }

  // ---- 検索 ----
  search(type: 'semantic' | 'keyword' | 'hybrid', data: SearchRequest) {
    return this.request<SearchResultItem[]>('POST', `/search/${type}`, data);
  }

  // ---- チャンク ----
  getFileChunks(documentId: string, level = 'file') {
    return this.request<ChunkItem[]>('GET', `/chunks/${documentId}/all`, undefined, { level });
  }

  getNeighborChunks(chunkId: string, before = 1, after = 1) {
    return this.request<ChunkItem[]>('GET', `/chunks/${chunkId}/neighbors`, undefined, { before, after });
  }

  // ---- キュー ----
  getQueueStatus() {
    return this.request<QueueStats>('GET', '/queue/status');
  }

  // ---- システム ----
  getHealth() {
    return fetch(`${BASE_URL.replace('/api/v1', '')}/health`).then(r => r.json());
  }

  getFolders() {
    return this.request<FolderItem[]>('GET', '/folders');
  }
}

export const api = new ApiClient();
```

---

## 付録B: CSS変数とデザイントークン

```css
/* src/styles/theme.css */
:root {
  /* カラーパレット */
  --color-primary: #3b82f6;       /* Blue-500 */
  --color-primary-hover: #2563eb; /* Blue-600 */
  --color-danger: #ef4444;        /* Red-500 */
  --color-success: #22c55e;       /* Green-500 */
  --color-warning: #f59e0b;       /* Amber-500 */

  /* サーフェス */
  --bg-app: #ffffff;
  --bg-sidebar: #f8fafc;          /* Slate-50 */
  --bg-card: #ffffff;
  --bg-input: #f1f5f9;            /* Slate-100 */

  /* テキスト */
  --text-primary: #0f172a;        /* Slate-900 */
  --text-secondary: #475569;      /* Slate-600 */
  --text-muted: #94a3b8;          /* Slate-400 */

  /* レイアウト */
  --sidebar-width: 260px;
  --header-height: 48px;
  --statusbar-height: 28px;
  --radius: 8px;

  /* タイポグラフィ */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}

[data-theme='dark'] {
  --bg-app: #0f172a;
  --bg-sidebar: #1e293b;
  --bg-card: #1e293b;
  --bg-input: #334155;
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
}
```

---

**本ドキュメントは、clawtionフロントエンド開発に必要な情報をすべて含んでいます。**
**バックエンドの内部実装を知らなくても、このドキュメントだけでフロントエンド開発が可能です。**

質問がある場合は、`http://127.0.0.1:8000/docs` のSwagger UIでAPIの動作を確認するか、
`http://127.0.0.1:8000/openapi.json` のOpenAPI仕様を参照してください。
