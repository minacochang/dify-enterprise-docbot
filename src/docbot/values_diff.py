"""
Helm values.yaml diff ロジック。
helm show values で from/to を取得し、flatten + diff + user_impacts を算出。
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Callable

import yaml

ARRAY_MODE_SET = "set"
ARRAY_MODE_INDEX = "index"
TYPE_NAMES = ("null", "bool", "int", "float", "str", "map", "list")


def _value_type(val) -> str:
    """粗い型分類"""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "bool"
    if isinstance(val, int):
        return "int"
    if isinstance(val, float):
        return "float"
    if isinstance(val, str):
        return "str"
    if isinstance(val, dict):
        return "map"
    if isinstance(val, list):
        return "list"
    return "str"


def _value_hash(val) -> str:
    """stable JSON ハッシュ（先頭16桁）"""
    try:
        s = json.dumps(val, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
    except (TypeError, ValueError):
        return ""


def _flatten_set(data, prefix: str) -> dict[str, tuple[str, object]]:
    """array-mode=set: a[] 形式で flatten（配列ノイズを抑える）"""
    out: dict[str, tuple[str, object]] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            out.update(_flatten_set(v, key))
    elif isinstance(data, list):
        if prefix:
            out[prefix] = (_value_type(data), data)
        for item in data:
            arr_prefix = f"{prefix}[]" if prefix else "[]"
            out.update(_flatten_set(item, arr_prefix))
    else:
        if prefix:
            out[prefix] = (_value_type(data), data)
    return out


def _flatten_index(data, prefix: str) -> dict[str, tuple[str, object]]:
    """array-mode=index: a[0] 形式で精密に flatten"""
    out: dict[str, tuple[str, object]] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            out.update(_flatten_index(v, key))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            arr_prefix = f"{prefix}[{i}]" if prefix else f"[{i}]"
            out.update(_flatten_index(item, arr_prefix))
    else:
        if prefix:
            out[prefix] = (_value_type(data), data)
    return out


def flatten_values(data: dict, array_mode: str) -> dict[str, tuple[str, object]]:
    """
    values を path -> (type, value) のフラット辞書に変換。
    array_mode: "set" | "index"
    """
    if array_mode == ARRAY_MODE_INDEX:
        return _flatten_index(data, "")
    return _flatten_set(data, "")


def compute_diff(
    from_flat: dict[str, tuple[str, object]],
    to_flat: dict[str, tuple[str, object]],
) -> dict:
    """
    added / removed / type_changed / default_changed を算出。
    """
    from_keys = set(from_flat.keys())
    to_keys = set(to_flat.keys())

    added = []
    for k in sorted(to_keys - from_keys):
        t, v = to_flat[k]
        added.append({"path": k, "type": t, "value": v})

    removed = []
    for k in sorted(from_keys - to_keys):
        t, v = from_flat[k]
        removed.append({"path": k, "type": t, "value": v})

    type_changed = []
    default_changed = []
    for k in sorted(from_keys & to_keys):
        ft, fv = from_flat[k]
        tt, tv = to_flat[k]
        if ft != tt:
            type_changed.append({
                "path": k, "from_type": ft, "to_type": tt,
                "from_value": fv, "to_value": tv,
            })
        elif _value_hash(fv) != _value_hash(tv):
            default_changed.append({
                "path": k, "type": tt, "from_value": fv, "to_value": tv,
            })

    return {
        "added": added,
        "removed": removed,
        "type_changed": type_changed,
        "default_changed": default_changed,
    }


def compute_user_impacts(
    diff: dict,
    user_flat: dict[str, tuple[str, object]],
) -> list[dict]:
    """
    user-values で使用しているキーが removed / type_changed に含まれる場合、
    user_impacts に追加。
    """
    removed_paths = {e["path"] for e in diff["removed"]}
    type_changed_paths = {e["path"] for e in diff["type_changed"]}

    impacts = []
    for path in sorted(user_flat.keys()):
        if path in removed_paths:
            _, uv = user_flat[path]
            impacts.append({
                "kind": "removed_but_used",
                "path": path,
                "user_value": uv,
            })
        elif path in type_changed_paths:
            entry = next(e for e in diff["type_changed"] if e["path"] == path)
            _, uv = user_flat[path]
            impacts.append({
                "kind": "type_changed_and_used",
                "path": path,
                "from_type": entry["from_type"],
                "to_type": entry["to_type"],
                "user_value": uv,
            })
    return impacts


def _is_cert_error(err: str) -> bool:
    """TLS/証明書関連エラーか判定"""
    if not err:
        return False
    lower = err.lower()
    return any(k in lower for k in ("tls", "certificate", "x509", "cert", "ssl"))

def _run_helm_show_values_impl(
    run: Callable, cmd: list[str], env: dict | None = None
) -> tuple[str | None, str | None]:
    """helm show values を実行し (stdout, error) を返す"""
    kw = {"capture_output": True, "text": True, "timeout": 60}
    if env is not None:
        kw["env"] = env
    try:
        r = run(cmd, **kw)
    except FileNotFoundError:
        return None, "helm が見つかりません。https://helm.sh でインストールしてください。"
    except subprocess.TimeoutExpired:
        return None, "helm show values がタイムアウトしました。"
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        return None, err or f"helm show values が終了コード {r.returncode} で失敗しました。"
    return r.stdout, None


def run_helm_show_values(chart_ref: str, version: str | None, run_subprocess: Callable | None = None) -> tuple[str | None, str | None]:
    """
    helm show values <chart> [--version X] を実行し、(stdout, error_message) を返す。
    失敗時、証明書エラーと判定できれば certifi の証明書でリトライする。
    それでも失敗した場合は証明書設定のヒントをエラーに付加する。
    run_subprocess はテスト用に差し替え可能。
    """
    run = run_subprocess or subprocess.run
    cmd = ["helm", "show", "values", chart_ref]
    if version:
        cmd.extend(["--version", version])

    out, err = _run_helm_show_values_impl(run, cmd)
    if out is not None:
        return out, None

    if not _is_cert_error(err or ""):
        return None, err

    try:
        import certifi
    except ImportError:
        return None, (err or "") + "\n\n証明書エラーの場合: SSL_CERT_FILE=$(python -m certifi) を設定して再試行してください。"

    env = os.environ.copy()
    env["SSL_CERT_FILE"] = certifi.where()
    out, err2 = _run_helm_show_values_impl(run, cmd, env)
    if out is not None:
        return out, None

    hint = "\n\n証明書エラーの場合は、次のコマンドで証明書を明示して再試行してください:\n  SSL_CERT_FILE=$(python -m certifi) docbot upgrade --from X.Y.Z --to X.Y.Z --mode helm"
    return None, (err2 or err or "") + hint


def build_values_diff_result(
    from_chart: str,
    from_version: str | None,
    to_chart: str,
    to_version: str | None,
    from_yaml: str,
    to_yaml: str,
    user_yaml: str | None,
    array_mode: str,
    run_subprocess: Callable | None = None,
) -> dict | None:
    """
    YAML 文字列から diff 結果 dict を構築。
    user_yaml が None でも user_impacts は空リストで返す。
    """
    try:
        from_data = yaml.safe_load(from_yaml)
        to_data = yaml.safe_load(to_yaml)
    except yaml.YAMLError as e:
        return {"error": f"YAML パースエラー: {e}"}

    if from_data is None:
        from_data = {}
    if to_data is None:
        to_data = {}

    from_flat = flatten_values(from_data, array_mode)
    to_flat = flatten_values(to_data, array_mode)

    diff = compute_diff(from_flat, to_flat)

    user_impacts = []
    if user_yaml:
        try:
            user_data = yaml.safe_load(user_yaml)
            user_data = user_data or {}
            user_flat = flatten_values(user_data, array_mode)
            user_impacts = compute_user_impacts(diff, user_flat)
        except yaml.YAMLError:
            pass

    commands = [
        f"helm show values {from_chart}" + (f" --version {from_version}" if from_version else ""),
        f"helm show values {to_chart}" + (f" --version {to_version}" if to_version else ""),
    ]

    return {
        "from": {"chart": from_chart, "version": from_version or ""},
        "to": {"chart": to_chart, "version": to_version or ""},
        "summary": {
            "added": len(diff["added"]),
            "removed": len(diff["removed"]),
            "type_changed": len(diff["type_changed"]),
            "default_changed": len(diff["default_changed"]),
            "user_impacts": len(user_impacts),
            "array_mode": array_mode,
        },
        "added": diff["added"],
        "removed": diff["removed"],
        "type_changed": diff["type_changed"],
        "default_changed": diff["default_changed"],
        "user_impacts": user_impacts,
        "commands": commands,
        "citations": [],
    }
