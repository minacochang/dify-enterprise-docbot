from bs4 import BeautifulSoup
from readability import Document

def extract_index_fields(html: str) -> tuple[str, str, str]:
    """
    索引用：title + h1-h3 + lead(冒頭)
    """
    doc = Document(html)
    title = (doc.short_title() or "").strip()

    main_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(main_html, "lxml")

    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        t = tag.get_text(" ", strip=True)
        if t:
            headings.append(t)
    hpath = " | ".join(headings[:60])

    lead = ""
    for p in soup.find_all(["p", "li"]):
        t = p.get_text(" ", strip=True)
        if t:
            lead = t
            break
    lead = lead[:600]

    return title, hpath, lead


def extract_headings_and_body_prefix(html: str, body_prefix_len: int = 4000) -> tuple[str, str]:
    """
    ja-jp 検索用：h2/h3 見出しと本文先頭を抽出。
    headings: h2,h3 のテキストを | で結合
    body_prefix: 本文（p,li等）の先頭 N 文字
    """
    doc = Document(html)
    main_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(main_html, "lxml")

    headings_parts = []
    for tag in soup.find_all(["h2", "h3"]):
        t = tag.get_text(" ", strip=True)
        if t:
            headings_parts.append(t)
    headings = " | ".join(headings_parts[:60])

    body_parts = []
    for el in soup.find_all(["p", "li", "td", "th"]):
        t = el.get_text(" ", strip=True)
        if t:
            body_parts.append(t)
            if sum(len(x) for x in body_parts) >= body_prefix_len:
                break
    body_prefix = " ".join(body_parts)[:body_prefix_len]

    return headings, body_prefix


def extract_index_fields_markdown(md: str) -> tuple[str, str, str]:
    """
    Markdown から索引用フィールドを抽出（Helm release notes 用）
    """
    lines = md.split("\n")
    title = ""
    headings_parts = []
    lead_parts = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("# "):
            title = s.lstrip("# ").strip()[:200]
        elif s.startswith("## ") or s.startswith("### "):
            h = s.lstrip("# ").strip()
            if h and len(headings_parts) < 60:
                headings_parts.append(h)
        elif len(lead_parts) < 3 and len(" ".join(lead_parts)) < 600:
            lead_parts.append(s[:300])

    hpath = " | ".join(headings_parts[:60])
    lead = " ".join(lead_parts)[:600]
    return title, hpath, lead


def extract_headings_and_body_prefix_markdown(md: str, body_prefix_len: int = 4000) -> tuple[str, str]:
    """Markdown から headings と body_prefix を抽出"""
    lines = md.split("\n")
    headings_parts = []
    body_parts = []
    total = 0

    for line in lines:
        s = line.strip()
        if s.startswith("## ") or s.startswith("### "):
            h = s.lstrip("# ").strip()
            if h and len(headings_parts) < 60:
                headings_parts.append(h)
        elif s and not s.startswith("#") and total < body_prefix_len:
            body_parts.append(s)
            total += len(s) + 1

    headings = " | ".join(headings_parts[:60])
    body_prefix = " ".join(body_parts)[:body_prefix_len]
    return headings, body_prefix


def extract_main_text_with_headings(html: str) -> list[dict]:
    """
    QA用：見出し単位で本文をセクション化
    return: [{"heading": "...", "text": "..."}, ...]
    """
    doc = Document(html)
    main_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(main_html, "lxml")

    sections = []
    cur = {"heading": "INTRO", "text": []}

    for el in soup.find_all(["h1", "h2", "h3", "p", "li", "code", "pre"]):
        name = el.name.lower()
        if name in ("h1", "h2", "h3"):
            if cur["text"]:
                sections.append({"heading": cur["heading"], "text": "\n".join(cur["text"]).strip()})
            cur = {"heading": el.get_text(" ", strip=True)[:200], "text": []}
        else:
            t = el.get_text(" ", strip=True)
            if t:
                cur["text"].append(t)

    if cur["text"]:
        sections.append({"heading": cur["heading"], "text": "\n".join(cur["text"]).strip()})

    return [s for s in sections if s["text"]]
