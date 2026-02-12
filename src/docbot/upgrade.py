"""
Dify Helm の Non-Skippable を考慮したアップグレード経路生成。
"""
import re

import httpx

from docbot.config import CFG

UA = {"User-Agent": "docbot/0.1 (+local)"}
HELM_SIDEBAR_URL = f"{CFG.helm_release_base}/_sidebar.md"

# Non-skippable 検出用キーワード（本文）
NON_SKIP_KEYWORDS = (
    "non-skippable", "non skippable", "cannot be skipped", "cannot skip",
    "must upgrade", "required step", "required for future upgrades",
)


def _parse_version(ver_str: str) -> tuple:
    """
    バージョン文字列を比較用タプルに変換。
    "3.6.5" -> (3, 6, 5), "3.6.0-beta.1" -> (3, 6, 0)
    """
    s = ver_str.strip().lower().replace("_", ".")
    if s.startswith("v"):
        s = s[1:]
    # -beta, -fix 以降は無視して数字部分のみ比較
    base = s.split("-")[0]
    parts = base.split(".")
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    return tuple(out) if out else (0, 0, 0)


def _version_in_range(v: tuple, from_v: tuple, to_v: tuple) -> bool:
    """v が from <= v <= to の範囲内か"""
    return from_v <= v <= to_v


def fetch_sidebar() -> str | None:
    """_sidebar.md を取得"""
    try:
        r = httpx.get(HELM_SIDEBAR_URL, headers=UA, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def parse_sidebar(sidebar: str) -> list[dict]:
    """
    _sidebar.md をパースして、バージョン一覧と Non-skippable を取得。
    return: [{"version": "3.6.5", "version_tuple": (3,6,5), "url": "...", "non_skippable": bool}, ...]
    並びは新しい順（3.7.5 が先頭）
    """
    # /pages/XXX.md を抽出。ラベルは行全体から取得（ネストした [] 対応）
    pattern = re.compile(r"/pages/([a-zA-Z0-9_.-]+)\.md")
    entries = []
    seen = set()
    for line in sidebar.split("\n"):
        m = pattern.search(line)
        if not m:
            continue
        page_id = m.group(1)
        if page_id in seen:
            continue
        seen.add(page_id)
        # 行から vX.Y.Z と Non-skippable を抽出
        ver_match = re.search(r"v([\d.]+(?:-\w+(?:\.\d+)?)?)", line, re.I)
        version = ver_match.group(1).replace("_", ".") if ver_match else page_id.replace("_", ".")
        non_skippable = "non-skippable" in line.lower() or "non skippable" in line.lower()
        url = f"{CFG.helm_release_base}/pages/{page_id}.md"
        entries.append({
            "version": version,
            "version_tuple": _parse_version(version),
            "url": url,
            "non_skippable": non_skippable,
            "page_id": page_id,
        })
    return entries


def compute_upgrade_path(
    entries: list[dict], from_ver: str, to_ver: str
) -> list[dict] | None:
    """
    from_ver から to_ver へのアップグレード経路を計算。
    Non-skippable を必ず含む。範囲外の場合は None。
    """
    from_t = _parse_version(from_ver)
    to_t = _parse_version(to_ver)
    if from_t > to_t:
        return None

    # 範囲内のバージョンを抽出、古い順にソート
    in_range = [
        e for e in entries
        if _version_in_range(e["version_tuple"], from_t, to_t)
    ]
    in_range.sort(key=lambda e: e["version_tuple"])

    # Non-skippable が範囲内にあって経路に含まれていなければ追加
    non_skip_in_range = [e for e in in_range if e["non_skippable"]]
    path = in_range  # 全経由でOK（すでに Non-skippable 含む）
    return path


def fetch_release_notes(url: str) -> str | None:
    """release notes の本文を取得"""
    try:
        r = httpx.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def extract_key_steps(md: str) -> list[str]:
    """
    release notes 本文から主な作業・手順を箇条書きで抽出。
    Upgrade Handbook, ## Warning, 手順番号 等を優先。
    """
    lines = md.split("\n")
    steps = []
    in_upgrade = False
    in_warning = False

    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        lower = s.lower()
        if "upgrade handbook" in lower or "upgrade guide" in lower:
            in_upgrade = True
            continue
        if "warning" in lower and ("#" in line or "##" in line):
            in_warning = True
            steps.append(s[:200])
            continue
        if in_upgrade or in_warning:
            if s.startswith(("#", "##", "###")):
                if in_upgrade and not s.lower().startswith("## assets"):
                    steps.append(s[:200])
            elif re.match(r"^\d+\.", s) or s.startswith("- ") or s.startswith("* "):
                clean = re.sub(r"^\d+\.\s*", "", s).strip()
                if clean and len(clean) > 10:
                    steps.append(clean[:300])
            elif "non-skippable" in lower or "cannot be skipped" in lower:
                steps.append(s[:200])
        if "## Assets" in s or "## Reports" in s:
            in_upgrade = False

    if not steps:
        for line in lines:
            s = line.strip()
            if "non-skippable" in s.lower() or "must run" in s.lower() or "migration" in s.lower():
                steps.append(s[:200])
            if "helm upgrade" in s.lower() or "flask" in s.lower():
                steps.append(s[:200])

    return steps[:15]
