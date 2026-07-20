"""
s5_position_engine.py — K4相当: ポジション計算

設計（セッション廃止版）:
- エントリー可能時間: 00:00-17:00 全バー（is_own_session=1）
- EOD: 17:00 固定
- session列: エントリーバーのセッション情報を引き継ぐ（s7集計用）
- TP/SL判定: 全バーで実施
"""

import argparse
import concurrent.futures
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.env_paths import (
    get_backtest_data_root as get_bt_data_dir,
    get_parquet_root as get_parquet_dir,
)
from lib.cli_common import add_trading_args, apply_env_overrides


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S5: ポジション計算（TP/SL/EOD/SPARK判定）")
    add_trading_args(p, lot=True, eod=True)
    p.add_argument("--jobs", type=int, default=None, help="並列プロセス数 (env: S5_JOBS, default: cpu_count)")
    return p.parse_args()


def _fv(env: dict, k: str, d: float) -> float:
    try:
        return float(env.get(k, d))
    except Exception:
        return float(d)


def _iv(env: dict, k: str, d: int) -> int:
    try:
        return int(float(env.get(k, d)))
    except Exception:
        return int(d)


def _hm(s) -> int | None:
    if not s:
        return None
    text = str(s).strip()
    if len(text) >= 16 and text[10] in ("T", " "):
        text = text[11:16]
    parts = text[:5].split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return None


def _parse_year_month(path: Path) -> tuple[int, int]:
    year = int(path.parent.name.split("=")[1])
    month = int(path.stem)
    return year, month


def _build_positions(rows: list[dict], ident: str, env: dict) -> list[dict]:
    pip = _fv(env, "PIP_SIZE", 0.01)
    tp_d = _fv(env, "RR_TP_PIPS", 30.0) * pip
    sl_d = _fv(env, "RR_SL_PIPS", 10.0) * pip
    lot = _fv(env, "LOT_PER_ENTRY", 0.1)
    maxn = _iv(env, "MAX_ENTRIES_PER_STRAT", 3)
    sp = _fv(env, "ABN_BURST_HL_PIPS", 30.0)
    spfw = _iv(env, "ABN_FORWARD_BLOCK_BARS", 3)
    eod_m = _hm(env.get("EOD_UTC", "17:00"))

    out = []
    opens = []
    pend = []
    net = 0
    blk = 0

    for i, r in enumerate(rows):
        t = r.get("time_utc", "")
        o = float(r["open"])
        h = float(r["high"])
        l = float(r["low"])
        c = float(r["close"])
        idx = _hm(str(t))

        # TP/SL 判定
        toc = []
        for j, p in enumerate(opens):
            if p.get("born", -1) >= i:
                continue
            if p["side"] == "BUY":
                if l <= p["sl"]:
                    toc.append((j, "SL"))
                elif h >= p["tp"]:
                    toc.append((j, "TP"))
            else:
                if h >= p["sl"]:
                    toc.append((j, "SL"))
                elif l <= p["tp"]:
                    toc.append((j, "TP"))

        for j, why in sorted(toc, key=lambda x: -x[0]):
            p = opens.pop(j)
            cp = p["tp"] if why == "TP" else p["sl"]
            net += -1 if p["side"] == "BUY" else 1
            out.append(
                {
                    "time_utc": t,
                    "id": ident,
                    "type": "close",
                    "abnormal": why,
                    "side": p["side"],
                    "lots": lot,
                    "position": net,
                    "entry": p["entry"],
                    "close_tp": None,
                    "close_sl": None,
                    "entry_time_utc": p.get("entry_time_utc", t),
                    "session": p.get("session", ""),
                    "close_price": cp,
                }
            )

        # SPARK / EOD
        flag = None
        if sp > 0 and (h - l) >= sp * pip:
            flag = "SPARK"
            blk = max(blk, spfw)
        elif eod_m is not None and idx is not None and idx >= eod_m:
            flag = "EOD"

        if flag and opens:
            while opens:
                p = opens.pop(0)
                net += -1 if p["side"] == "BUY" else 1
                out.append(
                    {
                        "time_utc": t,
                        "id": ident,
                        "type": "close",
                        "abnormal": flag,
                        "side": p["side"],
                        "lots": lot,
                        "position": net,
                        "entry": p["entry"],
                        "close_tp": None,
                        "close_sl": None,
                        "entry_time_utc": p.get("entry_time_utc", t),
                        "session": p.get("session", ""),
                        "close_price": c,
                    }
                )

        allow = (blk == 0) and (flag is None)
        if blk > 0:
            blk -= 1

        # pend キュー処理
        keep = []
        for q in pend:
            if q["at"] != i:
                keep.append(q)
                continue
            sd = q["side"]
            opp = [p for p in opens if p["side"] != sd]
            if opp:
                p = opp[0]
                opens.remove(p)
                net += -1 if p["side"] == "BUY" else 1
                out.append(
                    {
                        "time_utc": t,
                        "id": ident,
                        "type": "close",
                        "abnormal": "NET",
                        "side": p["side"],
                        "lots": lot,
                        "position": net,
                        "entry": p["entry"],
                        "close_tp": None,
                        "close_sl": None,
                        "entry_time_utc": p.get("entry_time_utc", t),
                        "session": p.get("session", ""),
                        "close_price": o,
                    }
                )
                continue
            if q["allow"] and allow and sum(1 for p in opens if p["side"] == sd) < maxn:
                tpv = o + tp_d if sd == "BUY" else o - tp_d
                slv = o - sl_d if sd == "BUY" else o + sl_d
                net += 1 if sd == "BUY" else -1
                entry_sess = q.get("session", "")
                opens.append(
                    {
                        "side": sd,
                        "entry": o,
                        "tp": tpv,
                        "sl": slv,
                        "born": i,
                        "entry_time_utc": t,
                        "session": entry_sess,
                    }
                )
                out.append(
                    {
                        "time_utc": t,
                        "id": ident,
                        "type": "open",
                        "abnormal": "",
                        "side": sd,
                        "lots": lot,
                        "position": net,
                        "entry": o,
                        "close_tp": tpv,
                        "close_sl": slv,
                        "entry_time_utc": t,
                        "session": entry_sess,
                        "close_price": None,
                    }
                )
        pend = keep

        # 次バー執行キューに積む（00:00-17:00 全バー対象）
        fl = int(r.get("entry_flag", 0)) == 1
        own = int(r.get("is_own_session", 0)) == 1
        sd_now = str(r.get("side", "")).strip().upper()
        if own and fl and sd_now in ("BUY", "SELL") and i + 1 < len(rows):
            pend.append(
                {
                    "at": i + 1,
                    "side": sd_now,
                    "allow": allow,
                    "session": r.get("session", ""),
                }
            )

    return out


def _process_one(
    tid: str,
    slug: str,
    year: int,
    month: int,
    parquet_root: Path,
    positions_root: Path,
    events_root: Path,
    env: dict,
) -> str:
    pq_path = parquet_root / f"year={year}" / f"{month:02d}.parquet"
    sig_path = positions_root / tid / slug / f"year={year}" / f"{month:02d}.parquet"
    out_path = events_root / tid / slug / f"year={year}" / f"{month:02d}.parquet"

    if not pq_path.exists() or not sig_path.exists():
        return "skipped"

    if out_path.exists():
        in_mtime = max(pq_path.stat().st_mtime, sig_path.stat().st_mtime)
        if out_path.stat().st_mtime >= in_mtime:
            return "skipped"

    try:
        bars = pd.read_parquet(
            pq_path, columns=["time_utc", "open", "high", "low", "close"]
        )
        bars["time_utc"] = pd.to_datetime(bars["time_utc"], utc=True)
        bars = bars.sort_values("time_utc").reset_index(drop=True)

        sig = pd.read_parquet(
            sig_path, columns=["time_utc", "entry_flag", "side", "session"]
        )
        sig["time_utc"] = pd.to_datetime(sig["time_utc"], utc=True)

        df = bars.merge(
            sig[["time_utc", "entry_flag", "side", "session"]],
            on="time_utc",
            how="left",
        )
        df["entry_flag"] = df["entry_flag"].fillna(0).astype(int)
        df["side"] = df["side"].fillna("").astype(str)
        df["session"] = df["session"].fillna("").astype(str)

        # セッション廃止: 00:00-17:00 全バーをエントリー可能に
        df["is_own_session"] = (
            (df["time_utc"].dt.hour >= 0) & (df["time_utc"].dt.hour < 17)
        ).astype(int)

        rows = df.to_dict("records")
        result = _build_positions(rows, ident=tid, env=env)

        if not result:
            return "skipped"

        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(result).to_parquet(out_path, index=False)
        return "wrote"

    except Exception as e:
        print(f"  ERROR {tid}/{slug} {year}/{month:02d}: {e}", flush=True)
        return "error"


def run(args: argparse.Namespace | None = None) -> None:
    if args is None:
        args = parse_args()

    data_root = get_bt_data_dir()
    parquet_root = get_parquet_dir()
    positions_root = data_root / "positions"
    events_root = data_root / "pos_events"

    env = apply_env_overrides(dict(os.environ), args)

    parquet_files = sorted(parquet_root.glob("year=*/*.parquet"))
    if not parquet_files:
        print("s5: no parquet files", flush=True)
        return

    tasks = []
    for tid_dir in sorted(positions_root.iterdir()):
        if not tid_dir.is_dir():
            continue
        tid = tid_dir.name
        for slug_dir in sorted(tid_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            slug = slug_dir.name
            for pf in parquet_files:
                year, month = _parse_year_month(pf)
                tasks.append((tid, slug, year, month))

    if not tasks:
        print("s5: no tasks found", flush=True)
        return

    jobs = args.jobs if args.jobs is not None else _iv(env, "S5_JOBS", os.cpu_count() or 1)
    print(f"s5: tasks={len(tasks)} jobs={jobs}", flush=True)

    wrote = skipped = errors = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as ex:
        futures = {
            ex.submit(
                _process_one,
                tid,
                slug,
                year,
                month,
                parquet_root,
                positions_root,
                events_root,
                env,
            ): (tid, slug, year, month)
            for tid, slug, year, month in tasks
        }
        for fut in concurrent.futures.as_completed(futures):
            try:
                r = fut.result()
                if r == "wrote":
                    wrote += 1
                elif r == "skipped":
                    skipped += 1
                else:
                    errors += 1
            except Exception as e:
                key = futures[fut]
                print(f"  FATAL {key}: {e}", flush=True)
                errors += 1

    print(f"s5 done: wrote={wrote} skipped={skipped} errors={errors}", flush=True)


if __name__ == "__main__":
    run()
