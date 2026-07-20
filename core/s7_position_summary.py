"""
s7_position_summary.py — K4c相当: ポジション集計

pos_events/ の parquet を集計し、戦略×月次・四半期・年次の CSV を出力する。
セッション分割はしない（00:00-17:00 全バーを一体として扱う）。

出力先:
  summary/all/<year>/monthly_all.csv
  summary/all/<year>/quarterly_all.csv
  summary/all/<year>/yearly_all.csv
"""

import math
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.env_paths import get_backtest_data_root, get_parquet_root

SESSION = "all"
EOD_HOUR = 17  # 00:00〜17:00

MONTHLY_COLS = [
    "year",
    "month",
    "session",
    "id",
    "slug",
    "entries_total",
    "bars5m_total",
    "entry_rate",
    "pips_sum_total",
    "pips_avg_per_entry",
]
QUARTERLY_COLS = [
    "year",
    "quarter",
    "session",
    "id",
    "slug",
    "entries_total",
    "bars5m_total",
    "entry_rate",
    "pips_sum_total",
    "pips_avg_per_entry",
]
YEARLY_COLS = [
    "year",
    "session",
    "id",
    "slug",
    "entries_total",
    "bars5m_total",
    "entry_rate",
    "pips_sum_total",
    "pips_avg_per_entry",
]


def _r2(x):
    if x is None:
        return None
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return round(float(x), 2)
    except Exception:
        return None


def _quarter(month: int) -> int:
    return (int(month) - 1) // 3 + 1


def _bars_in_window(parquet_path: Path) -> int:
    """00:00〜17:00 のバー数を返す"""
    try:
        df = pd.read_parquet(parquet_path, columns=["time_utc"])
        df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
        mask = df["time_utc"].dt.hour < EOD_HOUR
        return int(mask.sum())
    except Exception:
        return 0


def run() -> None:
    data_root = get_backtest_data_root()
    parquet_root = get_parquet_root()
    events_root = data_root / "pos_events"
    summary_root = data_root / "summary"

    if not events_root.exists():
        print("s7: pos_events/ not found", flush=True)
        return

    # 月ごとのバー数（00:00〜17:00）
    bars_by_ym: dict[tuple, int] = {}
    for pf in sorted(parquet_root.glob("year=*/*.parquet")):
        year = int(pf.parent.name.split("=")[1])
        month = int(pf.stem)
        bars_by_ym[(year, month)] = _bars_in_window(pf)

    monthly_records = []

    for tid_dir in sorted(events_root.iterdir()):
        if not tid_dir.is_dir():
            continue
        tid = tid_dir.name
        for slug_dir in sorted(tid_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            slug = slug_dir.name
            for year_dir in slug_dir.glob("year=*"):
                year = int(year_dir.name.split("=")[1])
                for pos_file in sorted(year_dir.glob("*.parquet")):
                    month = int(pos_file.stem)
                    try:
                        df = pd.read_parquet(pos_file)
                        if "type" not in df.columns:
                            continue
                        close = df[df["type"] == "close"]
                        if close.empty:
                            continue

                        entries = len(close)
                        pips = (
                            pd.to_numeric(close.get("pips_net"), errors="coerce")
                            .fillna(0)
                            .sum()
                        )
                        bars = bars_by_ym.get((year, month), 0)

                        if entries > 0:
                            monthly_records.append(
                                (
                                    year,
                                    month,
                                    SESSION,
                                    tid,
                                    slug,
                                    entries,
                                    bars,
                                    float(pips),
                                )
                            )
                    except Exception as e:
                        print(f"  WARN {pos_file}: {e}", flush=True)

    if not monthly_records:
        print("s7: no records found", flush=True)
        return

    print(f"s7: {len(monthly_records)} monthly records", flush=True)

    mdf = pd.DataFrame(
        monthly_records,
        columns=[
            "year",
            "month",
            "session",
            "id",
            "slug",
            "entries_total",
            "bars5m_total",
            "pips_sum_total",
        ],
    )
    mdf["entry_rate"] = mdf.apply(
        lambda r: (
            _r2(r["entries_total"] / r["bars5m_total"])
            if r["bars5m_total"] > 0
            else 0.0
        ),
        axis=1,
    )
    mdf["pips_avg_per_entry"] = mdf.apply(
        lambda r: (
            _r2(r["pips_sum_total"] / r["entries_total"])
            if r["entries_total"] > 0
            else None
        ),
        axis=1,
    )
    mdf["pips_sum_total"] = mdf["pips_sum_total"].apply(_r2)
    mdf = mdf.sort_values(["id", "slug", "year", "month"]).reset_index(drop=True)

    mdf["quarter"] = mdf["month"].apply(_quarter)
    qdf = mdf.groupby(["year", "quarter", "session", "id", "slug"], as_index=False).agg(
        entries_total=("entries_total", "sum"),
        bars5m_total=("bars5m_total", "sum"),
        pips_sum_total=("pips_sum_total", "sum"),
    )
    qdf["entry_rate"] = qdf.apply(
        lambda r: (
            _r2(r["entries_total"] / r["bars5m_total"])
            if r["bars5m_total"] > 0
            else 0.0
        ),
        axis=1,
    )
    qdf["pips_avg_per_entry"] = qdf.apply(
        lambda r: (
            _r2(r["pips_sum_total"] / r["entries_total"])
            if r["entries_total"] > 0
            else None
        ),
        axis=1,
    )
    qdf["pips_sum_total"] = qdf["pips_sum_total"].apply(_r2)

    ydf = mdf.groupby(["year", "session", "id", "slug"], as_index=False).agg(
        entries_total=("entries_total", "sum"),
        bars5m_total=("bars5m_total", "sum"),
        pips_sum_total=("pips_sum_total", "sum"),
    )
    ydf["entry_rate"] = ydf.apply(
        lambda r: (
            _r2(r["entries_total"] / r["bars5m_total"])
            if r["bars5m_total"] > 0
            else 0.0
        ),
        axis=1,
    )
    ydf["pips_avg_per_entry"] = ydf.apply(
        lambda r: (
            _r2(r["pips_sum_total"] / r["entries_total"])
            if r["entries_total"] > 0
            else None
        ),
        axis=1,
    )
    ydf["pips_sum_total"] = ydf["pips_sum_total"].apply(_r2)

    for year in sorted(mdf["year"].unique()):
        out_dir = summary_root / SESSION / str(year)
        out_dir.mkdir(parents=True, exist_ok=True)

        m_sub = mdf[mdf["year"] == year][MONTHLY_COLS]
        q_sub = qdf[qdf["year"] == year][QUARTERLY_COLS]
        y_sub = ydf[ydf["year"] == year][YEARLY_COLS]

        if not m_sub.empty:
            m_sub.to_csv(out_dir / "monthly_all.csv", index=False)
        if not q_sub.empty:
            q_sub.to_csv(out_dir / "quarterly_all.csv", index=False)
        if not y_sub.empty:
            y_sub.to_csv(out_dir / "yearly_all.csv", index=False)

    years = sorted(mdf["year"].unique())
    print(f"s7 done: session=all years={years}", flush=True)


if __name__ == "__main__":
    run()
