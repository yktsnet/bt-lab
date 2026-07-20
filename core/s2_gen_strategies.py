"""
core/s2_gen_strategies.py — S2: 戦略ファイル生成

- strategies_md/*/*/template.py を glob で全列挙
- PARAMS_GRID を直積展開して strategies/<kind>/<slug>.py を生成
- 冪等動作: 同一内容なら kept、差分あれば updated、新規なら created、不要なら deleted
- 実行サマリを1行で stdout に出力
"""
import importlib.util
import itertools
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.env_paths import get_strategies_root, get_import_root


def _vstr(v) -> str:
    if isinstance(v, float):
        s = f"{v:.10f}".rstrip("0")
        if s.endswith("."):
            s += "0"
        return s.replace(".", "p")
    return str(v)


def _make_slug(params: dict) -> str:
    return "_".join(f"{k}{_vstr(v)}" for k, v in sorted(params.items()))


def _expand_grid(params_grid: dict) -> list[dict]:
    keys = list(params_grid.keys())
    values = [v if isinstance(v, list) else [v] for v in params_grid.values()]
    result = []
    for combo in itertools.product(*values):
        result.append(dict(zip(keys, combo)))
    return result


def _load_template(path: Path):
    spec = importlib.util.spec_from_file_location("_tpl", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_code(template_source: str, slug: str, params: dict) -> str:
    suffix = (
        f"\nSLUG = {slug!r}\n"
        f"PARAMS = {params!r}\n\n"
        "_template_apply_entry_flag = apply_entry_flag\n\n\n"
        "def apply_entry_flag(df, params):\n"
        "    df = apply_indicators(df, params)\n"
        "    return _template_apply_entry_flag(df, params)\n"
    )
    return template_source.rstrip() + "\n" + suffix


def main() -> None:
    import_root = get_import_root()
    strategies_root = get_strategies_root()

    registry_path = import_root / "feature_registry.yaml"
    with open(registry_path) as f:
        registry = yaml.safe_load(f)
    available_features: set[str] = set(registry.get("precompute", []))

    project_root = Path(__file__).resolve().parents[1]
    templates_root = project_root / "strategies_md"
    template_paths = sorted(templates_root.glob("*/*/template.py"))

    desired: dict[Path, str] = {}
    skipped = 0

    for tpl_path in template_paths:
        try:
            mod = _load_template(tpl_path)
        except Exception as e:
            print(f"s2: skip {tpl_path}: {e}", flush=True)
            continue

        kind = getattr(mod, "KIND", None)
        params_grid = getattr(mod, "PARAMS_GRID", {})
        if not kind or not params_grid:
            continue

        template_source = tpl_path.read_text()

        for params in _expand_grid(params_grid):
            try:
                req = mod.required_features(params)
            except Exception:
                skipped += 1
                continue

            missing = [f for f in req if f not in available_features]
            if missing:
                skipped += 1
                continue

            slug = _make_slug(params)
            code = _make_code(template_source, slug, params)
            path = strategies_root / kind / f"{slug}.py"
            desired[path] = code

    existing: set[Path] = set()
    if strategies_root.exists():
        for p in strategies_root.glob("*/*.py"):
            existing.add(p)

    kept = created = updated = deleted = 0

    for path, code in desired.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        if path.exists():
            if path.read_text() == code:
                kept += 1
                continue
            tmp.write_text(code)
            os.replace(tmp, path)
            updated += 1
        else:
            tmp.write_text(code)
            os.replace(tmp, path)
            created += 1

    for path in existing:
        if path not in desired:
            path.unlink()
            deleted += 1

    print(
        f"s2 desired={len(desired)} kept={kept} updated={updated} "
        f"created={created} deleted={deleted} skipped={skipped}",
        flush=True,
    )


if __name__ == "__main__":
    main()
