# 全体像

Dify Enterprise ドキュメント（enterprise-docs.dify.ai）を対象にしたローカル検索ヘルパー。CLI と FastAPI サーバーで、公式ドキュメントの内容を高速に検索できる。

## アーキテクチャ概略

```
┌─────────────────┐     POST /search      ┌──────────────────┐     FTS5      ┌─────────────────┐
│ docbot.cli      │ ──────────────────▶  │ docbot.server    │ ────────────▶ │ data/index.db   │
│ (python -m)     │  http://127.0.0.1:8000│ (FastAPI)         │               │ (SQLite)        │
└─────────────────┘                       └──────────────────┘               └─────────────────┘
       │                                      │
       │ compose / helm サブコマンド            │ /ask (引用抽出)
       ▼                                      ▼
  検索結果URLから YAML 取得・解析           HTML fetch → セクション抽出
```

- **docbot.ingest**: クロールして `data/index.db` に格納
- **docbot.storage**: SQLite FTS5 で全文検索、ja-jp は N-gram + 再スコア
- **docbot.extract**: HTML から title/lead/headings/body 抽出

## 何ができるか

| 機能 | 説明 |
|------|------|
| **search** | クエリでドキュメントを検索し、Title / URL / Score / Snippet を表示 |
| **compose** | 検索 → docker-compose.yaml 取得 → services を表で要約 |
| **helm** | 検索 → Helm チャート取得 → helm template → Deployment/Service 等を表で要約 |
| **/search** | FastAPI の POST エンドポイント。外部ツールから呼び出し可 |
| **/ask** | 検索結果のページを fetch し、引用候補を返す（現状 LLM 未接続） |

## 対象ドキュメント

- **URL**: `https://enterprise-docs.dify.ai/versions/3-0-x/`
- **言語**: ja-jp, en-us のみ
- **クロール**: seed から BFS、最大 800 ページ、depth 8

---

[← README](../README.md) | [次: クイックスタート →](quickstart.md)
