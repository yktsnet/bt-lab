"""
s_monthly_sim.py — Monthly backtest simulation

Runs snapshot strategies with pips_avg_per_entry >= 0.3 over past 12 complete months.
Output: drip_sim_data/monthly/{YYYY-MM}/ALL/{date}.csv

計算は S3 → S5 → S6 と同じ関数を通す（月のバー全体に戦略を当て、S3 の間隔で絞り、
S5 でイベント化し、S6 で pips を出す）。日ごとの行は、閉じたイベントを閉じた日で数えたもの。

Run:
  python3 s_monthly_sim.py
  SIM_MONTH=2026-03 python3 s_monthly_sim.py
"""

import argparse
import importlib.util
import os
import sys
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.env_paths import get_backtest_data_root, get_parquet_root
from lib.cli_common import add_trading_args, apply_env_overrides
from core.s3_calc_positions import compute_entries
from core.s5_position_engine import build_events
from core.s6_position_pips import _calc_pips


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="月次バックテストシミュレーション")
    add_trading_args(p, spread=True)
    p.add_argument("--month", default=None, help="対象月 YYYY-MM (env: SIM_MONTH, default: 直近12ヶ月)")
    return p.parse_args()

SESSION = "ALL"
START_HOUR = 0
END_HOUR = 17


def _load_strategies_from_snapshot(
    snapshot_month: str,
    rank_root: Path,
    strategies_root: Path,
    min_avg: float = 0.3,
) -> list:
    import csv
    snapshot_path = rank_root / "snapshots" / snapshot_month / "rank_by_pips_avg.csv"
    if not snapshot_path.exists():
        print(f"s_monthly_sim: snapshot not found: {snapshot_path}", flush=True)
        return []
    strategy_files = []
    with open(snapshot_path) as f:
        for row in csv.DictReader(f):
            try:
                avg = float(row.get("pips_avg_per_entry", 0) or 0)
            except Exception:
                avg = 0.0
            if avg < min_avg:
                continue
            tid = row.get("id", "").strip()
            slug = row.get("slug", "").strip()
            sf = strategies_root / tid / f"{slug}.py"
            if sf.exists():
                strategy_files.append(sf)
            else:
                print(f"s_monthly_sim: strategy file not found: {sf}", flush=True)
    return strategy_files


def _load_strategy(path: Path):
    spec = importlib.util.spec_from_file_location("_strat", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _month_closes(mod, df_month: pd.DataFrame, ident: str, env: dict) -> pd.DataFrame:
    """1戦略を月のバー全体に S3 → S5 → S6 と同じ手順で当て、閉じたイベントを
    閉じた日（date）と pips_net の2列で返す。"""
    empty = pd.DataFrame({"date": [], "pips_net": []})
    interval = int(float(env.get("ENTRY_INTERVAL_MIN", 30)))
    sig = compute_entries(mod, df_month, interval)
    if sig is None:
        return empty
    events = build_events(df_month, sig, ident, env)
    if not events:
        return empty
    ev = _calc_pips(pd.DataFrame(events), env)
    closes = ev[ev["type"] == "close"]
    return pd.DataFrame({
        "date": pd.to_datetime(closes["time_utc"], utc=True).dt.date.values,
        "pips_net": closes["pips_net"].astype("float64").values,
    })


def trading_days_in_month(month: date) -> list:
    last = monthrange(month.year, month.month)[1]
    return [date(month.year, month.month, d) for d in range(1, last + 1) if date(month.year, month.month, d).weekday() < 5]


def _target_months(sim_month: str = "") -> list:
    sim_month = sim_month or os.environ.get("SIM_MONTH", "").strip()
    if sim_month:
        d = datetime.strptime(sim_month, "%Y-%m").date().replace(day=1)
        return [d]

    today = datetime.now(timezone.utc).date()
    # 前月から遡って12ヶ月（古い順）
    months = []
    y, m = today.year, today.month
    m -= 1
    if m == 0:
        m = 12
        y -= 1
    for _ in range(12):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()
    return months


def run(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = parse_args()

    env = apply_env_overrides(dict(os.environ), args)
    data_root = get_backtest_data_root()
    parquet_root = get_parquet_root()
    rank_root = data_root / "rank" / SESSION.lower()
    strategies_root = data_root / "strategies"
    monthly_root = data_root / "monthly"

    target_months = _target_months(args.month or "")

    for month in target_months:
        prev_y, prev_m = month.year, month.month - 1
        if prev_m == 0:
            prev_m = 12
            prev_y -= 1
        prev_month_str = f"{prev_y}-{prev_m:02d}"

        strategy_files = _load_strategies_from_snapshot(
            prev_month_str, rank_root, strategies_root
        )
        if not strategy_files:
            print(f"s_monthly_sim: skip {month.strftime('%Y-%m')} (no snapshot for {prev_month_str})", flush=True)
            continue

        pq_path = parquet_root / f"year={month.year}" / f"{month.month:02d}.parquet"
        if not pq_path.exists():
            print(f"skip {month.strftime('%Y-%m')}: parquet not found", flush=True)
            continue

        df_month = pd.read_parquet(pq_path)
        df_month["time_utc"] = pd.to_datetime(df_month["time_utc"], utc=True)

        days = trading_days_in_month(month)
        todo = [
            d for d in days
            if not (monthly_root / f"{month.year}-{month.month:02d}" / SESSION / f"{d}.csv").exists()
        ]
        # 日ごとに回さず月で1回回す。S5 の SPARK 後の建て止めなど日をまたぐ状態も S3〜S6 と揃う
        sess_bars = df_month[
            (df_month["time_utc"].dt.hour >= START_HOUR) & (df_month["time_utc"].dt.hour < END_HOUR)
        ]
        bar_days = set(sess_bars["time_utc"].dt.date)
        todo = [d for d in todo if d in bar_days]
        written = 0

        closes_by_strategy = {}
        if todo:
            for sf in strategy_files:
                try:
                    closes_by_strategy[sf] = _month_closes(
                        _load_strategy(sf), df_month, sf.parent.name, env
                    )
                except Exception as e:
                    print(f"  WARN ALL/{sf.name} {month.strftime('%Y-%m')}: {e}", flush=True)
                    closes_by_strategy[sf] = None

        for day in todo:
            out_path = monthly_root / f"{month.year}-{month.month:02d}" / SESSION / f"{day}.csv"

            records = []
            for sf in strategy_files:
                tid = sf.parent.name
                slug = sf.stem
                closes = closes_by_strategy[sf]
                if closes is None:
                    records.append({"tid": tid, "slug": slug, "entries": 0, "pips_sum": 0.0, "pips_avg": ""})
                    continue
                today = closes[closes["date"] == day]
                entries = len(today)
                pips_sum = float(today["pips_net"].sum())
                pips_avg = round(pips_sum / entries, 2) if entries > 0 else ""
                records.append({"tid": tid, "slug": slug, "entries": entries, "pips_sum": round(pips_sum, 2), "pips_avg": pips_avg})

            if records:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = out_path.with_suffix(".tmp")
                pd.DataFrame(records).to_csv(tmp_path, index=False)
                os.replace(tmp_path, out_path)
                written += 1

        print(f"s_monthly_sim: {month.strftime('%Y-%m')} → {written} days written", flush=True)

    print("s_monthly_sim done", flush=True)


if __name__ == "__main__":
    run()
