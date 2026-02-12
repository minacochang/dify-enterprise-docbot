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
    p.add_argument("--limit", type=int, default=10, help="max hits")
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
        print("(no hits)")
        return 0

    # 見やすい表示（Cursorでコピペしやすい）
    for i, h in enumerate(hits, 1):
        title = (h.get("title") or "").strip()
        lang = h.get("lang")
        url = h.get("url")
        lead = (h.get("lead") or "").strip()
        if len(lead) > 140:
            lead = lead[:140] + "…"
        print(f"[{i}] ({lang}) {title}")
        print(f"    {url}")
        if lead:
            print(f"    {lead}")
        print()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
