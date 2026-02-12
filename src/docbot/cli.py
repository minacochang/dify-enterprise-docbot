#!/usr/bin/env python3
"""docbot CLI: search / compose / helm"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

DEFAULT_BASE = "http://127.0.0.1:8000"
DIFY_COMPOSE_URL = "https://raw.githubusercontent.com/langgenius/dify/main/docker/docker-compose.yaml"
DIFY_HELM_REPO = "https://langgenius.github.io/dify-helm"
DIFY_HELM_CHART = "dify"


def _compose_url_from_hits(hits: list) -> str | None:
    """検索結果から docker-compose.yaml/yml のURLを探す"""
    for h in hits:
        url = (h.get("url") or "").strip()
        if "docker-compose.yaml" in url or "docker-compose.yml" in url:
            return url
    return None


def _fetch_compose_yaml(url: str) -> dict | None:
    """URLから YAML を取得してパース"""
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True, verify=True)
        r.raise_for_status()
        return yaml.safe_load(r.text)
    except Exception:
        try:
            r = httpx.get(url, timeout=15, follow_redirects=True, verify=False)
            r.raise_for_status()
            return yaml.safe_load(r.text)
        except Exception:
            return None


def _extract_services(data: dict) -> list[dict]:
    """services 以下を抽出"""
    services = data.get("services") or {}
    rows = []
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        image = svc.get("image") or ""
        ports = svc.get("ports") or []
        if isinstance(ports, list):
            ports = [str(p) for p in ports[:5]]
        else:
            ports = [str(ports)]
        dep = svc.get("depends_on")
        if isinstance(dep, list):
            dep = ", ".join(str(d) for d in dep[:5])
        elif isinstance(dep, dict):
            dep = ", ".join(dep.keys())[:80]
        else:
            dep = str(dep)[:80] if dep else ""
        vols = svc.get("volumes") or []
        if isinstance(vols, list):
            vols = [str(v) for v in vols[:3]]
        else:
            vols = [str(vols)]
        rows.append({
            "name": name,
            "image": image[:60] + ("…" if len(image) > 60 else ""),
            "ports": " | ".join(ports) if ports else "",
            "depends_on": dep,
            "volumes": " | ".join(vols) if vols else "",
        })
    return rows


def _format_table(rows: list[dict]) -> str:
    """Markdown table で出力"""
    if not rows:
        return ""
    keys = ["name", "image", "ports", "depends_on", "volumes"]
    headers = ["service", "image", "ports", "depends_on", "volumes"]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for r in rows:
        cells = [str(r.get(k, ""))[:50] for k in keys]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run_compose(base: str, query: str, lang: str | None, limit: int) -> int:
    """compose サブコマンド"""
    url = base.rstrip("/") + "/search"
    payload = {"query": query, "lang": lang, "limit": limit}
    try:
        r = httpx.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"ERROR: failed to call {url}: {e}", file=sys.stderr)
        return 1

    hits = (r.json()).get("hits") or []
    compose_url = _compose_url_from_hits(hits)

    if not compose_url:
        compose_url = DIFY_COMPOSE_URL
        if hits:
            titles = [h.get("title") or "" for h in hits[:3]]
            if any("Docker Compose" in t or "docker" in t.lower() for t in titles):
                pass
            else:
                compose_url = None
        else:
            compose_url = None

    if not compose_url:
        print("0件。検索対象フィールド/言語を確認")
        print("docker-compose.yaml への直接URLも見つかりませんでした。")
        return 0

    data = _fetch_compose_yaml(compose_url)
    if not data:
        print("取得できませんでした")
        return 0

    rows = _extract_services(data)
    if not rows:
        print("取得できませんでした（services なし）")
        return 0

    print(f"Source: {compose_url}\n")
    print(_format_table(rows))
    return 0


# --- Helm ---

def _helm_chart_url_from_hits(hits: list) -> str | None:
    clues = ("dify-helm", "helm chart", "values.yaml", ".tgz", "index.yaml")
    for h in hits:
        url = ((h.get("url") or "") + " " + (h.get("title") or "")).lower()
        if any(c in url for c in clues):
            u = (h.get("url") or "").strip()
            if u and (".tgz" in u or "index.yaml" in u):
                return u
    return None


def _is_tgz_url(url: str) -> bool:
    return ".tgz" in url


def _fetch_tgz(url: str, dest_dir: Path) -> Path | None:
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True)
        r.raise_for_status()
        tgz_path = dest_dir / "chart.tgz"
        tgz_path.write_bytes(r.content)
        with tarfile.open(tgz_path, "r:gz") as tf:
            members = tf.getmembers()
            tf.extractall(dest_dir, members)
        subdirs = [d for d in dest_dir.iterdir() if d.is_dir()]
        return subdirs[0] if subdirs else dest_dir
    except Exception:
        return None


def _fetch_chart_from_repo(
    repo_url: str, chart_name: str, dest_dir: Path, version: str | None = None
) -> Path | None:
    base = repo_url.rstrip("/")
    index_url = f"{base}/index.yaml"
    try:
        r = httpx.get(index_url, timeout=15)
        r.raise_for_status()
        idx = yaml.safe_load(r.text)
    except Exception:
        return None
    entries = idx.get("entries") or {}
    charts = entries.get(chart_name) or []
    if not charts:
        return None
    target = None
    if version:
        for entry in charts:
            if str(entry.get("version", "")) == version:
                target = entry
                break
        if target is None:
            return None
    else:
        target = charts[0]
    urls = target.get("urls") or []
    if not urls:
        return None
    tgz_name = urls[0] if isinstance(urls[0], str) else urls[0].get("url", "")
    chart_url = tgz_name if tgz_name.startswith("http") else f"{base}/{tgz_name}"
    return _fetch_tgz(chart_url, dest_dir)


def _helm_repo_add_and_pull(
    repo_name: str, repo_url: str, chart_name: str, dest_dir: Path, version: str | None = None
) -> Path | None:
    chart_dir = _fetch_chart_from_repo(repo_url, chart_name, dest_dir, version)
    if chart_dir:
        return chart_dir
    try:
        subprocess.run(["helm", "repo", "add", repo_name, repo_url], check=True, capture_output=True, timeout=30)
        subprocess.run(["helm", "repo", "update"], check=True, capture_output=True, timeout=60)
        cmd = ["helm", "pull", f"{repo_name}/{chart_name}", "--untar", "--untardir", str(dest_dir)]
        if version:
            cmd.extend(["--version", version])
        result = subprocess.run(cmd, capture_output=True, timeout=60, text=True)
        if result.returncode != 0:
            return None
        subdirs = [d for d in dest_dir.iterdir() if d.is_dir()]
        return subdirs[0] if subdirs else dest_dir
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        return None


_DIFY_HELM_DEFAULT_SET = [
    "postgresql.enabled=true",
    "postgresql.global.postgresql.auth.postgresPassword=placeholder",
    "redis.enabled=true",
    "redis.global.redis.password=placeholder",
]


def _run_helm_template(
    chart_dir: Path, release: str, namespace: str,
    values_path: Path | None, set_args: list[str]
) -> str | None:
    cmd = ["helm", "template", release, str(chart_dir), "--namespace", namespace]
    if values_path and values_path.exists():
        cmd.extend(["--values", str(values_path)])
    for s in _DIFY_HELM_DEFAULT_SET:
        cmd.extend(["--set", s])
    for s in set_args:
        cmd.extend(["--set", s])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return None
        return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _extract_workloads(yaml_text: str) -> list[dict]:
    rows = []
    for doc in yaml.safe_load_all(yaml_text):
        if not isinstance(doc, dict):
            continue
        kind = doc.get("kind") or ""
        if kind not in ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"):
            continue
        meta = doc.get("metadata") or {}
        name = meta.get("name") or ""
        spec = doc.get("spec") or {}
        template = spec.get("template") or {}
        pod_spec = template.get("spec") or {}
        containers = pod_spec.get("containers") or []

        replicas = str(spec.get("replicas")) if spec.get("replicas") is not None else "-"

        images = []
        ports = []
        env_keys = []
        vols = []
        res_req = ""
        res_lim = ""
        for c in containers:
            img = c.get("image") or ""
            if img:
                images.append(img[:50] + ("…" if len(img) > 50 else ""))
            for p in c.get("ports") or []:
                if isinstance(p, dict):
                    ports.append(str(p.get("containerPort", p.get("port", ""))))
                else:
                    ports.append(str(p))
            for e in c.get("env") or []:
                if isinstance(e, dict) and e.get("name"):
                    env_keys.append(e["name"])
            for v in c.get("volumeMounts") or []:
                if isinstance(v, dict) and v.get("name"):
                    vols.append(v["name"])
            res = c.get("resources") or {}
            req, lim = res.get("requests") or {}, res.get("limits") or {}
            if req:
                res_req += f"cpu:{req.get('cpu','-')} mem:{req.get('memory','-')} "
            if lim:
                res_lim += f"cpu:{lim.get('cpu','-')} mem:{lim.get('memory','-')} "

        for v in pod_spec.get("volumes") or []:
            if isinstance(v, dict) and v.get("name"):
                vtype = "pvc" if "persistentVolumeClaim" in v else "cfg" if "configMap" in v else "secret" if "secret" in v else "emptyDir" if "emptyDir" in v else "?"
                vols.append(f"{v['name']}({vtype})")

        rows.append({
            "kind": kind, "name": name, "replicas": replicas,
            "images": " | ".join(images[:3]) if images else "",
            "ports": " | ".join(ports[:5]) if ports else "",
            "env": ", ".join(env_keys[:5]) if env_keys else "",
            "volumes": " | ".join(vols[:3]) if vols else "",
            "resources": (res_req.strip() or "-") + " / " + (res_lim.strip() or "-"),
        })
    return rows


def _extract_k8s_services(yaml_text: str) -> list[dict]:
    rows = []
    for doc in yaml.safe_load_all(yaml_text):
        if not isinstance(doc, dict) or doc.get("kind") != "Service":
            continue
        meta = doc.get("metadata") or {}
        name = meta.get("name") or ""
        spec = doc.get("spec") or {}
        svc_type = spec.get("type") or "ClusterIP"
        ports = []
        for p in spec.get("ports") or []:
            if isinstance(p, dict):
                ports.append(f"{p.get('port','')}:{p.get('targetPort','')}")
            else:
                ports.append(str(p))
        selector = spec.get("selector") or {}
        sel = ", ".join(f"{k}={v}" for k, v in list(selector.items())[:3]) if selector else ""
        rows.append({
            "name": name,
            "type": svc_type,
            "ports": " | ".join(ports[:5]) if ports else "",
            "selector": sel[:60] + ("…" if len(sel) > 60 else ""),
        })
    return rows


def _extract_ingresses(yaml_text: str) -> list[dict]:
    rows = []
    for doc in yaml.safe_load_all(yaml_text):
        if not isinstance(doc, dict) or doc.get("kind") != "Ingress":
            continue
        meta = doc.get("metadata") or {}
        name = meta.get("name") or ""
        spec = doc.get("spec") or {}
        rules = spec.get("rules") or []
        hosts = [r.get("host", "") for r in rules if r.get("host")]
        rows.append({"name": name, "hosts": " | ".join(hosts[:3]) if hosts else ""})
    return rows


def _format_helm_table(rows: list[dict], headers: list[str], keys: list[str]) -> str:
    if not rows:
        return ""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for r in rows:
        cells = [str(r.get(k, ""))[:60] for k in keys]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _read_chart_metadata(chart_dir: Path) -> dict:
    """Chart.yaml から version / appVersion / name を取得"""
    meta = {"name": "", "version": "", "appVersion": ""}
    chart_yaml = chart_dir / "Chart.yaml"
    if not chart_yaml.exists():
        return meta
    try:
        data = yaml.safe_load(chart_yaml.read_text())
        if data:
            meta["name"] = str(data.get("name") or "")
            meta["version"] = str(data.get("version") or "")
            meta["appVersion"] = str(data.get("appVersion") or "")
    except Exception:
        pass
    return meta


def _resolve_local_chart(chart_path: str, dest_dir: Path) -> Path | None:
    """ローカル .tgz または展開済みディレクトリを解決して chart ディレクトリを返す"""
    p = Path(chart_path).resolve()
    if not p.exists():
        return None
    if p.is_dir():
        if (p / "Chart.yaml").exists():
            return p
        return None
    if p.suffix == ".tgz" or str(p).endswith(".tgz"):
        try:
            with tarfile.open(p, "r:gz") as tf:
                tf.extractall(dest_dir)
            subdirs = [d for d in dest_dir.iterdir() if d.is_dir()]
            for d in subdirs:
                if (d / "Chart.yaml").exists():
                    return d
            return subdirs[0] if subdirs else dest_dir
        except Exception:
            return None
    return None


def _format_helm_metadata(
    chart_name: str, chart_version: str, app_version: str,
    values_source: str | None, source: str
) -> str:
    rendered_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"- **Chart**: {chart_name} {chart_version}" if chart_version else f"- **Chart**: {chart_name}",
        f"- **AppVersion**: {app_version}" if app_version else "- **AppVersion**: -",
        f"- **Values**: {values_source}" if values_source else "- **Values**: -",
        f"- **RenderedAt**: {rendered_at}",
        f"- **Source**: {source}",
    ]
    return "\n".join(lines) + "\n"


def _fetch_values_if_url(values_arg: str | None, dest_dir: Path) -> Path | None:
    if not values_arg:
        return None
    if values_arg.startswith(("http://", "https://")):
        try:
            r = httpx.get(values_arg, timeout=15)
            r.raise_for_status()
            p = dest_dir / "values.yaml"
            p.write_text(r.text)
            return p
        except Exception:
            return None
    p = Path(values_arg)
    return p if p.exists() else None


def run_helm(
    base: str, query: str, lang: str | None, limit: int,
    namespace: str, release: str, values_arg: str | None, set_args: list[str],
    chart_path: str | None = None, chart_version: str | None = None,
) -> int:
    if not shutil.which("helm"):
        print("helm が必要です。https://helm.sh でインストールしてください。")
        return 1

    with tempfile.TemporaryDirectory(prefix="docbot-helm-") as tmp:
        tmp_path = Path(tmp)
        values_path = _fetch_values_if_url(values_arg, tmp_path)
        if values_path is None and values_arg:
            values_path = Path(values_arg) if Path(values_arg).exists() else None

        chart_dir: Path | None = None
        source_msg = ""

        if chart_path:
            chart_dir = _resolve_local_chart(chart_path, tmp_path)
            if chart_dir:
                source_msg = str(Path(chart_path).resolve())
            if not chart_dir:
                print(f"ERROR: --chart で指定したパスが無効です: {chart_path}")
                return 1

        if chart_dir is None:
            url = base.rstrip("/") + "/search"
            payload = {"query": query, "lang": lang, "limit": limit}
            hits = []
            try:
                r = httpx.post(url, json=payload, timeout=10)
                r.raise_for_status()
                hits = (r.json()).get("hits") or []
            except Exception as e:
                print(f"Note: search failed ({e}), using fallback chart.", file=sys.stderr)
            chart_url = _helm_chart_url_from_hits(hits)

            repo_url = DIFY_HELM_REPO
            if chart_url and ("index.yaml" in chart_url or "dify-helm" in chart_url):
                repo_url = chart_url.split("/index.yaml")[0] if "index.yaml" in chart_url else DIFY_HELM_REPO
            if not chart_version and chart_url and _is_tgz_url(chart_url):
                chart_dir = _fetch_tgz(chart_url, tmp_path)
                source_msg = chart_url
            if chart_dir is None:
                chart_dir = _helm_repo_add_and_pull("dify-helm", repo_url, DIFY_HELM_CHART, tmp_path, chart_version)
                source_msg = f"{repo_url} (chart: {DIFY_HELM_CHART})"
            if chart_dir is None and chart_version:
                print(f"ERROR: 指定した chart version を取得できませんでした: {chart_version}")
                print("利用可能なバージョンは index.yaml で確認してください。")
                return 1

        if not chart_dir or not (chart_dir / "Chart.yaml").exists():
            if chart_version:
                print(f"ERROR: chart version {chart_version} が取得できませんでした。")
                return 1
            print("取得できませんでした（チャートの取得に失敗）")
            return 0

        meta = _read_chart_metadata(chart_dir)
        chart_name = meta.get("name") or DIFY_HELM_CHART
        chart_ver = meta.get("version") or ""
        app_ver = meta.get("appVersion") or ""
        values_source = None
        if values_arg:
            values_source = values_arg if values_arg.startswith("http") else str(Path(values_arg).resolve())

        yaml_out = _run_helm_template(chart_dir, release, namespace, values_path, set_args)
        if not yaml_out:
            print("helm template 失敗")
            return 0

        workloads = _extract_workloads(yaml_out)
        services = _extract_k8s_services(yaml_out)
        ingresses = _extract_ingresses(yaml_out)

        print(_format_helm_metadata(chart_name, chart_ver, app_ver, values_source, source_msg))
        if workloads:
            print("## Workloads (Deployment / StatefulSet / DaemonSet / Job / CronJob)\n")
            print(_format_helm_table(workloads, ["kind", "name", "replicas", "images", "ports", "env", "volumes", "resources"], ["kind", "name", "replicas", "images", "ports", "env", "volumes", "resources"]))
            print()
        if services:
            print("## Services\n")
            print(_format_helm_table(services, ["name", "type", "ports", "selector"], ["name", "type", "ports", "selector"]))
            print()
        if ingresses:
            print("## Ingresses\n")
            print(_format_helm_table(ingresses, ["name", "hosts"], ["name", "hosts"]))

        if not workloads and not services and not ingresses:
            print("取得できませんでした（レンダリング結果に該当リソースなし）")

    return 0


def run_stats(db_path: str | None = None) -> int:
    """DB のサイズとページ数を表示"""
    from docbot.storage import open_db
    from docbot.config import CFG

    path = db_path or CFG.db_path
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    if not os.path.exists(path):
        print(f"DB が存在しません: {path}")
        print("python -m docbot.ingest を実行してインデックスを作成してください。")
        return 1

    total = os.path.getsize(path)
    size_str = f"{total:,} B"
    for unit, div in [("KB", 1024), ("MB", 1024**2), ("GB", 1024**3)]:
        val = total / div
        if val >= 1:
            size_str = f"{val:.1f} {unit}"
            break

    conn = open_db(db_path)
    cnt = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    by_lang = dict(conn.execute("SELECT lang, COUNT(*) FROM pages GROUP BY lang").fetchall())
    conn.close()

    print(f"DB: {path}")
    print(f"Size: {size_str}")
    print(f"Pages: {cnt}")
    for lang, n in sorted(by_lang.items()):
        print(f"  - {lang}: {n}")
    return 0


def run_upgrade(from_ver: str, to_ver: str, lang: str = "en-us") -> int:
    """Non-Skippable を考慮したアップグレード経路を表示（appVersion 基準）"""
    from docbot.upgrade import run_upgrade as _run_upgrade
    return _run_upgrade(from_ver, to_ver, lang)


def run_search(base: str, query: str, lang: str | None, limit: int, as_json: bool) -> int:
    url = base.rstrip("/") + "/search"
    payload = {"query": query, "lang": lang, "limit": limit}
    try:
        r = httpx.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"ERROR: failed to call {url}: {e}", file=sys.stderr)
        return 1

    data = r.json()
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    hits = data.get("hits") or []
    if not hits:
        print("0件。検索対象フィールド/言語を確認")
        return 0

    for h in hits:
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


def main() -> int:
    argv = sys.argv[1:]

    if argv and argv[0] == "compose":
        p = argparse.ArgumentParser(prog="docbot compose", description="docker-compose services table")
        p.add_argument("query", nargs="*", help="search query")
        p.add_argument("--lang", choices=["ja-jp", "en-us"], default=None)
        p.add_argument("--limit", type=int, default=10)
        p.add_argument("--base", default=DEFAULT_BASE)
        args = p.parse_args(argv[1:])
        q = " ".join(args.query).strip() or "Docker Compose"
        return run_compose(args.base, q, args.lang, args.limit)

    if argv and argv[0] == "helm":
        p = argparse.ArgumentParser(prog="docbot helm", description="Helm chart workload summary")
        p.add_argument("query", nargs="*", help="search query")
        p.add_argument("--lang", choices=["ja-jp", "en-us"], default=None)
        p.add_argument("--limit", type=int, default=15)
        p.add_argument("--base", default=DEFAULT_BASE)
        p.add_argument("--namespace", default="default")
        p.add_argument("--release", default="dify")
        p.add_argument("--values", dest="values_path", default=None)
        p.add_argument("--set", dest="set_args", action="append", default=[], metavar="KEY=VAL")
        p.add_argument("--chart-version", "--version", dest="chart_version", default=None, metavar="X.Y.Z",
                       help="チャートのバージョンを固定（指定必須、フォールバックなし）")
        p.add_argument("--chart", default=None, metavar="PATH",
                       help="ローカル .tgz または展開済みディレクトリを直接指定（検索スキップ）")
        args = p.parse_args(argv[1:])
        q = " ".join(args.query).strip() or "Dify Helm Chart"
        return run_helm(
            args.base, q, args.lang, args.limit, args.namespace, args.release,
            args.values_path, args.set_args or [], args.chart, args.chart_version
        )

    if argv and argv[0] == "stats":
        p = argparse.ArgumentParser(prog="docbot stats", description="DB のサイズとページ数を表示")
        p.add_argument("--db", default=None, help="DB パス（未指定で data/index.db）")
        args = p.parse_args(argv[1:])
        return run_stats(args.db)

    if argv and argv[0] == "upgrade":
        p = argparse.ArgumentParser(prog="docbot upgrade", description="Non-Skippable を考慮したアップグレード経路")
        p.add_argument("--from", dest="from_ver", required=True, metavar="X.Y.Z")
        p.add_argument("--to", dest="to_ver", required=True, metavar="X.Y.Z")
        p.add_argument("--values", default=None, help="values.yaml パス（オプション）")
        p.add_argument("--lang", choices=["ja-jp", "en-us"], default="en-us")
        args = p.parse_args(argv[1:])
        return run_upgrade(args.from_ver, args.to_ver, args.lang)

    if argv and argv[0] == "search":
        argv = argv[1:]

    p = argparse.ArgumentParser(prog="docbot", description="Local doc search helper for Dify Enterprise docs")
    p.add_argument("query", nargs="*", help="search query words")
    p.add_argument("--lang", choices=["ja-jp", "en-us"], default=None)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--base", default=DEFAULT_BASE)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    q = " ".join(args.query).strip()
    if not q:
        print("Usage: docbot [search] <query> [--lang ja-jp|en-us] [--limit N]", file=sys.stderr)
        print("       docbot compose <query> [--lang ja-jp|en-us]", file=sys.stderr)
        print("       docbot helm [query] [--chart PATH] [--chart-version X.Y.Z] [--values PATH] [--set K=V] ...", file=sys.stderr)
        print("       docbot upgrade --from X.Y.Z --to X.Y.Z", file=sys.stderr)
        print("       docbot stats  # DB サイズ・ページ数確認", file=sys.stderr)
        return 2

    return run_search(args.base, q, args.lang, args.limit, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
