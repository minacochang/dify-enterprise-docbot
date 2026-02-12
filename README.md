# dify-enterprise-docbot

Dify Enterprise 公式ドキュメント（enterprise-docs.dify.ai）のローカル検索ヘルパー。CLI と FastAPI サーバーで高速に検索し、Docker Compose / Helm 構成の要約も行える。

## Who is this for?
- People operating Dify Enterprise in production
- Engineers tired of opaque RAG pipelines
- Teams wanting deterministic, debuggable AI-assisted workflows
- Cursor users who want a local, structure-first doc assistant

## 主な特徴

- SQLite FTS5 による全文検索
- 日本語 N-gram + 再スコアで検索精度を改善
- `compose`: docker-compose.yaml の services を表で要約
- `helm`: Helm チャートから Deployment/Service 等を表で要約

## まず動かす

```bash
python -m venv .venv
.venv/bin/pip install -e .
python -m docbot.ingest
.venv/bin/python -m uvicorn docbot.server:app --port 8000   # 別ターミナルで
python -m docbot.cli "Docker Compose" --lang ja-jp
```

DB は `data/index.db` に格納。再生成: `rm -f data/index.db data/index.db-shm data/index.db-wal && python -m docbot.ingest`（目安: 約 7〜8 分）

### 動作確認

```bash
# サーバー起動（別ターミナル）
python -m uvicorn docbot.server:app --port 8000

# 検索
python -m docbot.cli search "docker" --lang ja-jp --limit 5
python -m docbot.cli search "introduction" --lang en-us --limit 5
# compose / helm
python -m docbot.cli compose "Docker Compose" --lang ja-jp
python -m docbot.cli helm "Dify Helm Chart" --lang en-us
# API
curl -X POST http://127.0.0.1:8000/search -H "Content-Type: application/json" -d '{"query":"docker","lang":"ja-jp","limit":3}'
```

## CLI 最小例

```bash
python -m docbot.cli search "パフォーマンス" --lang ja-jp   # search
python -m docbot.cli compose "Docker Compose" --lang ja-jp  # compose
python -m docbot.cli helm "Dify Helm Chart" --lang en-us    # helm（要 helm CLI）
python -m docbot.cli helm "Dify Helm Chart" --chart-version 3.7.5 --values ./values.yaml  # バージョン固定
python -m docbot.cli helm --chart ./dify-3.7.4.tgz  # ローカル chart を直接指定
python -m docbot.cli upgrade --from 2.8.2 --to 3.6.5  # Non-Skippable を考慮したアップグレード経路（appVersion 基準）
```

`upgrade` は storage/search で release notes を検索し、Non-Skippable を考慮した経路（例: 2.8.2 → 3.2.2 → 3.6.5）と各 Hop の作業・Sources を Markdown で出力する。

### 検索対象

- Enterprise docs（enterprise-docs.dify.ai の `/versions/` 配下の全バージョン・全言語）
- dify-helm release notes（https://langgenius.github.io/dify-helm/）

## ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [docs/overview.md](docs/overview.md) | 全体像・アーキテクチャ・何ができるか |
| [docs/quickstart.md](docs/quickstart.md) | セットアップ〜最短動作 |
| [docs/cli.md](docs/cli.md) | docbot.cli の使い方（search / compose / helm + オプション） |
| [docs/server.md](docs/server.md) | FastAPI /search の使い方・起動方法 |
| [docs/indexing.md](docs/indexing.md) | ingest / DB 再生成 / FTS5 / 日本語 N-gram |
| [docs/ranking.md](docs/ranking.md) | ja-jp の再スコアの考え方 |
| [docs/cursor-workflow.md](docs/cursor-workflow.md) | Cursor での docbot → Sources → Answer の運用手順 |
| [docs/cursor-agent-prompts.md](docs/cursor-agent-prompts.md) | Cursor Agent 用プロンプト例集（コピペ可） |
| [docs/design-decisions.md](docs/design-decisions.md) | SQLite/N-gram、Vector DB なしの理由とトレードオフ |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 0 件・lang 違い・DB 作り直し・helm template 失敗など |
| [docs/version-upgrade.md](docs/version-upgrade.md) | バージョンアップ時のチェックリスト |
