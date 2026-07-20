"""
s_monthly_sim.py — Monthly backtest simulation

Runs snapshot strategies with pips_avg_per_entry >= 0.3 over past 12 complete months.
Output: bt_data/backtest/monthly/{YYYY-MM}/ALL/{date}.csv

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
from lib.features import compute_all
from lib.cli_common import add_trading_args, apply_env_overrides


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="月次バックテストシミュレーション")
    add_trading_args(p, spread=True)
    p.add_argument("--month", default=None, help="対象月 YYYY-MM (env: SIM_MONTH, default: 直近12ヶ月)")
    return p.parse_args()

SESSION = "ALL"
START_HOUR = 0
END_HOUR = 17
EOD_UTC = "17:00"


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


def _hm(s):
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


def _build_positions(rows: list, env: dict) -> list:
    pip = _fv(env, "PIP_SIZE", 0.01)
    tp_d = _fv(env, "RR_TP_PIPS", 30.0) * pip
    sl_d = _fv(env, "RR_SL_PIPS", 10.0) * pip
    tp_p = _fv(env, "RR_TP_PIPS", 30.0)
    sl_p = _fv(env, "RR_SL_PIPS", 10.0)
    spread = _fv(env, "SPREAD_PIPS", 0.3)
    maxn = _iv(env, "MAX_ENTRIES_PER_STRAT", 3)
    sp = _fv(env, "ABN_BURST_HL_PIPS", 30.0)
    spfw = _iv(env, "ABN_FORWARD_BLOCK_BARS", 3)
    eod_m = _hm(EOD_UTC)

    out = []
    opens = []
    pend = []
    blk = 0

    for i, r in enumerate(rows):
        t = r.get("time_utc", "")
        o = float(r["open"])
        h = float(r["high"])
        l = float(r["low"])
        c = float(r["close"])
        idx = _hm(str(t))

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
            gross = tp_p if why == "TP" else -sl_p
            out.append({"why": why, "pips_net": round(gross - spread, 2)})

        flag = None
        if sp > 0 and (h - l) >= sp * pip:
            flag = "SPARK"
            blk = max(blk, spfw)
        elif eod_m is not None and idx is not None and idx >= eod_m:
            flag = "EOD"

        if flag and opens:
            while opens:
                p = opens.pop(0)
                sign = 1.0 if p["side"] == "BUY" else -1.0
                gross = sign * (c - p["entry"]) / pip
                out.append({"why": flag, "pips_net": round(gross - spread, 2)})

        allow = (blk == 0) and (flag is None)
        if blk > 0:
            blk -= 1

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
                sign = 1.0 if p["side"] == "BUY" else -1.0
                gross = sign * (o - p["entry"]) / pip
                out.append({"why": "NET", "pips_net": round(gross - spread, 2)})
                continue
            if q["allow"] and allow and sum(1 for p in opens if p["side"] == sd) < maxn:
                tpv = o + tp_d if sd == "BUY" else o - tp_d
                slv = o - sl_d if sd == "BUY" else o + sl_d
                opens.append({"side": sd, "entry": o, "tp": tpv, "sl": slv, "born": i})
        pend = keep

        fl = int(r.get("entry_flag", 0)) == 1
        own = int(r.get("is_own_session", 0)) == 1
        sd_now = str(r.get("side", "")).strip().upper()
        if sd_now not in ("BUY", "SELL"):
            sd_now = "BUY"
        if own and fl and i + 1 < len(rows):
            pend.append({"at": i + 1, "side": sd_now, "allow": allow})

    return out


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
        written = 0

        for day in days:
            out_path = monthly_root / f"{month.year}-{month.month:02d}" / SESSION / f"{day}.csv"
            if out_path.exists():
                continue

            df_today = df_month[df_month["time_utc"].dt.date == day].copy()
            if df_today.empty:
                continue

            all_computed = compute_all(df_today)
            for k, v in all_computed.items():
                if k not in df_today.columns:
                    df_today[k] = v.values

            df_sess = (
                df_today[
                    (df_today["time_utc"].dt.hour >= START_HOUR)
                    & (df_today["time_utc"].dt.hour < END_HOUR)
                ]
                .copy()
                .reset_index(drop=True)
            )
            if df_sess.empty:
                continue

            records = []
            for sf in strategy_files:
                tid = sf.parent.name
                slug = sf.stem

                try:
                    mod = _load_strategy(sf)
                    result = mod.apply_entry_flag(df_sess.copy(), getattr(mod, "PARAMS", {}))
                    if result is None or result.empty:
                        records.append({"tid": tid, "slug": slug, "entries": 0, "pips_sum": 0.0, "pips_avg": ""})
                        continue

                    result["entry_flag"] = (
                        pd.to_numeric(result.get("entry_flag", 0), errors="coerce")
                        .fillna(0)
                        .astype(int)
                    )
                    if "buy_sell" in result.columns:
                        result["side"] = result["buy_sell"].fillna("BUY").astype(str)
                    elif "side" not in result.columns:
                        result["side"] = "BUY"
                    else:
                        result["side"] = result["side"].fillna("BUY").astype(str)

                    sig = result[["time_utc", "entry_flag", "side"]].copy()
                    df_full = df_today.merge(sig, on="time_utc", how="left")
                    df_full["entry_flag"] = df_full["entry_flag"].fillna(0).astype(int)
                    df_full["side"] = df_full["side"].fillna("").astype(str)
                    df_full["is_own_session"] = (
                        (df_full["time_utc"].dt.hour >= START_HOUR)
                        & (df_full["time_utc"].dt.hour < END_HOUR)
                    ).astype(int)

                    closes = _build_positions(df_full.to_dict("records"), env)
                    entries = len(closes)
                    pips_sum = sum(c["pips_net"] for c in closes if c.get("pips_net") is not None)
                    pips_avg = round(pips_sum / entries, 2) if entries > 0 else ""

                    records.append({"tid": tid, "slug": slug, "entries": entries, "pips_sum": round(pips_sum, 2), "pips_avg": pips_avg})
                except Exception as e:
                    print(f"  WARN ALL/{sf.name} {day}: {e}", flush=True)
                    records.append({"tid": tid, "slug": slug, "entries": 0, "pips_sum": 0.0, "pips_avg": ""})

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
