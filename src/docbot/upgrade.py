"""
Dify Helm の Non-Skippable を考慮したアップグレード経路生成。
appVersion 基準。storage/search で release notes を検索。
"""
import re

from docbot.storage import open_db, search_index

# Non-skippable 検索キーワード（FTS5 で column: と解釈されないよう注意）
# 厳しめに限定して過剰マッチを防ぐ
NON_SKIP_KEYWORDS = [
    "non skippable",
    "cannot be skipped",
    "cannot skip",
]

# dify-helm release notes の URL パターン
HELM_RELEASE_URL_RE = re.compile(
    r"langgenius\.github\.io/dify-helm/pages/([a-zA-Z0-9_.-]+)\.md"
)
VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+(?:-\w+(?:\.\d+)?)?)\b")


def _parse_version(ver_str: str) -> tuple:
    """appVersion を比較用タプルに変換。3.6.5 -> (3, 6, 5)"""
    s = ver_str.strip().lower().replace("_", ".")
    if s.startswith("v"):
        s = s[1:]
    base = s.split("-")[0]
    parts = base.split(".")
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    return tuple(out) if out else (0, 0, 0)


def _version_from_url(url: str) -> str | None:
    """URL からバージョンを抽出。pages/3_6_5.md -> 3.6.5"""
    m = HELM_RELEASE_URL_RE.search(url)
    if not m:
        return None
    return m.group(1).replace("_", ".")


def _version_in_range(v: tuple, from_v: tuple, to_v: tuple) -> bool:
    """from < v < to の範囲内か（from/to は含まない）"""
    return from_v < v < to_v


def collect_non_skippable(conn) -> list[dict]:
    """
    storage/search で Non-Skippable キーワードを検索し、
    dify-helm release notes から version / source_url / text を抽出。
    """
    seen_urls = set()
    results = []

    for kw in NON_SKIP_KEYWORDS:
        hits = search_index(conn, kw, lang="en-us", limit=50)
        for h in hits:
            url = h.get("url") or ""
            if "dify-helm" not in url or "/pages/" not in url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            version = _version_from_url(url)
            if not version:
                continue
            text = " ".join(
                filter(None, [
                    h.get("title"),
                    h.get("hpath"),
                    h.get("lead"),
                    h.get("headings"),
                    h.get("body_prefix"),
                ])
            )
            results.append({
                "version": version,
                "version_tuple": _parse_version(version),
                "source_url": url,
                "text": text[:2000],
            })

    return results


def get_all_helm_versions(conn) -> list[dict]:
    """dify-helm release notes の全バージョン一覧を取得（検索で）"""
    # 幅広いクエリで release notes を取得
    hits = search_index(conn, "version release", lang="en-us", limit=100)
    seen = set()
    out = []
    for h in hits:
        url = h.get("url") or ""
        if "dify-helm" not in url or "/pages/" not in url:
            continue
        ver = _version_from_url(url)
        if not ver or ver in seen:
            continue
        seen.add(ver)
        out.append({
            "version": ver,
            "version_tuple": _parse_version(ver),
            "source_url": url,
        })
    out.sort(key=lambda e: e["version_tuple"])
    return out


def _collapse_same_minor(versions: list[str]) -> list[str]:
    """同一 minor 内で最新のみ残す。3.6.4, 3.6.5 → 3.6.5"""
    if len(versions) < 2:
        return versions
    by_minor = {}
    for v in versions:
        t = _parse_version(v)
        minor_key = (t[0], t[1]) if len(t) >= 2 else t
        if minor_key not in by_minor or t > _parse_version(by_minor[minor_key]):
            by_minor[minor_key] = v
    out = list(by_minor.values())
    out.sort(key=_parse_version)
    return out


def compute_upgrade_path(
    from_ver: str, to_ver: str, non_skippable: list[dict]
) -> list[str]:
    """
    経路計算: path = [from] + non_skippables_in_range + [to]
    同一 minor 内は最新のみ残して経路を簡略化。
    to_ver と同一 minor の古い Non-Skippable は除外（直接 to へ）。
    """
    from_t = _parse_version(from_ver)
    to_t = _parse_version(to_ver)
    if from_t >= to_t:
        return []

    to_minor = (to_t[0], to_t[1]) if len(to_t) >= 2 else to_t

    ns_in_range = [
        e["version"] for e in non_skippable
        if _version_in_range(e["version_tuple"], from_t, to_t)
    ]
    ns_in_range = list(dict.fromkeys(ns_in_range))
    ns_in_range.sort(key=lambda v: _parse_version(v))
    ns_in_range = _collapse_same_minor(ns_in_range)

    # to_ver と同一 minor の古い版を除外（3.6.4 を捨て 3.6.5 へ直行）
    ns_in_range = [
        v for v in ns_in_range
        if _parse_version(v)[:2] != to_minor or v == to_ver
    ]

    path = [from_ver] + ns_in_range
    if not path or path[-1] != to_ver:
        path.append(to_ver)
    return path


def extract_hop_steps(conn, from_ver: str, to_ver: str, lang: str) -> tuple[list[str], list[str]]:
    """
    Hop from_ver -> to_ver の作業を検索で抽出。
    return: (bullets, source_urls)
    """
    source_urls = []
    bullets = []
    seen_bullets = set()

    for q in [f"{to_ver} upgrade", to_ver]:
        hits = search_index(conn, q, lang=lang or "en-us", limit=20)
        for h in hits:
            url = h.get("url") or ""
            if "dify-helm" not in url or "/pages/" not in url:
                continue
            hit_ver = _version_from_url(url)
            if not hit_ver or _parse_version(hit_ver) != _parse_version(to_ver):
                continue
            if url not in source_urls:
                source_urls.append(url)

            text = " ".join(filter(None, [
                h.get("lead"),
                h.get("headings"),
                h.get("body_prefix"),
            ]))
            # 箇条書き・番号付き・imperative 文を抽出
            skip_starts = ("Dify Community:", "Base on ", "https://")
            for line in re.split(r"[\n.]", text):
                s = line.strip()
                if len(s) < 15 or len(s) > 300:
                    continue
                clean = re.sub(r"^[\d\-*•·]+\s*", "", s).strip()
                if not clean or any(clean.startswith(p) for p in skip_starts):
                    continue
                # 重複スキップ
                key = clean[:80].lower()
                if key in seen_bullets:
                    continue
                seen_bullets.add(key)
                if clean and (clean[0].isupper() or clean.startswith("-")):
                    bullets.append(clean[:250])

    return bullets[:12], list(dict.fromkeys(source_urls))


def format_upgrade_markdown(
    path: list[str],
    hop_bullets: dict[tuple[str, str], list[str]],
    hop_sources: dict[tuple[str, str], list[str]],
) -> str:
    """Markdown 出力を生成"""
    lines = []
    lines.append("Upgrade path:")
    lines.append(" → ".join(path))
    lines.append("")

    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        hop = (a, b)
        lines.append(f"## Hop {i + 1}: {a} → {b}")
        bullets = hop_bullets.get(hop, [])
        if bullets:
            for bl in bullets:
                lines.append(f"- {bl}")
        else:
            lines.append("- (release notes を確認してください)")
        lines.append("")
        lines.append("Sources:")
        for src in hop_sources.get(hop, []):
            lines.append(f"- {src}")
        lines.append("")

    return "\n".join(lines)


def run_upgrade(from_ver: str, to_ver: str, lang: str = "en-us") -> int:
    """
    upgrade 処理のメイン。storage を直接利用。
    """
    conn = open_db()

    non_skippable = collect_non_skippable(conn)
    if not non_skippable:
        # フォールバック: sidebar から取得するか、全バージョンから特定
        all_vers = get_all_helm_versions(conn)
        if not all_vers:
            print("ERROR: release notes が検索対象に含まれていません。")
            print("python -m docbot.ingest を実行してから再度お試しください。")
            conn.close()
            return 1
        # キーワード検索でヒットしなかった場合は、既知の Non-Skippable を使用
        known_ns = {"2.3.0", "2.8.0", "3.2.2", "3.6.5", "3.7.3"}
        non_skippable = [
            {"version": v, "version_tuple": _parse_version(v), "source_url": "", "text": ""}
            for e in all_vers for v in [e["version"]]
            if v in known_ns
        ]

    path = compute_upgrade_path(from_ver, to_ver, non_skippable)
    if not path:
        print(f"ERROR: アップグレード経路を計算できませんでした（--from {from_ver} --to {to_ver}）")
        print("from は to より小さいバージョンを指定してください。")
        conn.close()
        return 1

    hop_bullets = {}
    hop_sources = {}

    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        bullets, sources = extract_hop_steps(conn, a, b, lang)
        hop_bullets[(a, b)] = bullets
        hop_sources[(a, b)] = sources

    conn.close()

    md = format_upgrade_markdown(path, hop_bullets, hop_sources)
    print(md)
    return 0
