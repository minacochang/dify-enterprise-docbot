# バージョンアップ時のチェックリスト

Dify Enterprise ドキュメントやフォールバック先が更新された際に確認すべき項目。

## 1. Dify Enterprise ドキュメントのバージョン変更

**影響ファイル**: `src/docbot/config.py`

`/versions/` 配下の全バージョン・全言語を対象とする。ingest は llms.txt から URL を動的に取得するため、新バージョン追加時は config 変更不要。

| 項目 | 説明 |
|------|------|
| `allow_re` | `/versions/[version]/[lang]` 形式の URL を許容 |
| `seed_urls` | llms.txt 取得失敗時のフォールバック |
| `max_pages` | 全版を拾うため 2500（必要に応じて調整） |

**手順**: 通常は config 変更不要。DB 再生成で最新ドキュメントが取得される。

```bash
rm -f data/index.db data/index.db-shm data/index.db-wal
python -m docbot.ingest
```

所要時間目安: 約 7〜8 分

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
