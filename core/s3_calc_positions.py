"""
S3: エントリー・ポジション計算
strategies/<tid>/<slug>.py → parquet_data/positions/<tid>/<slug>/<year>/<mm>.parquet

環境変数:
  S3_MONTHS_LIMIT=N   : 直近N ヶ月のみ処理（未指定=全期間）
  S3_BAN_FILE=path    : Ban リスト YAML のパス（未指定=Ban なし）
  ENTRY_JOBS          : 並列度（数値または auto）
  ENTRY_INTERVAL_MIN  : エントリー間隔(分)。バーの分がこの倍数のときだけentry_flagを残す
                        （未指定=30、本番相当の判定間隔を想定したデフォルト。
                        5を指定すると旧来の5分足全バーエントリーに戻る）
"""

import argparse
import concurrent.futures
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir.parent))

from lib.env_paths import (
    get_backtest_data_root,
    ensure_dirs,
    get_parquet_root,
    get_strategies_root,
)
from lib.session_util import decide_session


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S3: 戦略をparquetに適用してエントリーを計算")
    p.add_argument("--months-limit", type=int, default=None, help="直近Nヶ月のみ処理 (env: S3_MONTHS_LIMIT, default: 全期間)")
    p.add_argument("--ban-file", default=None, help="BanリストYAMLのパス (env: S3_BAN_FILE, default: ban/の最新ファイルを自動解決)")
    p.add_argument("--jobs", default=None, help="並列度、数値または auto (env: ENTRY_JOBS, default: auto)")
    p.add_argument(
        "--entry-interval",
        type=int,
        default=None,
        help="エントリー間隔(分)。バーの分がこの倍数のときのみエントリー許可 (env: ENTRY_INTERVAL_MIN, default: 30)",
    )
    return p.parse_args()


_SESSION_PARAMS = {
    "SESS_TYO": "00:00-07:00",
    "SESS_LON": "07:00-13:00",
    "SESS_NYC": "13:00-17:00",
}


def _load_ban_set(ban_file: Optional[str]) -> set:
    """Ban リスト YAML を読み込み (tid, slug) のセットを返す。"""
    if not ban_file:
        return set()
    path = Path(ban_file)
    if not path.exists():
        print(f"s3: ban file not found: {path}", flush=True)
        return set()
    try:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)
        pairs = set()
        for item in (data.get("entries") if isinstance(data, dict) else data) or []:
            tid = item.get("id") or item.get("tid")
            slug = item.get("slug")
            if tid and slug:
                pairs.add((tid, slug))
        print(f"s3: loaded {len(pairs)} ban pairs from {path}", flush=True)
        return pairs
    except Exception as e:
        print(f"s3: failed to load ban file: {e}", flush=True)
        return set()


def _filter_recent_months(parquet_files: list, n: int) -> list:
    """直近 N ヶ月分の Parquet ファイルだけを返す。"""
    return parquet_files[-n:] if n < len(parquet_files) else parquet_files


def _load_strategy(path: Path):
    spec = importlib.util.spec_from_file_location("_strat", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _list_parquet_files(parquet_root: Path) -> list[Path]:
    files = sorted(parquet_root.glob("year=*/*.parquet"))
    return files


def _parse_year_month(parquet_path: Path) -> tuple[int, int]:
    year = int(parquet_path.parent.name.split("=")[1])
    month = int(parquet_path.stem)
    return year, month


def _add_session_column(df: pd.DataFrame) -> pd.DataFrame:
    if "time_utc" not in df.columns:
        df["session"] = ""
        return df

    def _sess(ts) -> str:
        try:
            t = pd.Timestamp(ts)
            return decide_session(t, _SESSION_PARAMS)
        except Exception:
            return ""

    df["session"] = df["time_utc"].map(_sess)
    return df


def _out_path(positions_root: Path, tid: str, slug: str, year: int, month: int) -> Path:
    return positions_root / tid / slug / f"year={year}" / f"{month:02d}.parquet"


def _process_strategy_month(
    strategy_path: Path,
    parquet_path: Path,
    out_path: Path,
    entry_interval_min: int,
) -> bool:
    if out_path.exists():
        in_mtime = max(strategy_path.stat().st_mtime, parquet_path.stat().st_mtime)
        if out_path.stat().st_mtime >= in_mtime:
            return False

    try:
        mod = _load_strategy(strategy_path)
        df = pd.read_parquet(parquet_path)

        if df.empty:
            return False

        result = mod.apply_entry_flag(df.copy(), getattr(mod, "PARAMS", {}))
        if result is None or result.empty:
            return False

        if "entry_flag" not in result.columns:
            result["entry_flag"] = 0
        result["entry_flag"] = (
            pd.to_numeric(result["entry_flag"], errors="coerce").fillna(0).astype(int)
        )

        if "buy_sell" in result.columns:
            s = result["buy_sell"].astype("string")
            result["side"] = s.where(s.isin(["BUY", "SELL"]), "")
        elif "side" in result.columns:
            s = result["side"].astype("string")
            result["side"] = s.where(s.isin(["BUY", "SELL"]), "")
        else:
            result["side"] = ""

        result = _add_session_column(result)
        result = result[result["entry_flag"] == 1].copy()
        if result.empty:
            return False

        if entry_interval_min > 0:
            minute = pd.to_datetime(result["time_utc"], utc=True, errors="coerce").dt.minute
            result = result[(minute % entry_interval_min) == 0].copy()
            if result.empty:
                return False

        out_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_parquet(out_path, index=False)
        return True

    except Exception as e:
        print(f"  ERROR {strategy_path.name} {parquet_path.name}: {e}", flush=True)
        return False


def _process_strategy(
    strategy_path: Path,
    parquet_files: list[Path],
    positions_root: Path,
    entry_interval_min: int,
) -> tuple[int, int]:
    try:
        mod = _load_strategy(strategy_path)
    except Exception as e:
        print(f"  LOAD ERROR {strategy_path}: {e}", flush=True)
        return 0, len(parquet_files)

    tid = strategy_path.parent.name
    slug = strategy_path.stem
    wrote = 0
    skipped = 0

    for pq in parquet_files:
        year, month = _parse_year_month(pq)
        out = _out_path(positions_root, tid, slug, year, month)
        if _process_strategy_month(strategy_path, pq, out, entry_interval_min):
            wrote += 1
        else:
            skipped += 1

    return wrote, skipped


def _jobs(raw: str | None = None) -> int:
    v = (raw if raw is not None else os.environ.get("ENTRY_JOBS", "auto")).strip().lower()
    if v in ("", "auto"):
        return os.cpu_count() or 1
    try:
        return max(1, int(v))
    except Exception:
        return os.cpu_count() or 1


def run(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = parse_args()

    ensure_dirs()

    parquet_root = get_parquet_root()
    strategies_root = get_strategies_root()
    positions_root = parquet_root.parent / "positions"

    parquet_files = _list_parquet_files(parquet_root)
    if not parquet_files:
        print("s3: no parquet files found", flush=True)
        return

    # 直近N ヶ月制限
    months_limit = str(args.months_limit) if args.months_limit is not None else os.environ.get("S3_MONTHS_LIMIT", "").strip()
    if months_limit:
        try:
            n = int(months_limit)
            parquet_files = _filter_recent_months(parquet_files, n)
            print(
                f"s3: limited to {len(parquet_files)} months (S3_MONTHS_LIMIT={n})",
                flush=True,
            )
        except ValueError:
            pass

    # Ban リスト
    ban_file = args.ban_file or os.environ.get("S3_BAN_FILE", "").strip()
    # 未指定の場合はbanディレクトリの最新ALLファイルを自動解決
    if not ban_file:
        ban_dir = get_backtest_data_root() / "ban"
        union_files = (
            sorted(ban_dir.glob("entry_ban_all_*.yaml")) if ban_dir.exists() else []
        )
        if union_files:
            ban_file = str(union_files[-1])
            print(f"s3: auto-resolved ban file: {union_files[-1].name}", flush=True)
    ban_set = _load_ban_set(ban_file if ban_file else None)

    strategy_files = sorted(strategies_root.glob("*/*.py"))
    if not strategy_files:
        print("s3: no strategy files found", flush=True)
        return

    # Ban 除外
    if ban_set:
        before = len(strategy_files)
        strategy_files = [
            sp for sp in strategy_files if (sp.parent.name, sp.stem) not in ban_set
        ]
        print(
            f"s3: {before - len(strategy_files)} strategies banned, {len(strategy_files)} remain",
            flush=True,
        )

    jobs = _jobs(args.jobs)
    entry_interval_min = (
        args.entry_interval
        if args.entry_interval is not None
        else int(os.environ.get("ENTRY_INTERVAL_MIN", "30"))
    )
    print(
        f"s3: strategies={len(strategy_files)} months={len(parquet_files)} jobs={jobs} "
        f"entry_interval_min={entry_interval_min}",
        flush=True,
    )

    total_wrote = 0
    total_skipped = 0
    total_errors = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as ex:
        futures = {
            ex.submit(
                _process_strategy, sp, parquet_files, positions_root, entry_interval_min
            ): sp
            for sp in strategy_files
        }
        for fut in concurrent.futures.as_completed(futures):
            sp = futures[fut]
            try:
                wrote, skipped = fut.result()
                total_wrote += wrote
                total_skipped += skipped
            except Exception as e:
                print(f"  FATAL {sp}: {e}", flush=True)
                total_errors += 1

    print(
        f"s3 done: wrote={total_wrote} skipped={total_skipped} errors={total_errors}",
        flush=True,
    )


if __name__ == "__main__":
    run()
