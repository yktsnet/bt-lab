from pathlib import Path
from typing import Dict, List, Set, Any

from lib.yaml_loader import load_yaml


def load_feature_registry(path: Path) -> Dict[str, Any]:
    data = load_yaml(path) or {}
    if "precompute" not in data:
        data["precompute"] = []
    if "runtime_only" not in data:
        data["runtime_only"] = []
    return data


def _row_name(row: Any) -> str:
    """precompute/runtime_only の1行から特徴量名を取り出す。
    import/feature_registry.yaml は素の文字列リスト(`- rsi14`)。
    辞書形式(`- name: rsi14`)も後方互換として受ける。"""
    if isinstance(row, dict):
        return str(row.get("name", "")).strip()
    return str(row).strip()


def available_feature_names(path: Path) -> Set[str]:
    data = load_feature_registry(path)
    out = set()
    for row in data.get("precompute", []):
        name = _row_name(row)
        if name:
            out.add(name)
    for row in data.get("runtime_only", []):
        name = _row_name(row)
        if name:
            out.add(name)
    return out


def precompute_specs(path: Path) -> List[Dict[str, Any]]:
    data = load_feature_registry(path)
    return list(data.get("precompute", []))
