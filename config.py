from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Config:
    host: str = "enterprise-docs.dify.ai"
    base_path: str = "/versions/3-0-x/"
    langs: tuple[str, ...] = ("ja-jp", "en-us")

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

CFG = Config()
