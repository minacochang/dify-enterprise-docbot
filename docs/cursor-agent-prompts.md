# Cursor Agent Prompt Cookbook

## はじめに

この repo を Cursor で開いた状態で Agent に投げる前提。  
docbot は Dify Enterprise docs と dify-helm release notes を検索し、`search` / `compose` / `helm` / `upgrade` で要約や経路を出力する。Agent が docbot の結果を根拠に答えを出すと精度が上がる。

---

## ドキュメント検索

### テンプレ（汎用）

> この repo の docbot を使って  
> 「{query}」について調べて、要点と根拠URLをまとめて

### 例

> この repo の docbot を使って  
> 「vector database Qdrant の設定」について調べて、要点と根拠URLをまとめて

---

## Docker Compose

### 全体サービス一覧

> docbot compose で Docker Compose のサービス一覧（image, ports, depends_on, volumes）を出して。表形式でまとめて

### 外部公開確認

> docbot compose の結果から、外部にポート公開しているサービスを抽出して。どのポートが露出しているか一覧にして

### depends_on 確認

> docbot compose で depends_on の依存関係を出して。起動順序やブロッキングの可能性を整理して

---

## Helm / values.yaml

### values.yaml 前提構成

> docbot helm で Dify Helm Chart の構成を出して。values.yaml を使う前提で、どの Deployments と Services が生成されるかまとめて

### Deployment / Service / Ingress

> docbot helm "Dify Helm Chart" で Workloads, Services, Ingresses を取得して。各リソースの kind, name, ポート、selector を表形式で整理して

### env / Secret 抽出

> docbot helm の結果から、各 Deployment が参照している env 変数や Secret を抽出して。機密扱いになりそうな項目をリストアップして

### 特定バージョン指定

> docbot helm "Dify Helm Chart" --chart-version 3.7.5 --values ./values.yaml で構成を出して。レンダリングに使った Chart/AppVersion を明記して

---

## Upgrade（Non-Skippable）

### 基本テンプレ

> この repo の docbot upgrade で {from} から {to} への upgrade 経路と作業を Non-Skippable 考慮でまとめて。各 Hop の主な作業と Sources（release notes URL）を出して

### 例

> この repo の docbot upgrade で 2.8.2 から 3.6.5 への upgrade 経路と作業を Non-Skippable 考慮でまとめて。各 Hop の主な作業と Sources（release notes URL）を出して

### values.yaml 付き版

> docbot upgrade --from 2.8.2 --to 3.6.5 を実行し、作業手順をまとめて。あわせて ./values.yaml を読んで、upgrade で追加・変更が必要な helm values がないか確認して

---

## 設計レビュー系

### アーキ概要

> Dify Enterprise の主要コンポーネントと通信関係を docbot の検索結果を根拠にして整理して。フロント・API・Worker・DB・ストレージの役割と接続関係を図か箇条書きで

### 外部公開面

> docbot helm の結果から、Ingress や NodePort で外部公開されているリソースを抽出して。セキュリティ観点で注意すべきポートをリストアップして

### Secret 管理

> docbot helm の結果とドキュメント検索を使って、Dify が参照する Secret / 環境変数を洗い出して。管理方針の提案を箇条書きで

### 運用注意点

> docbot の search / helm / upgrade の結果を根拠に、Dify Enterprise の運用で注意すべき点（バックアップ、Non-Skippable、パフォーマンス）をまとめて

---

## コツ

- **「docbot の検索結果を根拠にして」** と書くと、Agent が docbot 出力を参照しやすく精度が上がる
- **upgrade は appVersion 基準**（2.8.2, 3.6.5 などはchartVersion）。chartVersion と混同しない
- helm の Chart version と App version は別物。upgrade 経路では appVersion を使う
- docbot 実行前に `python -m docbot.ingest` でインデックス作成が必要（未実行の場合は Agent に ingest させてから検索させる）
