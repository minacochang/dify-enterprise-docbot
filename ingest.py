"""
Dify Enterprise docs クロール＆インデックス作成。

スキーマ変更後は DB 再生成が必要:
  rm -f index.db index.db-shm index.db-wal && python ingest.py
"""
import asyncio
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from lxml import etree

from config import CFG
from storage import open_db, upsert_page
from extract import extract_index_fields, extract_headings_and_body_prefix

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

async def fetch_text(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url, headers=UA, timeout=20, follow_redirects=True)
        if r.status_code != 200:
            return None
        ctype = r.headers.get("content-type", "")
        if "text/html" not in ctype and "application/xml" not in ctype and "text/xml" not in ctype:
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

def make_ngrams(text: str, ns=(2, 3), limit=4000) -> str:
    # 超雑でOK：日本語は空白で区切られないので、連続文字からN-gramを作る
    s = "".join(text.split())
    toks = []
    for n in ns:
        if len(s) < n:
            continue
        for i in range(len(s) - n + 1):
            toks.append(s[i:i+n])
    # でかくなりすぎ防止
    if len(toks) > limit:
        toks = toks[:limit]
    return " ".join(toks)


async def main() -> None:
    conn = open_db("index.db")
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

    conn.close()
    print(f"Done. {count} pages indexed.")


if __name__ == "__main__":
    asyncio.run(main())
