# サーバー（FastAPI）

`docbot.server` は FastAPI アプリ。主に `/search` を docbot CLI や外部ツールが利用する。

## 起動

```bash
python -m uvicorn docbot.server:app --reload --port 8000
```

または:

```bash
uvicorn docbot.server:app --port 8000
```

## エンドポイント

### POST /search

検索。docbot が内部で使用。

**リクエスト**:

```json
{
  "query": "パフォーマンス",
  "lang": "ja-jp",
  "limit": 10
}
```

| フィールド | 型 | 説明 |
|-----------|-----|------|
| query | string | 検索クエリ |
| lang | string \| null | ja-jp / en-us で絞り込み。null は絞らない |
| limit | int | 返却件数。デフォルト 10 |

**レスポンス**:

```json
{
  "hits": [
    {
      "url": "https://enterprise-docs.dify.ai/...",
      "lang": "ja-jp",
      "title": "パフォーマンスチューニング - Dify Enterprise Docs",
      "hpath": "h1 | h2 | h3 のパス",
      "lead": "冒頭テキスト...",
      "score": 111.4
    }
  ]
}
```

**curl 例**:

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"Docker Compose","lang":"ja-jp","limit":5}'
```

### POST /ask

検索 → ヒットページの HTML 取得 → セクション単位で引用を返す。現状は LLM 未接続で引用候補のみ返す。

**リクエスト**:

```json
{
  "question": "Docker Compose の構成は？",
  "lang": "ja-jp",
  "topk_pages": 6,
  "max_sections": 10
}
```

### GET /health

死活監視用。

```bash
curl http://127.0.0.1:8000/health
# {"ok": true}
```

## DB パス

`docbot.server` は `data/index.db`（`docbot.config.CFG.db_path`）を cwd 基準で読み込む。事前に `python -m docbot.ingest` で DB を生成しておく必要がある。

---

[← CLI](cli.md) | [次: インデックス作成 →](indexing.md)
