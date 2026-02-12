# CLI（docbot.cli）の使い方

docbot は検索用 CLI。サブコマンド `search`（省略可）/ `compose` / `helm` がある。デフォルトでサーバー `http://127.0.0.1:8000` へ `/search` を POST する。

## 実行方法

```bash
python -m docbot.cli [search] <query> [options]
python -m docbot.cli compose <query> [options]
python -m docbot.cli helm <query> [options]
```

## search（既定）

```
python -m docbot.cli [search] "<query>" [--lang ja-jp|en-us] [--limit N] [--base URL] [--json]
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--lang` | 言語で絞り込み | なし |
| `--limit` | ヒット件数 | 5 |
| `--base` | サーバー URL | http://127.0.0.1:8000 |
| `--json` | JSON 出力 | false |

**例**:

```bash
python -m docbot.cli search "パフォーマンス チューニング" --lang ja-jp
python -m docbot.cli "Docker Compose" --lang en-us --limit 10
python -m docbot.cli "timeout" --json
```

**出力例**:

```
Title: パフォーマンスチューニング - Dify Enterprise Docs
URL: https://enterprise-docs.dify.ai/versions/3-0-x/ja-jp/deployment/advanced-configuration/performance
Score: 111.4
Snippet: Helm チャート内の各サービスのリソース割り当てを調整することで...
```

---

## compose

docker-compose.yaml の services を表で要約する。

```
python -m docbot.cli compose "<query>" [--lang ja-jp|en-us] [--limit N] [--base URL]
```

- 検索結果から `docker-compose.yaml` を含む URL を探す
- 見つからなければ Dify コミュニティの compose URL をフォールバック
- 取得した YAML から service / image / ports / depends_on / volumes を抽出

**例**:

```bash
python -m docbot.cli compose "Docker Compose" --lang ja-jp
```

**出力例**:

```
Source: https://raw.githubusercontent.com/langgenius/dify/main/docker/docker-compose.yaml

| service | image | ports | depends_on | volumes |
| --- | --- | --- | --- | --- |
| api | langgenius/dify-api:1.13.0 |  | init_permissions, db_postgres, ... | ./volumes/... |
```

---

## helm

Helm チャートを取得し、helm template でレンダリングして Deployment/StatefulSet/Service 等を表で要約する。

```
python -m docbot.cli helm "<query>" [--lang ja-jp|en-us] [--limit N] [--namespace NS] [--release NAME] [--values PATH] [--set K=V ...] [--base URL]
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--namespace` | helm template の namespace | default |
| `--release` | helm template の release 名 | dify |
| `--values` | values ファイルのパス or URL | なし |
| `--set` | helm --set（複数可） | なし |

- **要 helm CLI**: 未インストール時は「helm が必要です」と表示して終了
- 検索からチャートが見つからない場合は `https://langgenius.github.io/dify-helm` をフォールバック

**例**:

```bash
python -m docbot.cli helm "Dify Helm Chart" --lang en-us
python -m docbot.cli helm "dify-helm" --namespace my-ns --set api.replicas=2
```

**出力例**:

```
Source: https://langgenius.github.io/dify-helm (chart: dify)

## Workloads (Deployment / StatefulSet / DaemonSet / Job / CronJob)

| kind | name | replicas | images | ...
| Deployment | dify-api | 1 | langgenius/dify-api:... | ...
```

---

[← クイックスタート](quickstart.md) | [次: サーバー →](server.md)
