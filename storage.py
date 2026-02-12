import sqlite3


def _make_ngrams(text: str, ns: tuple[int, ...] = (2, 3), limit: int = 60) -> list[str]:
    """検索クエリ用: 日本語テキストをN-gramトークンに分割（トークン数制限）"""
    s = "".join(text.split())
    toks: list[str] = []
    for n in ns:
        if len(s) < n:
            continue
        for i in range(len(s) - n + 1):
            toks.append(s[i : i + n])
            if len(toks) >= limit:
                return toks
    return toks


def _query_to_ngrams_or(query: str, limit: int = 60) -> str:
    """lang=ja-jp 時に FTS MATCH 用の OR クエリを生成。既存 title/hpath/lead も対象なので OR で緩く当てる"""
    toks = _make_ngrams(query, ns=(2, 3), limit=limit)
    if not toks:
        return query  # 1文字だけ等のフォールバック
    # FTS5: フレーズは "..." で囲む。単語はそのまま。OR 結合
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
  ngrams TEXT,
  fetched_at INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts
USING fts5(url, lang, title, hpath, lead, ngrams, content='pages', content_rowid='rowid');

CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
  INSERT INTO pages_fts(rowid, url, lang, title, hpath, lead, ngrams)
  VALUES (new.rowid, new.url, new.lang, new.title, new.hpath, new.lead, new.ngrams);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
  INSERT INTO pages_fts(pages_fts, rowid, url, lang, title, hpath, lead, ngrams)
  VALUES ('delete', old.rowid, old.url, old.lang, old.title, old.hpath, old.lead, old.ngrams);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
  INSERT INTO pages_fts(pages_fts, rowid, url, lang, title, hpath, lead, ngrams)
  VALUES ('delete', old.rowid, old.url, old.lang, old.title, old.hpath, old.lead, old.ngrams);
  INSERT INTO pages_fts(rowid, url, lang, title, hpath, lead, ngrams)
  VALUES (new.rowid, new.url, new.lang, new.title, new.hpath, new.lead, new.ngrams);
END;
"""

def open_db(path: str = "index.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(SCHEMA)
    return conn

def upsert_page(conn, url, lang, title, hpath, lead, ngrams, fetched_at):
    conn.execute(
        """INSERT INTO pages(url, lang, title, hpath, lead, ngrams, fetched_at)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(url) DO UPDATE SET
             lang=excluded.lang,
             title=excluded.title,
             hpath=excluded.hpath,
             lead=excluded.lead,
             ngrams=excluded.ngrams,
             fetched_at=excluded.fetched_at
        """,
        (url, lang, title, hpath, lead, ngrams, fetched_at),
    )
    conn.commit()


def search_index(conn: sqlite3.Connection, query: str, lang: str | None = None, limit: int = 20) -> list[dict]:
    fts_query = query
    if lang == "ja-jp":
        fts_query = _query_to_ngrams_or(query)

    if lang:
        rows = conn.execute(
            """SELECT url, lang, title, hpath, lead
               FROM pages_fts
               WHERE pages_fts MATCH ? AND lang = ?
               ORDER BY bm25(pages_fts)
               LIMIT ?""",
            (fts_query, lang, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT url, lang, title, hpath, lead
               FROM pages_fts
               WHERE pages_fts MATCH ?
               ORDER BY bm25(pages_fts)
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()

    return [{"url": r[0], "lang": r[1], "title": r[2], "hpath": r[3], "lead": r[4]} for r in rows]
