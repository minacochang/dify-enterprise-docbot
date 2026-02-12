# dify-enterprise-docbot

Dify Enterprise 公式ドキュメント（enterprise-docs.dify.ai）のローカル検索ヘルパー。CLI と FastAPI サーバーで高速に検索し、Docker Compose / Helm 構成の要約も行える。

## 主な特徴

- SQLite FTS5 による全文検索
- 日本語 N-gram + 再スコアで検索精度を改善
- `compose`: docker-compose.yaml の services を表で要約
- `helm`: Helm チャートから Deployment/Service 等を表で要約

## まず動かす

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
python ingest.py
.venv/bin/python -m uvicorn server:app --port 8000   # 別ターミナルで
./docbot.py "Docker Compose" --lang ja-jp
```

## CLI 最小例

```bash
./docbot.py "パフォーマンス" --lang ja-jp            # search（既定）
./docbot.py compose "Docker Compose" --lang ja-jp   # compose
./docbot.py helm "Dify Helm Chart" --lang en-us    # helm（要 helm CLI）
```

## ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [docs/overview.md](docs/overview.md) | 全体像・アーキテクチャ・何ができるか |
| [docs/quickstart.md](docs/quickstart.md) | セットアップ〜最短動作 |
| [docs/cli.md](docs/cli.md) | docbot.py の使い方（search / compose / helm + オプション） |
| [docs/server.md](docs/server.md) | FastAPI /search の使い方・起動方法 |
| [docs/indexing.md](docs/indexing.md) | ingest / DB 再生成 / FTS5 / 日本語 N-gram |
| [docs/ranking.md](docs/ranking.md) | ja-jp の再スコアの考え方 |
| [docs/cursor-workflow.md](docs/cursor-workflow.md) | Cursor での docbot → Sources → Answer の運用手順 |
| [docs/design-decisions.md](docs/design-decisions.md) | SQLite/N-gram、Vector DB なしの理由とトレードオフ |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 0 件・lang 違い・DB 作り直し・helm template 失敗など |
