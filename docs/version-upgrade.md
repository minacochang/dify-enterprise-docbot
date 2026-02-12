# バージョンアップ時のチェックリスト

Dify Enterprise ドキュメントやフォールバック先が更新された際に確認すべき項目。

## 1. Dify Enterprise ドキュメントのバージョン変更

**影響ファイル**: `src/docbot/config.py`

現在は `3-0-x` に固定。Docs が `3-1-x` 等に変わった場合、以下を更新する。

| 項目 | 場所 | 対応 |
|------|------|------|
| `base_path` | config.py | `/versions/3-1-x/` 等に変更 |
| `allow_re` | config.py | 正規表現内の `3-0-x` を新バージョンに変更 |
| `seed_urls` | config.py | introduction の URL を新バージョンに変更 |

**手順**: config 更新後、**必ず DB 再生成**する。

```bash
rm -f data/index.db data/index.db-shm data/index.db-wal
python -m docbot.ingest
```

## 2. compose / helm フォールバック URL

**影響ファイル**: `src/docbot/cli.py`

| 定数 | 用途 |
|------|------|
| `DIFY_COMPOSE_URL` | compose フォールバック（langgenius/dify main） |
| `DIFY_HELM_REPO` | helm フォールバック |
| `DIFY_HELM_CHART` | chart 名（通常 dify） |

フォールバック先のチャート構造が変わった場合、`_DIFY_HELM_DEFAULT_SET` の見直しが必要な場合あり。

## 3. DB スキーマ変更

**影響ファイル**: `src/docbot/storage.py`

スキーマ（FTS5 カラム等）を変更した場合は **必ず DB 再生成**する。

```bash
rm -f data/index.db data/index.db-shm data/index.db-wal
python -m docbot.ingest
```

## 4. Python 依存関係

`pyproject.toml` 更新後は `pip install -e .` で再インストール。必要に応じて venv をクリーンに作り直す。

---

## チェックリスト一覧

| 項目 | 確認内容 |
|------|----------|
| ドキュメント URL | enterprise-docs.dify.ai に新バージョンパスが追加されていないか |
| config.py | `base_path` / `allow_re` / `seed_urls` を更新したか |
| DB 再生成 | `python -m docbot.ingest` 実行で新ドキュメントがインデックスされるか |
| compose | `python -m docbot.cli compose "Docker Compose"` が動くか |
| helm | `python -m docbot.cli helm "Dify Helm Chart"` が動くか |
| スキーマ | `storage.py` 変更時、DB 再生成したか |

---

[← トラブルシューティング](troubleshooting.md) | [README に戻る](../README.md)
