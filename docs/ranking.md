# ja-jp の再スコア（ランキング）

日本語検索は N-gram + 2 段ランキングで精度を上げている。

## 1 段目: FTS5 候補取得

- クエリを 2/3-gram に分解し、FTS5 の OR クエリにする
- `CANDIDATE_LIMIT = 80` 件を BM25 順で取得

```python
# storage.py の _query_to_ngrams_or による例
# クエリ "パフォーマンス" → "パフォ" OR "フォー" OR "ォーマ" OR ...
```

## 2 段目: 再スコア（_rescore_ja）

候補 80 件を `_rescore_ja` で再スコアし、上位 `limit` 件を返す。

### スコア計算

| 条件 | 加点 |
|------|------|
| クエリが title に含まれる | +80 |
| クエリが headings に含まれる | +50 |
| クエリが hpath に含まれる | +25 |
| クエリが lead に含まれる | +18 |
| クエリが body_prefix に含まれる | +10 |
| N-gram ヒット数（title+headings 重視） | +0.8×hit_th + 0.2×hit_lb |
| 連続一致ボーナス | +min(20, len(query)) |

正規化: 空白除去、記号削除。英数字・ひらがな・カタカナ・漢字を残す。

## en-us の扱い

- N-gram は使わず、クエリをそのまま FTS5 に渡す
- BM25 順を維持
- `_is_anchor_noise_en`: URL のアンカー（`#introduction` 等）だけで一致し本文に無い場合、ノイズとして後ろに寄せる

---

[← インデックス](indexing.md) | [次: Cursor ワークフロー →](cursor-workflow.md)
