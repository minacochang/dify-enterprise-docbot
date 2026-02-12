"""
Dify Enterprise docs クロール＆インデックス作成。

スキーマ変更後は DB 再生成が必要:
  rm -f data/index.db data/index.db-shm data/index.db-wal && python -m docbot.ingest
"""
import asyncio
import os
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from lxml import etree

from docbot.config import CFG
from docbot.storage import open_db, upsert_page
from docbot.extract import (
    extract_index_fields,
    extract_headings_and_body_prefix,
    extract_index_fields_markdown,
    extract_headings_and_body_prefix_markdown,
)

UA = {"User-Agent": "docbot/0.1 (+local)"}


def is_allowed(url: str) -> bool:
    if not CFG.allow_re.match(url):
        return False
    low = url.lower()
    if any(low.endswith(ext) for ext in CFG.deny_ext):
        return False
    return True


def detect_lang(url: str) -> str:
    parts = urlparse(url).path.split("/")
    return parts[3] if len(parts) >= 4 else "unknown"


async def fetch_text(client: httpx.AsyncClient, url: str, accept_any_text: bool = False) -> str | None:
    try:
        r = await client.get(url, headers=UA, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            return None
        ctype = (r.headers.get("content-type") or "").lower()
        allowed = (
            "text/html" in ctype or "application/xml" in ctype or "text/xml" in ctype or
            (accept_any_text and ("text/" in ctype or "application/" in ctype or not ctype))
        )
        if not allowed:
            return None
        return r.text
    except Exception:
        return None


async def try_sitemap(client: httpx.AsyncClient) -> list[str] | None:
    sitemap_url = f"https://{CFG.host}/sitemap.xml"
    xml = await fetch_text(client, sitemap_url)
    if not xml:
        return None

    try:
        root = etree.fromstring(xml.encode("utf-8"))
    except Exception:
        return None

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    locs = root.xpath("//sm:sitemap/sm:loc/text()", namespaces=ns)
    urls: list[str] = []
    if locs:
        for loc in locs:
            sub_xml = await fetch_text(client, loc)
            if not sub_xml:
                continue
            try:
                sub_root = etree.fromstring(sub_xml.encode("utf-8"))
            except Exception:
                continue
            sub_urls = sub_root.xpath("//sm:url/sm:loc/text()", namespaces=ns)
            urls.extend([u for u in sub_urls if is_allowed(u)])
        return urls or None

    sub_urls = root.xpath("//sm:url/sm:loc/text()", namespaces=ns)
    urls = [u for u in sub_urls if is_allowed(u)]
    return urls or None


def extract_helm_page_links(sidebar_content: str) -> list[str]:
    """
    dify-helm _sidebar.md から /pages/X.md リンクを抽出し、フル URL に変換。
    形式: * [v3.7.5](/pages/3_7_5.md)
    """
    base = CFG.helm_release_base
    seen = set()
    out = []
    for m in re.finditer(r"\(/pages/([a-zA-Z0-9_.-]+)\.md\)", sidebar_content):
        page_id = m.group(1)
        if page_id in seen:
            continue
        seen.add(page_id)
        url = f"{base}/pages/{page_id}.md"
        out.append(url)
    return out


def extract_nav_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = urljoin(base_url, href)
        if not is_allowed(full_url):
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        out.append(full_url)
    return out


async def ingest_helm_release_notes(conn, client: httpx.AsyncClient) -> int:
    """dify-helm release notes をインデックスに追加"""
    base = CFG.helm_release_base
    sidebar_url = f"{base}/_sidebar.md"

    sidebar = await fetch_text(client, sidebar_url, accept_any_text=True)
    if not sidebar:
        print("Note: dify-helm _sidebar.md fetch failed, skipping release notes.")
        return 0

    urls = extract_helm_page_links(sidebar)
    urls.append(f"{base}/README.md")
    urls = list(dict.fromkeys(urls))

    count = 0
    now = int(time.time())
    lang = "en-us"

    for url in urls:
        md = await fetch_text(client, url, accept_any_text=True)
        if not md:
            continue
        title, hpath, lead = extract_index_fields_markdown(md)
        headings, body_prefix = extract_headings_and_body_prefix_markdown(md, body_prefix_len=4000)
        ngrams_source = f"{title}\n{hpath}\n{lead}\n{headings}\n{body_prefix}"
        ngrams = make_ngrams(ngrams_source)
        upsert_page(conn, url, lang, title, hpath, lead, headings, body_prefix, ngrams, now)
        count += 1
        print(f"[helm+{count}] {url}")

    return count


def make_ngrams(text: str, ns=(2, 3), limit=4000) -> str:
    s = "".join(text.split())
    toks = []
    for n in ns:
        if len(s) < n:
            continue
        for i in range(len(s) - n + 1):
            toks.append(s[i:i+n])
    if len(toks) > limit:
        toks = toks[:limit]
    return " ".join(toks)


async def main() -> None:
    db_path = CFG.db_path
    parent = Path(db_path).parent
    if parent:
        parent.mkdir(parents=True, exist_ok=True)

    conn = open_db(db_path)
    queue: deque[tuple[str, int]] = deque((u, 0) for u in CFG.seed_urls)
    done: set[str] = set()
    count = 0

    async with httpx.AsyncClient() as client:
        while queue and count < CFG.max_pages:
            batch = []
            while queue and len(batch) < CFG.concurrency:
                item = queue.popleft()
                if item[0] in done:
                    continue
                done.add(item[0])
                batch.append(item)

            if not batch:
                break

            tasks = [fetch_text(client, url) for url, depth in batch]
            results = await asyncio.gather(*tasks)
            now = int(time.time())

            for (url, depth), html in zip(batch, results):
                if not html:
                    continue
                lang = detect_lang(url)
                title, hpath, lead = extract_index_fields(html)
                headings = ""
                body_prefix = ""
                ngrams = ""
                if lang == "ja-jp":
                    headings, body_prefix = extract_headings_and_body_prefix(html, body_prefix_len=4000)
                    ngrams_source = f"{title}\n{hpath}\n{lead}\n{headings}\n{body_prefix}"
                    ngrams = make_ngrams(ngrams_source)
                upsert_page(conn, url, lang, title, hpath, lead, headings, body_prefix, ngrams, now)
                count += 1
                print(f"[{count}] {url}")

                if depth < CFG.max_depth:
                    for link in extract_nav_links(url, html):
                        if link not in done:
                            queue.append((link, depth + 1))

        helm_count = await ingest_helm_release_notes(conn, client)
    conn.close()
    print(f"Done. {count} enterprise docs + {helm_count} helm release notes indexed.")


if __name__ == "__main__":
    asyncio.run(main())
