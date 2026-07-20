"""
s6_position_pips.py — K4b相当: pips計算

pos_events/ の各 parquet に pips_net 列を付与して上書きする。

計算ルール:
  type=open  行 → pips_net = None
  type=close 行:
    abnormal=TP    → pips_gross = +RR_TP_PIPS
    abnormal=SL    → pips_gross = -RR_SL_PIPS
    その他         → pips_gross = sign × (close_price - entry) / PIP_SIZE
  pips_net = pips_gross - SPREAD_PIPS

環境変数:
  RR_TP_PIPS    (default: 30)
  RR_SL_PIPS    (default: 10)
  PIP_SIZE      (default: 0.01)
  SPREAD_PIPS   (default: 0.3)
  S6_JOBS       (default: auto)
"""

import argparse
import concurrent.futures
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.env_paths import get_backtest_data_root
from lib.cli_common import add_trading_args, apply_env_overrides


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S6: pips_net列の付与")
    add_trading_args(p, spread=True)
    p.add_argument("--jobs", type=int, default=None, help="並列プロセス数 (env: S6_JOBS, default: cpu_count)")
    return p.parse_args()


def _fv(env, k, d):
    try:
        return float(env.get(k, d))
    except Exception:
        return float(d)


def _iv(env, k, d):
    try:
        return int(float(env.get(k, d)))
    except Exception:
        return int(d)


def _calc_pips(df: pd.DataFrame, env: dict) -> pd.DataFrame:
    tp_pips  = _fv(env, "RR_TP_PIPS", 30.0)
    sl_pips  = _fv(env, "RR_SL_PIPS", 10.0)
    pip      = _fv(env, "PIP_SIZE", 0.01)
    spread   = _fv(env, "SPREAD_PIPS", 0.3)

    close_rows = df["type"] == "close"
    pips_net = pd.Series([None] * len(df), dtype="Float64")

    for i, row in df[close_rows].iterrows():
        abn  = str(row.get("abnormal", "")).strip().upper()
        side = str(row.get("side", "")).strip().upper()
        sign = 1.0 if side == "BUY" else -1.0

        if abn == "TP":
            gross = tp_pips
        elif abn == "SL":
            gross = -sl_pips
        else:
            cp = row.get("close_price")
            en = row.get("entry")
            if cp is None or en is None or pd.isna(cp) or pd.isna(en):
                gross = None
            else:
                gross = sign * (float(cp) - float(en)) / pip

        if gross is not None:
            pips_net[i] = round(gross - spread, 2)

    df = df.copy()
    df["pips_net"] = pips_net
    return df


def _process_one(path: Path, env: dict) -> str:
    try:
        df = pd.read_parquet(path)

        # 既に pips_net があってclose行に値が入っていればスキップ
        if "pips_net" in df.columns:
            close_mask = df["type"] == "close"
            if close_mask.any() and df.loc[close_mask, "pips_net"].notna().all():
                return "skipped"

        df = _calc_pips(df, env)
        df.to_parquet(path, index=False)
        return "wrote"
    except Exception as e:
        print(f"  ERROR {path}: {e}", flush=True)
        return "error"


def run(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = parse_args()

    data_root   = get_backtest_data_root()
    events_root = data_root / "pos_events"
    env         = apply_env_overrides(dict(os.environ), args)

    files = sorted(events_root.rglob("*.parquet"))
    if not files:
        print("s6: no pos_events parquet found", flush=True)
        return

    jobs = args.jobs if args.jobs is not None else _iv(env, "S6_JOBS", os.cpu_count() or 1)
    print(f"s6: files={len(files)} jobs={jobs}", flush=True)

    wrote = skipped = errors = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as ex:
        futures = {ex.submit(_process_one, f, env): f for f in files}
        for fut in concurrent.futures.as_completed(futures):
            try:
                r = fut.result()
                if r == "wrote":    wrote += 1
                elif r == "skipped": skipped += 1
                else:               errors += 1
            except Exception as e:
                print(f"  FATAL {futures[fut]}: {e}", flush=True)
                errors += 1

    print(f"s6 done: wrote={wrote} skipped={skipped} errors={errors}", flush=True)


if __name__ == "__main__":
    run()
