"""
s4_ban_build.py — ALL Banリスト生成 + Jaccard重複排除

処理フロー:
  1. 直近N ヶ月の positions/ を読み、ALLでエントリー率を計算
  2. rate < min_rate または rate > max_rate の戦略をBan（rate_ban）
  3. 残った戦略（rate_ok）同士でJaccard類似度を計算し、閾値以上なら除外（jaccard_ban）
  4. Ban YAML を出力（ALL）

使い方:
  python3 s4_ban_build.py [--months 3] [--min-rate 0.01] [--max-rate 0.5]
                          [--jaccard 0.3] [--dry-run]
"""

import argparse
import datetime
import os
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.env_paths import get_backtest_data_root, get_parquet_root

SESSION = "all"
ENTRY_WINDOW_HOURS = (0, 17)


def _list_recent_parquet(parquet_root: Path, n: int) -> list[Path]:
    files = sorted(parquet_root.glob("year=*/*.parquet"))
    return files[-n:] if n < len(files) else files


def _parse_year_month(path: Path) -> tuple[int, int]:
    year = int(path.parent.name.split("=")[1])
    month = int(path.stem)
    return year, month


def _bars_in_window(parquet_path: Path) -> int:
    try:
        df = pd.read_parquet(parquet_path, columns=["time_utc"])
        df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
        h_start, h_end = ENTRY_WINDOW_HOURS
        mask = (df["time_utc"].dt.hour >= h_start) & (df["time_utc"].dt.hour < h_end)
        return int(mask.sum())
    except Exception:
        return 0


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _jaccard_dedup(
    strategy_timestamps: dict[str, set],
    thr: float,
) -> tuple[list[str], list[str]]:
    """
    Jaccard >= thr のペアを重複とみなし、後者を除外する。
    戻り値: (残すキーリスト, 除外されたキーリスト)
    """
    keys = list(strategy_timestamps.keys())
    removed = set()

    for i in range(len(keys)):
        if keys[i] in removed:
            continue
        for j in range(i + 1, len(keys)):
            if keys[j] in removed:
                continue
            j_val = _jaccard(
                strategy_timestamps[keys[i]],
                strategy_timestamps[keys[j]],
            )
            if j_val >= thr:
                removed.add(keys[j])

    survivors = [k for k in keys if k not in removed]
    removed_list = [k for k in keys if k in removed]
    return survivors, removed_list


def run(
    months: int, min_rate: float, max_rate: float, jaccard_thr: float, dry_run: bool
) -> None:

    data_root = get_backtest_data_root()
    parquet_root = get_parquet_root()
    positions_root = data_root / "positions"
    ban_dir = data_root / "ban"

    parquet_files = _list_recent_parquet(parquet_root, months)
    if not parquet_files:
        print("s4: no parquet files found", flush=True)
        return

    target_months = set(_parse_year_month(pf) for pf in parquet_files)
    print(
        f"s4: months={len(target_months)} "
        f"min_rate={min_rate} max_rate={max_rate} jaccard={jaccard_thr}",
        flush=True,
    )

    # 月ごとの00:00-17:00全バー数
    bars_by_m: dict[tuple, int] = {}
    for pf in parquet_files:
        ym = _parse_year_month(pf)
        bars_by_m[ym] = _bars_in_window(pf)

    if not positions_root.exists():
        print("s4: positions/ not found. Run S3 first.", flush=True)
        return

    # (tid, slug) ごとにエントリー数とタイムスタンプを集計
    stats: dict[tuple, dict] = {}
    timestamps: dict[tuple, set] = {}

    for tid_dir in sorted(positions_root.iterdir()):
        if not tid_dir.is_dir():
            continue
        tid = tid_dir.name
        for slug_dir in sorted(tid_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            slug = slug_dir.name
            for year_dir in slug_dir.glob("year=*"):
                year = int(year_dir.name.split("=")[1])
                for pos_file in year_dir.glob("*.parquet"):
                    month = int(pos_file.stem)
                    if (year, month) not in target_months:
                        continue
                    try:
                        df = pd.read_parquet(pos_file)
                        if "entry_flag" in df.columns:
                            df = df[df["entry_flag"] == 1]
                        key = (tid, slug)
                        if key not in stats:
                            stats[key] = {"entries": 0, "bars": 0}
                            timestamps[key] = set()
                        stats[key]["entries"] += len(df)
                        stats[key]["bars"] += bars_by_m.get((year, month), 0)
                        if "time_utc" in df.columns:
                            timestamps[key].update(df["time_utc"].astype(str).tolist())
                    except Exception as e:
                        print(f"  WARN {pos_file}: {e}", flush=True)

    if not stats:
        print("s4: no position data found. Run S3 first.", flush=True)
        return

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M")
    total_ban = 0

    pairs = sorted(stats)
    total_strategies = len(pairs)

    # Step1: rate Ban
    rate_ban = []
    rate_ok = []  # (tid, slug) のリスト
    for tid, slug in pairs:
        s = stats.get((tid, slug), {"entries": 0, "bars": 0})
        bars = s["bars"]
        entries = s["entries"]
        if bars == 0:
            rate_ban.append(
                {
                    "id": tid,
                    "slug": slug,
                    "rate": 0.0,
                    "entries": 0,
                    "bars": 0,
                    "reason": "no_data",
                }
            )
            continue
        rate = entries / bars
        if rate < min_rate:
            rate_ban.append(
                {
                    "id": tid,
                    "slug": slug,
                    "rate": round(rate, 6),
                    "entries": entries,
                    "bars": bars,
                    "reason": "low_rate",
                }
            )
        elif rate > max_rate:
            rate_ban.append(
                {
                    "id": tid,
                    "slug": slug,
                    "rate": round(rate, 6),
                    "entries": entries,
                    "bars": bars,
                    "reason": "high_rate",
                }
            )
        else:
            rate_ok.append((tid, slug))

    # Step2: Jaccard重複排除（rate_okのみ対象）
    ts_map = {
        f"{tid}/{slug}": timestamps.get((tid, slug), set()) for (tid, slug) in rate_ok
    }
    _survivors, removed_keys = _jaccard_dedup(ts_map, jaccard_thr)

    jaccard_ban = []
    for key in removed_keys:
        tid, slug = key.split("/", 1)
        s = stats.get((tid, slug), {"entries": 0, "bars": 0})
        bars = max(s["bars"], 1)
        jaccard_ban.append(
            {
                "id": tid,
                "slug": slug,
                "rate": round(s["entries"] / bars, 6),
                "entries": s["entries"],
                "bars": s["bars"],
                "reason": "jaccard_dedup",
            }
        )

    all_ban = rate_ban + jaccard_ban
    ok_count = total_strategies - len(all_ban)
    total_ban += len(all_ban)

    print(
        f"s4 [{SESSION}]: total={total_strategies} "
        f"rate_ban={len(rate_ban)} jaccard_ban={len(jaccard_ban)} ok={ok_count}",
        flush=True,
    )

    if dry_run:
        print("  -- rate ban (top 5) --")
        for item in rate_ban[:5]:
            print(
                f"  {item['id']}/{item['slug']}  rate={item['rate']}  reason={item['reason']}"
            )
        if len(rate_ban) > 5:
            print(f"  ... and {len(rate_ban)-5} more")
        print("  -- jaccard ban (top 5) --")
        for item in jaccard_ban[:5]:
            print(f"  {item['id']}/{item['slug']}  rate={item['rate']}")
        if len(jaccard_ban) > 5:
            print(f"  ... and {len(jaccard_ban)-5} more")
        print(f"s4: total banned = {total_ban}", flush=True)
        return

    ban_dir.mkdir(parents=True, exist_ok=True)
    out_path = ban_dir / f"entry_ban_all_{now_str}.yaml"
    doc = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "session": SESSION,
        "months": months,
        "min_rate": min_rate,
        "max_rate": max_rate,
        "jaccard_thr": jaccard_thr,
        "ban_count": len(all_ban),
        "entries": all_ban,
    }
    tmp = str(out_path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(doc, f, default_flow_style=False, allow_unicode=True)
    os.replace(tmp, out_path)
    print(f"s4: wrote {out_path}", flush=True)

    print(f"s4: total banned = {total_ban}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--min-rate", type=float, default=0.01)
    parser.add_argument("--max-rate", type=float, default=0.5)
    parser.add_argument("--jaccard", type=float, default=0.3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(
        months=args.months,
        min_rate=args.min_rate,
        max_rate=args.max_rate,
        jaccard_thr=args.jaccard,
        dry_run=args.dry_run,
    )
