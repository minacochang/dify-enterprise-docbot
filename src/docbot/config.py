from dataclasses import dataclass
import os
import re

# DB パス（data/ に集約）。環境変数 DOCBOT_DB_PATH で上書き可
DEFAULT_DB_PATH = os.environ.get("DOCBOT_DB_PATH", "data/index.db")


@dataclass(frozen=True)
class Config:
    host: str = "enterprise-docs.dify.ai"
    base_path: str = "/versions/3-0-x/"
    langs: tuple[str, ...] = ("ja-jp", "en-us")
    db_path: str = DEFAULT_DB_PATH

    # 対象URL: バージョン3-0-x かつ ja-jp / en-us のみ
    allow_re: re.Pattern = re.compile(
        r"^https://enterprise-docs\.dify\.ai/versions/3-0-x/(ja-jp|en-us)/"
    )

    # アセット類は除外
    deny_ext: tuple[str, ...] = (
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
        ".zip", ".tar", ".gz", ".pdf"
    )

    # BFSの入口（seed）
    seed_urls: tuple[str, ...] = (
        "https://enterprise-docs.dify.ai/versions/3-0-x/ja-jp/introduction",
        "https://enterprise-docs.dify.ai/versions/3-0-x/en-us/introduction",
    )

    # BFS制限（まずは安全側）
    max_pages: int = 800
    max_depth: int = 8
    concurrency: int = 10

    # dify-helm release notes（追加 ingest 用）
    helm_release_base: str = "https://langgenius.github.io/dify-helm"
    helm_release_seed: str = "https://langgenius.github.io/dify-helm/"


CFG = Config()
