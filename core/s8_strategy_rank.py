"""
s8_strategy_rank.py — K5相当: Recovery Factorフィルタ + 戦略ランキング

処理フロー:
  1. summary/all/ の monthly_all.csv から Recovery Factor（total_pips / 最大DD）
     と回復月数（最大DD / 月次平均利益）を計算
  2. 基準を満たさない戦略を除外
  3. 直近N月のデータでランキング（pips_avg順 / pips_sum順）

出力:
  rank/all/rank_by_pips_avg.csv
  rank/all/rank_by_pips_sum.csv
  rank/all/dd_filtered.csv  （除外された戦略一覧）

環境変数 / s8_config.json:
  S8_RANK_MONTHS          ランキング対象の直近月数 (default: 12)
  S8_RF_MIN               Recovery Factor下限 (default: 2.0)
  S8_RECOVERY_MONTHS_MAX  回復月数上限 (default: 6.0)
  S8_MIN_SIG_PER_HOUR     ランキング対象の最低シグナル頻度 signals/hour (default: 0.1)
  S8_AS_OF                YYYY-MM指定でその月末時点のスナップショットを作る（省略時は現在時刻基準）
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S8: Recovery Factorフィルタ + 戦略ランキング")
    p.add_argument("--rank-months", type=int, default=None, help="ランキング対象の直近月数 (env/s8_config: S8_RANK_MONTHS, default: 12)")
    p.add_argument("--rf-min", type=float, default=None, help="Recovery Factor下限 (env/s8_config: S8_RF_MIN, default: 2.0)")
    p.add_argument("--recovery-months-max", type=float, default=None, help="回復月数上限 (env/s8_config: S8_RECOVERY_MONTHS_MAX, default: 6.0)")
    p.add_argument("--min-sig-per-hour", type=float, default=None, help="最低シグナル頻度 signals/hour (env/s8_config: S8_MIN_SIG_PER_HOUR, default: 0.1)")
    p.add_argument("--as-of", default=None, help="YYYY-MM指定でその月末時点のスナップショットを作る (env: S8_AS_OF)")
    return p.parse_args()
from lib.env_paths import get_backtest_data_root

SESSION = "all"


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


def _dd_metrics(pips_series: pd.Series) -> dict:
    """
    abs_dd          : ピークからの最大下落幅（pips絶対値）
    recovery_factor : total_pips / abs_dd（回収効率）
    recovery_months : abs_dd / 利益月平均pips（回復にかかる月数推計）
    """
    cumsum = pips_series.cumsum()
    peak = cumsum.cummax()
    abs_dd = float((peak - cumsum).max())

    total = float(pips_series.sum())
    rf = total / abs_dd if abs_dd > 0 else float("inf")

    profit_months = pips_series[pips_series > 0]
    avg_profit = float(profit_months.mean()) if not profit_months.empty else 0.0
    rec_months = abs_dd / avg_profit if avg_profit > 0 else float("inf")

    return {
        "abs_dd": round(abs_dd, 1),
        "recovery_factor": round(rf, 2),
        "recovery_months": round(rec_months, 1),
    }


def run(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = parse_args()

    data_root = get_backtest_data_root()
    summary_root = data_root / "summary" / SESSION
    rank_root = data_root / "rank" / SESSION

    env = dict(os.environ)
    config_file = data_root / "s8_config.json"
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text())
            env.update({k: str(v) for k, v in cfg.items()})
        except Exception as e:
            print(f"s8: config load failed: {e}", flush=True)

    rank_months = args.rank_months if args.rank_months is not None else _iv(env, "S8_RANK_MONTHS", 12)
    rf_min = args.rf_min if args.rf_min is not None else _fv(env, "S8_RF_MIN", 2.0)
    recovery_months_max = (
        args.recovery_months_max if args.recovery_months_max is not None
        else _fv(env, "S8_RECOVERY_MONTHS_MAX", 6.0)
    )
    min_sig_per_hour = (
        args.min_sig_per_hour if args.min_sig_per_hour is not None
        else _fv(env, "S8_MIN_SIG_PER_HOUR", 0.1)
    )

    print(
        f"s8: rank_months={rank_months} rf_min={rf_min} "
        f"recovery_months_max={recovery_months_max} min_sig_per_hour={min_sig_per_hour}",
        flush=True,
    )

    if not summary_root.exists():
        print(f"s8: summary/all/ not found. Run s7 first.", flush=True)
        return

    all_monthly = []
    for f in sorted(summary_root.rglob("monthly_all.csv")):
        try:
            all_monthly.append(pd.read_csv(f))
        except Exception:
            pass

    if not all_monthly:
        print("s8: no monthly_all.csv found.", flush=True)
        return

    df = pd.concat(all_monthly, ignore_index=True)
    df = df.sort_values(["id", "slug", "year", "month"]).reset_index(drop=True)

    as_of_str = (args.as_of or os.environ.get("S8_AS_OF", "")).strip()
    if as_of_str:
        now = datetime.strptime(as_of_str, "%Y-%m").replace(day=1, tzinfo=timezone.utc)
    else:
        now = datetime.now(timezone.utc)
        as_of_str = ""

    cutoff_year = now.year
    cutoff_month = now.month - rank_months
    while cutoff_month <= 0:
        cutoff_month += 12
        cutoff_year -= 1

    df["ym"] = df["year"] * 100 + df["month"]
    cutoff_ym = cutoff_year * 100 + cutoff_month

    if as_of_str:
        as_of_ym = int(as_of_str[:4]) * 100 + int(as_of_str[5:7])
        df = df[df["ym"] <= as_of_ym].copy()

    df_recent = df[df["ym"] >= cutoff_ym].copy()

    print(
        f"s8: total={len(df)} recent={len(df_recent)} (since {cutoff_year}-{cutoff_month:02d})",
        flush=True,
    )

    # DD フィルタ（全期間）
    dd_records = []
    for (sid, slug), grp in df.groupby(["id", "slug"]):
        grp = grp.sort_values(["year", "month"])
        pips = pd.to_numeric(grp["pips_sum_total"], errors="coerce").fillna(0)
        metrics = _dd_metrics(pips)
        total_entries = int(grp["entries_total"].sum())
        total_pips = float(pips.sum())
        dd_records.append(
            {
                "id": sid,
                "slug": slug,
                "abs_dd": metrics["abs_dd"],
                "recovery_factor": metrics["recovery_factor"],
                "recovery_months": metrics["recovery_months"],
                "total_entries": total_entries,
                "total_pips": round(total_pips, 2),
            }
        )

    dd_df = pd.DataFrame(dd_records)
    banned_dd = dd_df[
        (dd_df["recovery_factor"] < rf_min)
        | (dd_df["recovery_months"] > recovery_months_max)
        | (dd_df["total_pips"] < 0)
    ]
    passed_dd = dd_df[
        (dd_df["recovery_factor"] >= rf_min)
        & (dd_df["recovery_months"] <= recovery_months_max)
        & (dd_df["total_pips"] >= 0)
    ]

    print(
        f"s8 [all]: total={len(dd_df)} dd_ban={len(banned_dd)} passed={len(passed_dd)}",
        flush=True,
    )

    passed_keys = set(zip(passed_dd["id"], passed_dd["slug"]))
    # 行ごとのapply(axis=1)は0行のdf_recentで列情報を失いKeyErrorになるため、
    # MultiIndex.isinで判定する(0行でも列構造が保たれる)。
    recent_passed = df_recent[
        pd.MultiIndex.from_frame(df_recent[["id", "slug"]]).isin(passed_keys)
    ]

    rank_agg = recent_passed.groupby(["id", "slug"], as_index=False).agg(
        entries_total=("entries_total", "sum"),
        bars5m_total=("bars5m_total", "sum"),
        pips_sum_total=("pips_sum_total", "sum"),
    )
    rank_agg["pips_avg_per_entry"] = (
        rank_agg["pips_sum_total"] / rank_agg["entries_total"].replace(0, float("nan"))
    ).round(2)
    rank_agg["entry_rate"] = (
        rank_agg["entries_total"] / rank_agg["bars5m_total"].replace(0, float("nan"))
    ).round(6)
    rank_agg["signals_per_hour"] = (
        rank_agg["entries_total"]
        / (rank_agg["bars5m_total"].replace(0, float("nan")) / 12)
    ).round(4)

    rank_agg = rank_agg[rank_agg["signals_per_hour"] >= min_sig_per_hour]
    rank_agg = rank_agg.merge(
        passed_dd[
            ["id", "slug", "abs_dd", "recovery_factor", "recovery_months", "total_pips"]
        ],
        on=["id", "slug"],
        how="left",
    )
    rank_agg["session"] = SESSION

    rank_avg = rank_agg.sort_values("pips_avg_per_entry", ascending=False).reset_index(
        drop=True
    )
    rank_avg.index += 1
    rank_avg.index.name = "rank"

    rank_sum = rank_agg.sort_values("pips_sum_total", ascending=False).reset_index(
        drop=True
    )
    rank_sum.index += 1
    rank_sum.index.name = "rank"

    if len(rank_agg) > 0:
        top = rank_avg.iloc[0]
        print(
            f"s8 [all]: rank candidates={len(rank_agg)} "
            f"(top avg: {top['id']}/{top['slug']} avg={top['pips_avg_per_entry']})",
            flush=True,
        )
    else:
        print("s8 [all]: no candidates after filter", flush=True)

    rank_root.mkdir(parents=True, exist_ok=True)
    if not as_of_str:
        rank_avg.to_csv(rank_root / "rank_by_pips_avg.csv")
        rank_sum.to_csv(rank_root / "rank_by_pips_sum.csv")
        banned_dd[
            [
                "id",
                "slug",
                "abs_dd",
                "recovery_factor",
                "recovery_months",
                "total_entries",
                "total_pips",
            ]
        ].to_csv(rank_root / "dd_filtered.csv", index=False)

    if as_of_str:
        snapshot_dir = rank_root / "snapshots" / as_of_str
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / "rank_by_pips_avg.csv"
        if not snapshot_path.exists():
            rank_avg.to_csv(snapshot_path)
            print(f"s8: snapshot saved → {snapshot_path}", flush=True)
        else:
            print(f"s8: snapshot already exists, skip → {snapshot_path}", flush=True)

    print(f"s8 done: wrote to rank/all/", flush=True)


if __name__ == "__main__":
    run()
