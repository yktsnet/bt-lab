import json
import sys
from pathlib import Path

import pandas as pd

current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir.parent))

from lib.env_paths import ensure_dirs, get_bt_data_root, get_parquet_root


def run() -> None:
    ensure_dirs()
    src_root = get_bt_data_root()
    out_root = get_parquet_root()

    files = sorted(src_root.glob("*_m5_*.jsonl"))
    if not files:
        print("no jsonl files")
        return

    for path in files:
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass

        if not rows:
            continue

        df = pd.DataFrame(rows)
        df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True, errors="coerce")
        df = df.dropna(subset=["time_utc"]).sort_values("time_utc")
        df = df.drop_duplicates(subset=["time_utc"], keep="last")

        for (year, month), group in df.groupby(
            [df["time_utc"].dt.year, df["time_utc"].dt.month],
            sort=True,
        ):
            out_dir = out_root / f"year={int(year)}"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{int(month):02d}.parquet"
            group = group.reset_index(drop=True)
            group.to_parquet(out_path, index=False)
            print(f"wrote {out_path} rows={len(group)}")


if __name__ == "__main__":
    run()
