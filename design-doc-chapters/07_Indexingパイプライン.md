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
