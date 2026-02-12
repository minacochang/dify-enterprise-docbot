# クイックスタート

最短で動かすための手順。

## 1. 依存関係

```bash
python -m venv .venv
.venv/bin/pip install -e .
```

## 2. インデックス作成

初回は DB を生成する。DB は `data/index.db` に格納される。

```bash
python -m docbot.ingest
```

出力例:
```
[1] https://enterprise-docs.dify.ai/versions/3-0-x/ja-jp/introduction
[2] https://...
...
Done. N pages indexed.
```

## 3. サーバー起動（CLI がサーバーを叩く前提）

```bash
.venv/bin/python -m uvicorn docbot.server:app --reload --port 8000
```

## 4. 検索

別ターミナルで:

```bash
python -m docbot.cli "Docker Compose" --lang ja-jp
```

## 5. 動作確認

- `python -m docbot.cli search "パフォーマンス" --lang ja-jp` → ヒット数件
- `python -m docbot.cli compose "Docker Compose"` → services 表
- `python -m docbot.cli helm "Dify Helm Chart" --lang en-us` → Workloads/Services 表（要 helm インストール）

---

[← 全体像](overview.md) | [次: CLI 使い方 →](cli.md)
