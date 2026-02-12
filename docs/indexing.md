# インデックス作成（ingest）

`docbot.ingest` が enterprise-docs.dify.ai をクロールし、`data/index.db` に格納する。あわせて **dify-helm release notes**（https://langgenius.github.io/dify-helm/）の `_sidebar.md` と `/pages/*.md` も取得し、検索対象に追加する。

## 実行方法

```bash
python -m docbot.ingest
```

- seed: `llms.txt` から URL を動的取得（失敗時は `seed_urls` で BFS）
- 最大 `max_pages`（2500）件まで
- **所要時間目安**: 約 7〜8 分（ネットワーク状況により変動。2500 ページ＋helm release notes 取得）

## DB 再生成

スキーマ変更や全再取得が必要な場合:

```bash
rm -f data/index.db data/index.db-shm data/index.db-wal
python -m docbot.ingest
```

## スキーマ（FTS5）

`docbot.storage` の `SCHEMA` で定義:

- **pages**: url, lang, title, hpath, lead, headings, body_prefix, ngrams, fetched_at
- **pages_fts**: FTS5 仮想テーブル。`content='pages'` で pages を参照

FTS5 のクエリは `ORDER BY bm25(pages_fts)` で BM25 スコア順。

## 日本語 N-gram

- **ingest**: `lang in ("ja-jp", "zh-cn")` のとき、`extract_headings_and_body_prefix` で headings + body_prefix（先頭 4000 字）を取得し、`make_ngrams` で 2/3-gram を生成して `ngrams` に格納
- **storage**: 検索時に `_query_to_ngrams_or` でクエリを N-gram 化し、FTS5 の OR クエリとして実行
- **ranking**: FTS5 候補を `_rescore_ja` で再スコアし、上位を返す

詳細は [ranking.md](ranking.md) を参照。

## 対象 URL

`docbot.config` の `allow_re` で制限:

- `https://enterprise-docs.dify.ai/versions/[version]/[lang]` 配下の全バージョン・全言語
- 画像・ZIP 等は `deny_ext` で除外

---

[← サーバー](server.md) | [次: ランキング →](ranking.md)
