import sqlite3

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS pages (
  url TEXT PRIMARY KEY,
  lang TEXT NOT NULL,
  title TEXT,
  hpath TEXT,
  lead TEXT,
  fetched_at INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts
USING fts5(
  url, lang, title, hpath, lead,
  content='pages', content_rowid='rowid',
  tokenize='trigram'
);


CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
  INSERT INTO pages_fts(rowid, url, lang, title, hpath, lead)
  VALUES (new.rowid, new.url, new.lang, new.title, new.hpath, new.lead);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
  INSERT INTO pages_fts(pages_fts, rowid, url, lang, title, hpath, lead)
  VALUES ('delete', old.rowid, old.url, old.lang, old.title, old.hpath, old.lead);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
  INSERT INTO pages_fts(pages_fts, rowid, url, lang, title, hpath, lead)
  VALUES ('delete', old.rowid, old.url, old.lang, old.title, old.hpath, old.lead);
  INSERT INTO pages_fts(rowid, url, lang, title, hpath, lead)
  VALUES (new.rowid, new.url, new.lang, new.title, new.hpath, new.lead);
END;
"""

def open_db(path: str = "index.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(SCHEMA)
    return conn

def upsert_page(conn: sqlite3.Connection, url: str, lang: str, title: str, hpath: str, lead: str, fetched_at: int) -> None:
    conn.execute(
        """INSERT INTO pages(url, lang, title, hpath, lead, fetched_at)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(url) DO UPDATE SET
             lang=excluded.lang,
             title=excluded.title,
             hpath=excluded.hpath,
             lead=excluded.lead,
             fetched_at=excluded.fetched_at
        """,
        (url, lang, title, hpath, lead, fetched_at),
    )
    conn.commit()

def search_index(conn: sqlite3.Connection, query: str, lang: str | None = None, limit: int = 20) -> list[dict]:
    if lang:
        rows = conn.execute(
            """SELECT url, lang, title, hpath, lead
               FROM pages_fts
               WHERE pages_fts MATCH ? AND lang = ?
               ORDER BY bm25(pages_fts)
               LIMIT ?""",
            (query, lang, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT url, lang, title, hpath, lead
               FROM pages_fts
               WHERE pages_fts MATCH ?
               ORDER BY bm25(pages_fts)
               LIMIT ?""",
            (query, limit),
        ).fetchall()

    return [{"url": r[0], "lang": r[1], "title": r[2], "hpath": r[3], "lead": r[4]} for r in rows]
