from dataclasses import dataclass
import os
import re

# DB パス（data/ に集約）。環境変数 DOCBOT_DB_PATH で上書き可
DEFAULT_DB_PATH = os.environ.get("DOCBOT_DB_PATH", "data/index.db")


@dataclass(frozen=True)
class Config:
    host: str = "enterprise-docs.dify.ai"
    base_path: str = "/versions/"
    langs: tuple[str, ...] = ("ja-jp", "en-us", "zh-cn")
    db_path: str = DEFAULT_DB_PATH

    # 対象URL: /versions/ 配下の全バージョン・全言語
    allow_re: re.Pattern = re.compile(
        r"^https://enterprise-docs\.dify\.ai/versions/[^/]+/[^/]+"
    )

    # アセット類は除外
    deny_ext: tuple[str, ...] = (
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
        ".zip", ".tar", ".gz", ".pdf"
    )

    # BFSの入口（seed）。複数版・複数言語の introduction から辿る
    seed_urls: tuple[str, ...] = (
        # 3-0-x（メイン）
        "https://enterprise-docs.dify.ai/versions/3-0-x/ja-jp/introduction",
        "https://enterprise-docs.dify.ai/versions/3-0-x/en-us/introduction",
        "https://enterprise-docs.dify.ai/versions/3-0-x/zh-cn/introduction",
        # 2-8-x, 3-1-x～3-7-x（部分更新あり）
        "https://enterprise-docs.dify.ai/versions/2-8-x/zh-cn/introduction",
        "https://enterprise-docs.dify.ai/versions/3-1-x/zh-cn/introduction",
        "https://enterprise-docs.dify.ai/versions/3-2-x/zh-cn/introduction",
        "https://enterprise-docs.dify.ai/versions/3-5-x/zh-cn/introduction",
        "https://enterprise-docs.dify.ai/versions/3-6-x/zh-cn/introduction",
        "https://enterprise-docs.dify.ai/versions/3-7-x/zh-cn/introduction",
    )

    # BFS制限（versions 配下複数版を拾うため多めに）
    max_pages: int = 2500
    max_depth: int = 8
    concurrency: int = 10

    # dify-helm release notes（追加 ingest 用）
    helm_release_base: str = "https://langgenius.github.io/dify-helm"
    helm_release_seed: str = "https://langgenius.github.io/dify-helm/"


CFG = Config()
