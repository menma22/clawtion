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
