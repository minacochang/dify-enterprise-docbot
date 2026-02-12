import os
import re
import sqlite3

from docbot.config import CFG

# ja-jp 2段ランキング：1段目の候補数
CANDIDATE_LIMIT = 80
MAX_NGRAM_TERMS = 180


def _normalize_ja(text: str) -> str:
    """空白除去、記号削除"""
    s = "".join(text.split())
    # 記号・制御文字を除去（英数字・日本語・一部記号は残す）
    s = re.sub(r"[^\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]", "", s)
    return s


def _make_ngrams_q(text: str, ns: tuple[int, ...] = (3, 2), max_terms: int = MAX_NGRAM_TERMS) -> list[str]:
    """3-gram優先＋2-gram補助、重複除去、max_terms 上限"""
    s = _normalize_ja(text)
    seen: set[str] = set()
    toks: list[str] = []
    for n in ns:
        if len(s) < n or len(toks) >= max_terms:
            continue
        for i in range(len(s) - n + 1):
            t = s[i : i + n]
            if t not in seen:
                seen.add(t)
                toks.append(t)
                if len(toks) >= max_terms:
                    return toks
    return toks


def _query_to_ngrams_or(query: str, max_terms: int = MAX_NGRAM_TERMS) -> str:
    """ORクエリ生成、エスケープ実装"""
    toks = _make_ngrams_q(query, ns=(3, 2), max_terms=max_terms)
    if not toks:
        return query
    escaped = [t.replace('"', '""') for t in toks]
    return " OR ".join(f'"{t}"' for t in escaped)


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS pages (
  url TEXT PRIMARY KEY,
  lang TEXT NOT NULL,
  title TEXT,
  hpath TEXT,
  lead TEXT,
  headings TEXT,
  body_prefix TEXT,
  ngrams TEXT,
  fetched_at INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts
USING fts5(url, lang, title, hpath, lead, headings, body_prefix, ngrams, content='pages', content_rowid='rowid');

CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
  INSERT INTO pages_fts(rowid, url, lang, title, hpath, lead, headings, body_prefix, ngrams)
  VALUES (new.rowid, new.url, new.lang, new.title, new.hpath, new.lead, new.headings, new.body_prefix, new.ngrams);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
  INSERT INTO pages_fts(pages_fts, rowid, url, lang, title, hpath, lead, headings, body_prefix, ngrams)
  VALUES ('delete', old.rowid, old.url, old.lang, old.title, old.hpath, old.lead, old.headings, old.body_prefix, old.ngrams);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
  INSERT INTO pages_fts(pages_fts, rowid, url, lang, title, hpath, lead, headings, body_prefix, ngrams)
  VALUES ('delete', old.rowid, old.url, old.lang, old.title, old.hpath, old.lead, old.headings, old.body_prefix, old.ngrams);
  INSERT INTO pages_fts(rowid, url, lang, title, hpath, lead, headings, body_prefix, ngrams)
  VALUES (new.rowid, new.url, new.lang, new.title, new.hpath, new.lead, new.headings, new.body_prefix, new.ngrams);
END;
"""


def _rescore_ja(row: tuple, query: str) -> float:
    """ja-jp 用再スコア"""
    url, lang, title, hpath, lead, headings, body_prefix = row[:7]
    qn = _normalize_ja(query)
    score = 0.0

    title_n = _normalize_ja(title or "")
    headings_n = _normalize_ja(headings or "")
    hpath_n = _normalize_ja(hpath or "")
    lead_n = _normalize_ja(lead or "")
    body_n = _normalize_ja(body_prefix or "")

    if qn and qn in title_n:
        score += 80
    if qn and qn in headings_n:
        score += 50
    if qn and qn in hpath_n:
        score += 25
    if qn and qn in lead_n:
        score += 18
    if qn and qn in body_n:
        score += 10

    # ngramヒット数（簡易: 正規化テキストにクエリngramがいくつ含まれるか）
    q_toks = _make_ngrams_q(query, max_terms=60)
    title_head = title_n + " " + headings_n
    lead_body = lead_n + " " + body_n
    hit_th = sum(1 for t in q_toks if t in title_head)
    hit_lb = sum(1 for t in q_toks if t in lead_body)
    score += 0.8 * hit_th + 0.2 * hit_lb

    # 連続一致ボーナス
    for field in (title_n, headings_n, lead_n):
        if qn and qn in field:
            score += min(20, len(qn))
            break

    return score


def _resolve_db_path(path: str | None = None) -> str:
    """DB パスを解決。path がなければ CFG.db_path。相対パスは cwd 基準"""
    p = path or CFG.db_path
    if not os.path.isabs(p):
        return os.path.join(os.getcwd(), p)
    return p


def open_db(path: str | None = None) -> sqlite3.Connection:
    resolved = _resolve_db_path(path)
    conn = sqlite3.connect(resolved)
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(SCHEMA)
    return conn


def upsert_page(
    conn: sqlite3.Connection,
    url: str,
    lang: str,
    title: str,
    hpath: str,
    lead: str,
    headings: str,
    body_prefix: str,
    ngrams: str,
    fetched_at: int,
) -> None:
    conn.execute(
        """INSERT INTO pages(url, lang, title, hpath, lead, headings, body_prefix, ngrams, fetched_at)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(url) DO UPDATE SET
             lang=excluded.lang,
             title=excluded.title,
             hpath=excluded.hpath,
             lead=excluded.lead,
             headings=excluded.headings,
             body_prefix=excluded.body_prefix,
             ngrams=excluded.ngrams,
             fetched_at=excluded.fetched_at
        """,
        (url, lang, title, hpath, lead, headings, body_prefix, ngrams, fetched_at),
    )
    conn.commit()


def _is_anchor_noise_en(row: tuple, query: str) -> bool:
    """en-us: URLアンカー #<query> だけで一致、本文に無い → ノイズ"""
    url, title, lead = row[0], row[2], row[4]
    q = query.lower().strip()
    url_l = (url or "").lower()
    title_l = (title or "").lower()
    lead_l = (lead or "").lower()
    anchor_match = f"#{q}" in url_l or url_l.endswith("#" + q.replace(" ", "-"))
    has_content = q in title_l or q in lead_l
    return anchor_match and not has_content


def _sanitize_fts_query(q: str) -> str:
    """FTS5 でエラーになる文字を置換"""
    return q.replace(".", " ").replace(":", " ").replace("-", " ")

def search_index(conn: sqlite3.Connection, query: str, lang: str | None = None, limit: int = 20) -> list[dict]:
    fts_query = _sanitize_fts_query(query)
    if lang == "ja-jp":
        fts_query = _query_to_ngrams_or(query)
        fetch_limit = CANDIDATE_LIMIT
    else:
        fetch_limit = max(limit, 80) if lang == "en-us" else limit

    if lang:
        rows = conn.execute(
            """SELECT url, lang, title, hpath, lead, headings, body_prefix
               FROM pages_fts
               WHERE pages_fts MATCH ? AND lang = ?
               ORDER BY bm25(pages_fts)
               LIMIT ?""",
            (fts_query, lang, fetch_limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT url, lang, title, hpath, lead, headings, body_prefix
               FROM pages_fts
               WHERE pages_fts MATCH ?
               ORDER BY bm25(pages_fts)
               LIMIT ?""",
            (fts_query, fetch_limit),
        ).fetchall()

    def _row_to_hit(r):
        return {
            "url": r[0], "lang": r[1], "title": r[2], "hpath": r[3], "lead": r[4],
            "headings": r[5] if len(r) > 5 else "",
            "body_prefix": r[6] if len(r) > 6 else "",
            "score": None,
        }

    if lang == "ja-jp" and rows:
        scored = [(r, _rescore_ja(r, query)) for r in rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        cut = scored[:limit]
        return [{**_row_to_hit(r), "score": s} for r, s in cut]
    if lang == "en-us" and rows:
        # アンカーのみノイズを後ろに寄せる、他は bm25 順維持
        rows = sorted(rows, key=lambda r: (_is_anchor_noise_en(r, query), 0))[:limit]
    elif lang and len(rows) > limit:
        rows = rows[:limit]

    return [_row_to_hit(r) for r in rows]
