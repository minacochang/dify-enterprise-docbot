import os
import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from storage import open_db, search_index
from extract import extract_main_text_with_headings

UA = {"User-Agent": "docbot/0.1 (+local)"}

app = FastAPI()
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.db")


def get_conn():
    return open_db(DB_PATH)


class AskReq(BaseModel):
    question: str
    lang: str | None = None
    topk_pages: int = 6
    max_sections: int = 10

class SearchReq(BaseModel):
    query: str
    lang: str | None = None
    limit: int = 10


async def fetch_html(url: str) -> str | None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=UA, timeout=20, follow_redirects=True)
            if r.status_code != 200:
                return None
            if "text/html" not in r.headers.get("content-type", ""):
                return None
            return r.text
    except Exception:
        return None


def pick_sections(sections: list[dict], max_sections: int) -> list[dict]:
    # 最小：長い順（あとで「質問との関連度」で改善できる）
    return sorted(sections, key=lambda s: len(s["text"]), reverse=True)[:max_sections]


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/search")
def search(req: SearchReq):
    try:
        conn = get_conn()
        hits = search_index(conn, req.query, lang=req.lang, limit=req.limit)
        conn.close()
        return {"hits": hits}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "type": type(e).__name__},
        )


@app.post("/ask")
async def ask(req: AskReq):
    conn = get_conn()
    hits = search_index(conn, req.question, lang=req.lang, limit=max(30, req.topk_pages * 5))
    pages = hits[:req.topk_pages]

    contexts = []
    for p in pages:
        html = await fetch_html(p["url"])
        if not html:
            continue
        sections = extract_main_text_with_headings(html)
        for s in pick_sections(sections, req.max_sections):
            contexts.append(
                {
                    "url": p["url"],
                    "heading": s["heading"],
                    "quote": s["text"][:900],
                }
            )

    conn.close()
    # まずはLLM未接続で引用候補を返す（動作確認用）
    return {
        "answer": "（LLM未接続）関連する引用候補です。LLMを繋ぐと、この引用だけを根拠に文章回答します。",
        "citations": contexts[:25],
        "hits": pages,
    }
