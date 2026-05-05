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
