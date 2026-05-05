# clawtion

ローカル知識ベース + AIナレッジ検索 + ノートアプリ

## 概要

clawtionは、以下の2つの役割を1つのアプリケーションで実現します：

1. **AIのためのナレッジベース**: Claude Codeがエージェント的に検索・参照できるローカルRAG基盤
2. **人間のためのメモ帳**: Markdownノートを書き、検索し、整理できる軽量ノートアプリ

## 特徴

- ローカルファイルベース（.md / .pdf / 画像）の知識ベース構築
- Postgres + pgvectorによるベクトル検索
- Hybrid Search（ベクトル + キーワード + メタデータフィルタ）
- Gemini Embedding 2による埋め込み生成（マルチモーダル）
- Claude Codeからの自動アクセス（MCP + サブエージェント + スキル）
- CLI経由のすべての操作
- REST APIによる外部アプリ統合

## クイックスタート

```bash
# インストール
pipx install clawtion

# 初期セットアップ
clawtion init

# 動作確認
clawtion doctor

# 検索
clawtion search "クエリ"

# Claude Codeで使用
# 「私のノートのRAGについて教えて」と聞くだけ
```

## 必要条件

- Python 3.11+
- Docker Desktop
- Gemini APIキー（Google AI Studioで無料取得可能）
- Claude Code（オプション、AI機能を使う場合）

## ライセンス

MIT License
