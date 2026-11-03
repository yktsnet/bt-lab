"""
core/s1_enrich_parquet.py — S1c: Parquetへ特徴量を事前焼き込み

- import/feature_registry.yaml の precompute にある列だけを、欠け列のみ追記して原子的に置換
- registry にあって compute_all が計算しない列があれば、名前を出して失敗する
- 全列が揃っている月はスキップ（冪等）
- 出力: files=N added_total=N
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.env_paths import get_import_root, get_parquet_root
from lib.feature_registry import _row_name, precompute_specs
from lib.features import compute_all


class RegistryMismatch(ValueError):
    """registry の precompute に、compute_all が計算しない列がある。"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S1c: parquetへ特徴量列を事前焼き込み")
    p.add_argument("--year", default=None, help="対象年のみ処理 (env: YEAR_ONLY, default: 全年)")
    return p.parse_args()


def _load_parquet(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(path)
        if "close" not in df.columns:
            print(f"skip {path}: missing close column", flush=True)
            return None
        return df
    except Exception as e:
        print(f"skip {path}: {e}", flush=True)
        return None


def registry_columns() -> list[str]:
    """焼き込む列の名前。import/feature_registry.yaml の precompute が単一情報源。"""
    specs = precompute_specs(get_import_root() / "feature_registry.yaml")
    return [n for n in (_row_name(r) for r in specs) if n]


def _enrich_file(path: Path, columns: list[str] | None = None) -> int:
    """registry の列のうち欠けているものを追記して原子置換。追加した列数を返す。"""
    if columns is None:
        columns = registry_columns()
    df = _load_parquet(path)
    if df is None:
        return 0

    # time_utc を datetime に正規化（int64 ms の場合も許容）
    if "time_utc" in df.columns:
        if pd.api.types.is_integer_dtype(df["time_utc"]):
            df["time_utc"] = pd.to_datetime(df["time_utc"], unit="ms", utc=True)

    all_cols = compute_all(df)

    unknown = [c for c in columns if c not in all_cols]
    if unknown:
        raise RegistryMismatch(
            "feature_registry.yaml precompute has columns that compute_all does not "
            "produce: " + ", ".join(unknown)
        )

    missing = {c: all_cols[c] for c in columns if c not in df.columns}
    if not missing:
        return 0

    new_df = pd.concat([df, pd.DataFrame(missing, index=df.index)], axis=1)
    df = new_df

    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
    return len(missing)


def main(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = parse_args()

    parquet_root = get_parquet_root()
    paths = sorted(parquet_root.rglob("*.parquet"))
    # cal_ プレフィックスは除外（bt/ の慣習）
    paths = [p for p in paths if not p.name.startswith("cal_")]

    year_only = args.year or os.environ.get("YEAR_ONLY", "").strip()
    if year_only:
        paths = [p for p in paths if f"year={year_only}" in str(p)]

    columns = registry_columns()
    total_added = 0
    for path in paths:
        try:
            added = _enrich_file(path, columns)
        except RegistryMismatch as e:
            print(f"s1c: {e}", file=sys.stderr, flush=True)
            sys.exit(1)
        if added:
            print(f"enriched {path}: added {added} cols", flush=True)
        total_added += added

    print(f"files={len(paths)} added_total={total_added}", flush=True)


if __name__ == "__main__":
    main()
