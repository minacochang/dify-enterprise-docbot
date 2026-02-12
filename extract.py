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
