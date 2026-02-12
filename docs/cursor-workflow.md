# Cursor での使い方

AI がドキュメント根拠付きで回答するための運用手順。`.cursor/rules/doc-search.mdc` にルールが定義されている。

## ワークフロー概要

1. **検索必須の判定**: 手順・設定・仕様・エラー対応・「根拠は？」等 → 必須
2. **docbot 実行**: `./docbot.py "<クエリ>" --lang <lang>`
3. **Sources 取得**: Title, URL, Snippet を上位 3〜5 件
4. **Answer**: Sources を根拠に要点を整理し、推測は明記

## 検索手順

1. リポジトリルートで:
   ```bash
   python -m docbot.cli "<検索クエリ>" --lang <lang>
   ```
2. 言語:
   - 日本語質問 → `--lang ja-jp`
   - 英語質問 → `--lang en-us`
3. クエリ: 核心語 1〜3 語。0 件時は別表記で最大 2 回まで再検索

## 出力フォーマット（AI 向け）

### Sources（上位 3 件まで）

- Title: ...
- URL: ...
- Snippet: ...

Snippet が薄い場合は 5 件まで増やすか、再検索して補強。

### Answer

- Sources を根拠に要点を箇条書き
- 推測が混じる場合は「推測」と明記

## 0 件のとき

- 「0件。検索語を言い換える / 対象言語を変える」
- 試したクエリを明記してから別案を提案

## 前提

- server 未起動時: `uvicorn docbot.server:app --port 8000` で起動

---

[← ランキング](ranking.md) | [次: 設計判断 →](design-decisions.md)
