# クイックスタート

最短で動かすための手順。

## 1. 依存関係

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. インデックス作成

初回は DB を生成する。

```bash
python ingest.py
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
.venv/bin/python -m uvicorn server:app --reload --port 8000
```

## 4. 検索

別ターミナルで:

```bash
./docbot.py "Docker Compose" --lang ja-jp
```

または `docbot.py` に実行権がない場合:

```bash
.venv/bin/python docbot.py "Docker Compose" --lang ja-jp
```

## 5. 動作確認

- `./docbot.py "パフォーマンス" --lang ja-jp` → ヒット数件
- `./docbot.py compose "Docker Compose"` → services 表
- `./docbot.py helm "Dify Helm Chart" --lang en-us` → Workloads/Services 表（要 helm インストール）

---

[← 全体像](overview.md) | [次: CLI 使い方 →](cli.md)
