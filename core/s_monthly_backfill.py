"""
s_monthly_backfill.py — Monthly backfill oneshot

過去12ヶ月分のS8 snapshot生成 → s_monthly_sim を順番に実行する。
一度実行すれば冪等（既存snapshotとmonthly/は上書きしない）。

実行:
  python3 s_monthly_backfill.py
"""

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PYTHON = sys.executable
S8 = str(Path(__file__).parent / "s8_strategy_rank.py")
SIM = str(Path(__file__).parent / "s_monthly_sim.py")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="過去N ヶ月分のS8 snapshot生成 → s_monthly_sim を順番に実行")
    p.add_argument("--months", type=int, default=12, help="backfillする月数 (default: 12)")
    return p.parse_args()


def _months_to_backfill(n: int = 12) -> list:
    """
    対象: 前月末から遡ってNヶ月のsnapshot月（古い順）
    例: n=12, 2026-04実行時 → ["2025-04", "2025-05", ..., "2026-03"]
    """
    today = datetime.now(timezone.utc).date()
    y, m = today.year, today.month - 1
    if m == 0:
        m = 12
        y -= 1
    months = []
    for _ in range(n):
        months.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()
    return months


def run(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = parse_args()

    snapshot_months = _months_to_backfill(args.months)
    print(f"backfill: {snapshot_months[0]} → {snapshot_months[-1]}", flush=True)

    for snap_month in snapshot_months:
        # Step1: S8 as-of実行（snapshot生成）
        print(f"\n[S8] as-of={snap_month}", flush=True)
        r = subprocess.run(
            [PYTHON, S8],
            env={**__import__("os").environ, "S8_AS_OF": snap_month},
        )
        if r.returncode != 0:
            print(f"S8 failed for {snap_month}, abort", flush=True)
            sys.exit(1)

        # Step2: 翌月のsim実行
        y, mo = int(snap_month[:4]), int(snap_month[5:7])
        mo += 1
        if mo == 13:
            mo = 1
            y += 1
        sim_month = f"{y}-{mo:02d}"
        print(f"\n[sim] month={sim_month} (snapshot={snap_month})", flush=True)
        r = subprocess.run(
            [PYTHON, SIM],
            env={**__import__("os").environ, "SIM_MONTH": sim_month},
        )
        if r.returncode != 0:
            print(f"sim failed for {sim_month}, abort", flush=True)
            sys.exit(1)

    print("\nbackfill done", flush=True)


if __name__ == "__main__":
    run()
