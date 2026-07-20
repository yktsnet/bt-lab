"""合成M5バーデータの生成スクリプト。

シード付き乱数ウォークで生成した架空のOHLCデータ。実市場データではない。
出力はs1b(core/s1_export_parquet.py)が読む `*_m5_*.jsonl` 命名規則に従う。

使い方:
    python3 examples/sample/generate_data.py

価格系列はシード固定で毎回同じになるが、開始日は実行時点から逆算した直近の月曜
(3週間前)を使う。s8の既定ランキング窓(直近12ヶ月)に収まるようにするため。
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20250101
DAYS = 10


def _last_monday_weeks_ago(weeks: int) -> datetime:
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    monday = now - timedelta(days=now.weekday())
    return monday - timedelta(weeks=weeks)


START = _last_monday_weeks_ago(3)  # 直近の月曜から3週間前(bt.py s8の既定rank-months=12に収まるように)
OUT_PATH = Path(__file__).resolve().parent / "data" / f"sample_m5_{START.year}.jsonl"
SESSION_START_MIN = 0     # 00:00 UTC
SESSION_END_MIN = 17 * 60  # 17:00 UTC
BAR_MINUTES = 5
BASE_PRICE = 150.00
PIP = 0.01
VOL_PIPS_PER_BAR = 3.0  # 1バーあたりの典型的な値幅(pips)


def generate_day(rng: random.Random, day_start: datetime, open_price: float):
    rows = []
    price = open_price
    minute = SESSION_START_MIN
    while minute < SESSION_END_MIN:
        t = day_start + timedelta(minutes=minute)
        drift = rng.gauss(0, 1) * VOL_PIPS_PER_BAR * PIP
        o = price
        c = price + drift
        hi = max(o, c) + abs(rng.gauss(0, 1)) * VOL_PIPS_PER_BAR * PIP * 0.5
        lo = min(o, c) - abs(rng.gauss(0, 1)) * VOL_PIPS_PER_BAR * PIP * 0.5
        rows.append({
            "time_utc": t.isoformat().replace("+00:00", "Z"),
            "open": round(o, 3),
            "high": round(hi, 3),
            "low": round(lo, 3),
            "close": round(c, 3),
        })
        price = c
        minute += BAR_MINUTES
    return rows, price


def main() -> None:
    rng = random.Random(SEED)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    price = BASE_PRICE
    all_rows = []
    d = START
    business_days = 0
    while business_days < DAYS:
        if d.weekday() < 5:  # 月〜金のみ
            rows, price = generate_day(rng, d, price)
            all_rows.extend(rows)
            business_days += 1
        d += timedelta(days=1)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row) + "\n")

    print(f"wrote {OUT_PATH} rows={len(all_rows)} days={DAYS}")


if __name__ == "__main__":
    main()
