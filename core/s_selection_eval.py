"""
s_selection_eval.py — 選抜の当たり具合の集計

各月末のスナップショット（rank/all/snapshots/<M>/ の rank_by_*.csv）で選ばれた候補が、
翌月（M+1）にどれだけ稼いだかを、全候補と比べて月ごとに集計する。
翌月の成績は s7 の monthly_all.csv の pips_sum_total で測る。

  母集団          : M 以前の月次 CSV に一度でも現れた候補
  M+1 に行が無い候補 : 0 pips として扱う
  対象の月         : M+1 の月次データがある月だけ

出力:
  rank/all/eval/selection_eval.csv （1行 = スナップショット月 × 順位ファイル）

使い方:
  python3 s_selection_eval.py [--top 10] [--from YYYY-MM] [--until YYYY-MM]
"""

import argparse
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.env_paths import get_backtest_data_root

SESSION = "all"
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

OUT_COLS = [
    "snapshot",
    "rank_file",
    "n_universe",
    "n_selected",
    "univ_mean_pips",
    "sel_mean_pips",
    "sel_minus_univ",
    "topk_mean_pips",
    "topk_hit_rate",
    "rank_corr",
]


def _month_arg(value: str) -> str:
    if not _MONTH_RE.match(value):
        raise argparse.ArgumentTypeError(f"expected YYYY-MM, got {value!r}")
    return value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="選抜の当たり具合（翌月の成績）を月ごとに集計")
    p.add_argument("--top", type=int, default=10, help="上位K件の集計に使う件数 (default: 10)")
    p.add_argument("--from", dest="from_month", type=_month_arg, default=None, help="対象とするスナップショット月の下限 YYYY-MM")
    p.add_argument("--until", dest="until_month", type=_month_arg, default=None, help="対象とするスナップショット月の上限 YYYY-MM")
    return p.parse_args()


def _ym(month: str) -> int:
    return int(month[:4]) * 100 + int(month[5:7])


def _next_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7]) + 1
    if m == 13:
        y, m = y + 1, 1
    return f"{y}-{m:02d}"


def _spearman(rank: pd.Series, pips: pd.Series) -> float:
    """順位（小さい=良い）と翌月 pips の Spearman 相関。当たっていれば正。3 件未満・片方が定数なら NaN。"""
    if len(rank) < 3:
        return float("nan")
    rx = rank.rank().to_numpy(dtype=float)
    ry = pips.rank().to_numpy(dtype=float)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = np.sqrt((rx**2).sum() * (ry**2).sum())
    if denom == 0:
        return float("nan")
    return float(-(rx * ry).sum() / denom)


def _load_monthly(summary_root: Path) -> pd.DataFrame:
    """候補×月の pips_sum_total。列: id, slug, ym, pips。"""
    frames = []
    for f in sorted(summary_root.rglob("monthly_all.csv")):
        try:
            frames.append(pd.read_csv(f))
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=["id", "slug", "ym", "pips"])
    df = pd.concat(frames, ignore_index=True)
    df["ym"] = df["year"] * 100 + df["month"]
    df["pips"] = pd.to_numeric(df["pips_sum_total"], errors="coerce").fillna(0.0)
    return df.groupby(["id", "slug", "ym"], as_index=False)["pips"].sum()


def _list_snapshots(snap_root: Path, from_month: str | None, until_month: str | None) -> list[str]:
    if not snap_root.exists():
        return []
    months = [d.name for d in snap_root.iterdir() if d.is_dir() and _MONTH_RE.match(d.name)]
    if from_month:
        months = [m for m in months if m >= from_month]
    if until_month:
        months = [m for m in months if m <= until_month]
    return sorted(months)


def _evaluate(
    snapshot: str,
    rank_file: str,
    sel: pd.DataFrame,
    universe: pd.MultiIndex,
    next_pips: pd.Series,
    top: int,
) -> dict:
    """1 つの順位ファイルを翌月の成績で評価した 1 行を返す。"""
    if "rank" in sel.columns:
        sel = sel.sort_values("rank", kind="stable")
    sel = sel.reset_index(drop=True)
    rank = sel["rank"] if "rank" in sel.columns else pd.Series(np.arange(1, len(sel) + 1))

    sel_keys = pd.MultiIndex.from_frame(sel[["id", "slug"]])
    sel_pips = pd.Series(next_pips.reindex(sel_keys).fillna(0.0).to_numpy())
    univ_pips = next_pips.reindex(universe).fillna(0.0)

    nan = float("nan")
    univ_mean = float(univ_pips.mean()) if len(univ_pips) else nan
    sel_mean = float(sel_pips.mean()) if len(sel_pips) else nan
    topk = sel_pips.iloc[:top]
    return {
        "snapshot": snapshot,
        "rank_file": rank_file,
        "n_universe": int(len(universe)),
        "n_selected": int(len(sel)),
        "univ_mean_pips": univ_mean,
        "sel_mean_pips": sel_mean,
        "sel_minus_univ": sel_mean - univ_mean,
        "topk_mean_pips": float(topk.mean()) if len(topk) else nan,
        "topk_hit_rate": float((topk > 0).mean()) if len(topk) else nan,
        "rank_corr": _spearman(rank, sel_pips),
    }


def _write_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _print_summary(result: pd.DataFrame) -> None:
    for rank_file, grp in result.groupby("rank_file", sort=True):
        diff = grp["sel_minus_univ"].dropna()
        share = float((diff > 0).mean()) if len(diff) else float("nan")
        print(
            f"s_selection_eval [{rank_file}]: months={len(grp)} "
            f"mean_sel_minus_univ={diff.mean():.2f} "
            f"share_positive={share:.2f} "
            f"mean_rank_corr={grp['rank_corr'].mean():.3f}",
            flush=True,
        )


def run(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = parse_args()
    if args.top < 1:
        print("s_selection_eval: --top must be >= 1", file=sys.stderr)
        sys.exit(2)

    data_root = get_backtest_data_root()
    snap_root = data_root / "rank" / SESSION / "snapshots"
    summary_root = data_root / "summary" / SESSION
    out_path = data_root / "rank" / SESSION / "eval" / "selection_eval.csv"

    snapshots = _list_snapshots(snap_root, args.from_month, args.until_month)
    if not snapshots:
        print("s_selection_eval: no snapshots found in range. Run monthly-backfill first.", flush=True)
        return

    monthly = _load_monthly(summary_root)
    if monthly.empty:
        print("s_selection_eval: no monthly_all.csv found. Run s7 first.", flush=True)
        return

    rows = []
    for snap in snapshots:
        nxt = _next_month(snap)
        nxt_rows = monthly[monthly["ym"] == _ym(nxt)]
        if nxt_rows.empty:
            continue
        universe = pd.MultiIndex.from_frame(
            monthly.loc[monthly["ym"] <= _ym(snap), ["id", "slug"]].drop_duplicates()
        )
        next_pips = nxt_rows.set_index(["id", "slug"])["pips"]
        for csv in sorted((snap_root / snap).glob("rank_by_*.csv")):
            sel = pd.read_csv(csv)
            if not {"id", "slug"} <= set(sel.columns):
                print(f"s_selection_eval: skip {csv} (no id/slug columns)", flush=True)
                continue
            rows.append(_evaluate(snap, csv.stem, sel, universe, next_pips, args.top))

    if not rows:
        print("s_selection_eval: no snapshot has next-month data. Nothing to evaluate.", flush=True)
        return

    result = pd.DataFrame(rows, columns=OUT_COLS)
    _write_atomic(result, out_path)
    _print_summary(result)
    print(f"s_selection_eval done: wrote {out_path}", flush=True)


if __name__ == "__main__":
    run()
