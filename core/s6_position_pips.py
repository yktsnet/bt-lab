"""
s6_position_pips.py — K4b相当: pips計算

pos_events/ の各 parquet に pips_net 列を付与して上書きする。

計算ルール:
  type=open  行 → pips_net = None
  type=close 行 → pips_gross = sign × (close_price - entry) / PIP_SIZE
                  （TP/SL で閉じた行も同じ。S5 が close_price に TP/SL の価格を入れている）
  pips_net = pips_gross - SPREAD_PIPS

環境変数:
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
from core.s3_calc_positions import read_meta, write_parquet_atomic, META_PREFIX

META_KEY_S6 = META_PREFIX + "s6"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S6: pips_net列の付与")
    add_trading_args(p, spread=True)
    # TP/SL は S5 が close_price に反映済みで、S6 は価格差から pips を出す。
    # 共通引数として受け取るだけで、S6 の結果には効かない。
    for action in p._actions:
        if action.dest in ("tp_pips", "sl_pips"):
            action.help = "S6 では効かない（S5 に渡した値が close_price に入っている）"
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


def _pips_params(env: dict) -> dict:
    return {"pip_size": _fv(env, "PIP_SIZE", 0.01), "spread_pips": _fv(env, "SPREAD_PIPS", 0.3)}


def _calc_pips(df: pd.DataFrame, env: dict) -> pd.DataFrame:
    prm = _pips_params(env)
    pip = prm["pip_size"]
    spread = prm["spread_pips"]

    close_rows = df["type"] == "close"
    pips_net = pd.Series([None] * len(df), dtype="Float64")

    for i, row in df[close_rows].iterrows():
        side = str(row.get("side", "")).strip().upper()
        sign = 1.0 if side == "BUY" else -1.0

        cp = row.get("close_price")
        en = row.get("entry")
        if cp is None or en is None or pd.isna(cp) or pd.isna(en):
            continue
        gross = sign * (float(cp) - float(en)) / pip
        pips_net[i] = round(gross - spread, 2)

    df = df.copy()
    df["pips_net"] = pips_net
    return df


def _process_one(path: Path, env: dict) -> str:
    try:
        params = _pips_params(env)
        meta = read_meta(path)
        df = pd.read_parquet(path)

        # 引数を残していない旧いファイルは meta が空なので、付け直す
        if "pips_net" in df.columns and meta.get(META_KEY_S6) == params:
            return "skipped"

        df = _calc_pips(df, env)
        meta[META_KEY_S6] = params
        write_parquet_atomic(df, path, meta)
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
