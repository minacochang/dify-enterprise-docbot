# トラブルシューティング

## 0 件になる

**症状**: `python -m docbot.cli "検索語"` で「0件。検索対象フィールド/言語を確認」と表示される。

**確認**:
1. **DB の有無**: `data/index.db` が存在するか。無ければ `python -m docbot.ingest` を実行
2. **言語**: `--lang ja-jp` / `--lang en-us` を付けるとヒットしやすい。付けないと全言語だが、クエリが曖昧だと 0 件になりやすい
3. **クエリ**: 核心語 1〜3 語で試す。表記ゆれがあれば別表記で再検索（例: 「パフォーマンス」「performance」）

## 言語が想定と違う

**症状**: 日本語を期待しているのに英語ページが多く出る、またはその逆。

**対応**: `--lang ja-jp` または `--lang en-us` で明示的に絞る。

## DB を作り直したい

スキーマ変更や再クロールが必要な場合:

```bash
rm -f data/index.db data/index.db-shm data/index.db-wal
python -m docbot.ingest
```

## helm template 失敗

**症状**: `python -m docbot.cli helm "..."` で「helm template 失敗」と表示される。

**確認**:
1. **helm の有無**: `which helm` でパスが返るか。無ければ https://helm.sh からインストール
2. **チャート取得**: ネットワークが通じているか。フォールバック先 `https://langgenius.github.io/dify-helm` が取得できるか

**補足**: Dify チャートは postgresql/redis を無効にするとテンプレートエラーになる。docbot は要約用のダミー値を `--set` で渡して回避している。

## compose で「取得できませんでした」

**症状**: `python -m docbot.cli compose "..."` で YAML 取得に失敗する。

**確認**:
1. 検索が成功しているか（サーバー起動済みか）
2. フォールバックの `https://raw.githubusercontent.com/langgenius/dify/main/docker/docker-compose.yaml` にアクセスできるか
3. 企業ネットワークで GitHub raw がブロックされていないか

## サーバー 500 エラー

**症状**: docbot 実行時に `ERROR: failed to call .../search: 500 Internal Server Error`

**確認**:
1. `data/index.db` が存在するか
2. スキーマが壊れていないか（`rm` して `python -m docbot.ingest` で再生成）

**helm の場合**: 検索が 500 でも、フォールバックチャートで続行する。stderr に「Note: search failed, using fallback chart」と出る。

---

[← 設計判断](design-decisions.md) | [次: バージョンアップ →](version-upgrade.md) | [README に戻る](../README.md)
