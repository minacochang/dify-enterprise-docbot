#!/usr/bin/env python3
import argparse
import json
import sys
import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"

def main():
    p = argparse.ArgumentParser(prog="docbot", description="Local doc search helper for Dify Enterprise docs")
    p.add_argument("query", nargs="*", help="search query words")
    p.add_argument("--lang", choices=["ja-jp", "en-us"], default=None, help="language filter")
    p.add_argument("--limit", type=int, default=5, help="max hits")
    p.add_argument("--base", default=DEFAULT_BASE, help="API base url (default: http://127.0.0.1:8000)")
    p.add_argument("--json", action="store_true", help="print raw json")
    args = p.parse_args()

    q = " ".join(args.query).strip()
    if not q:
        print("Usage: docbot <query> [--lang ja-jp|en-us] [--limit N]", file=sys.stderr)
        return 2

    url = args.base.rstrip("/") + "/search"
    payload = {"query": q, "lang": args.lang, "limit": args.limit}

    try:
        r = httpx.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"ERROR: failed to call {url}: {e}", file=sys.stderr)
        return 1

    data = r.json()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    hits = data.get("hits") or []
    if not hits:
        print("0件。検索対象フィールド/言語を確認")
        return 0

    # Cursorがそのまま貼れる形式: Title, URL, Score, Snippet
    for i, h in enumerate(hits, 1):
        title = (h.get("title") or "").strip()
        url = h.get("url") or ""
        score = h.get("score")
        snippet = (h.get("lead") or "").replace("\n", " ").strip()
        snippet = snippet[:280] + ("…" if len(snippet) > 280 else "")

        print(f"Title: {title}")
        print(f"URL: {url}")
        if score is not None:
            print(f"Score: {score:.1f}")
        if snippet:
            print(f"Snippet: {snippet}")
        print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
