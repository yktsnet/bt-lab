import concurrent.futures
from pathlib import Path

import pandas as pd

import core.s5_position_engine as s5


def test_hm_parses_hhmm():
    assert s5._hm("07:30") == 7 * 60 + 30


def test_hm_parses_iso_timestamp_with_t_separator():
    assert s5._hm("2026-01-05T13:05:00Z") == 13 * 60 + 5


def test_hm_parses_iso_timestamp_with_space_separator():
    assert s5._hm("2026-01-05 09:00:00") == 9 * 60


def test_hm_none_or_empty_returns_none():
    assert s5._hm(None) is None
    assert s5._hm("") is None


def test_fv_iv_defaults_and_fallback():
    assert s5._fv({}, "X", 1.5) == 1.5
    assert s5._fv({"X": "3.5"}, "X", 1.0) == 3.5
    assert s5._fv({"X": "bad"}, "X", 2.0) == 2.0
    assert s5._iv({"X": "5"}, "X", 1) == 5
    assert s5._iv({}, "X", 7) == 7


def _row(t, o, h, l, c, entry_flag=0, side="", own=1):
    return {
        "time_utc": t, "open": o, "high": h, "low": l, "close": c,
        "entry_flag": entry_flag, "side": side, "is_own_session": own, "session": "TYO",
    }


def test_build_positions_opens_then_hits_tp():
    env = {"PIP_SIZE": "0.01", "RR_TP_PIPS": "10", "RR_SL_PIPS": "5", "LOT_PER_ENTRY": "0.1", "MAX_ENTRIES_PER_STRAT": "3"}
    rows = [
        _row("2026-01-05T01:00", 100.0, 100.05, 99.95, 100.0, entry_flag=1, side="BUY"),
        _row("2026-01-05T01:05", 100.0, 100.05, 99.95, 100.02),  # executes the pending open here
        _row("2026-01-05T01:10", 100.10, 100.15, 100.05, 100.12),  # high >= tp(100.10) -> TP
    ]
    out = s5._build_positions(rows, "rsi_zone", env)
    types = [o["type"] for o in out]
    assert types == ["open", "close"]
    close = out[1]
    assert close["abnormal"] == "TP"
    assert close["side"] == "BUY"


def test_build_positions_hits_sl():
    env = {"PIP_SIZE": "0.01", "RR_TP_PIPS": "10", "RR_SL_PIPS": "5"}
    rows = [
        _row("2026-01-05T01:00", 100.0, 100.05, 99.95, 100.0, entry_flag=1, side="SELL"),
        _row("2026-01-05T01:05", 100.0, 100.05, 99.95, 100.0),
        _row("2026-01-05T01:10", 100.10, 100.20, 100.05, 100.15),  # SELL sl = entry+0.05=100.05, high>=sl
    ]
    out = s5._build_positions(rows, "rsi_zone", env)
    close = [o for o in out if o["type"] == "close"][0]
    assert close["abnormal"] == "SL"
    assert close["side"] == "SELL"


def test_build_positions_eod_forces_close():
    env = {"PIP_SIZE": "0.01", "RR_TP_PIPS": "50", "RR_SL_PIPS": "50", "EOD_UTC": "17:00"}
    rows = [
        _row("2026-01-05T16:50", 100.0, 100.05, 99.95, 100.0, entry_flag=1, side="BUY"),
        _row("2026-01-05T16:55", 100.0, 100.05, 99.95, 100.0),  # pending order executes -> opens
        _row("2026-01-05T17:00", 100.0, 100.05, 99.95, 100.0),  # EOD reached -> force close
    ]
    out = s5._build_positions(rows, "rsi_zone", env)
    aborts = [o["abnormal"] for o in out if o["type"] == "close"]
    assert "EOD" in aborts


def test_build_positions_spark_blocks_forward_entries():
    env = {"PIP_SIZE": "0.01", "RR_TP_PIPS": "50", "RR_SL_PIPS": "50", "ABN_BURST_HL_PIPS": "5", "ABN_FORWARD_BLOCK_BARS": "2"}
    rows = [
        _row("2026-01-05T01:00", 100.0, 100.10, 99.90, 100.0),  # burst: h-l=0.20 >= 5*0.01=0.05 -> SPARK
        _row("2026-01-05T01:05", 100.0, 100.01, 99.99, 100.0, entry_flag=1, side="BUY"),  # blocked
        _row("2026-01-05T01:10", 100.0, 100.01, 99.99, 100.0),
    ]
    out = s5._build_positions(rows, "rsi_zone", env)
    assert all(o["type"] != "open" for o in out)  # blocked, never opened


def test_build_positions_max_entries_per_strat_caps_opens():
    env = {"PIP_SIZE": "0.01", "RR_TP_PIPS": "50", "RR_SL_PIPS": "50", "MAX_ENTRIES_PER_STRAT": "1"}
    rows = [
        _row("2026-01-05T01:00", 100.0, 100.01, 99.99, 100.0, entry_flag=1, side="BUY"),
        _row("2026-01-05T01:05", 100.0, 100.01, 99.99, 100.0, entry_flag=1, side="BUY"),
        _row("2026-01-05T01:10", 100.0, 100.01, 99.99, 100.0, entry_flag=1, side="BUY"),
        _row("2026-01-05T01:15", 100.0, 100.01, 99.99, 100.0),
    ]
    out = s5._build_positions(rows, "rsi_zone", env)
    opens = [o for o in out if o["type"] == "open"]
    assert len(opens) == 1


def test_process_one_writes_events_parquet(tmp_path):
    parquet_root = tmp_path / "parquet_data"
    positions_root = tmp_path / "positions"
    events_root = tmp_path / "pos_events"

    times = pd.date_range("2026-01-05", periods=10, freq="5min", tz="UTC")
    bars = pd.DataFrame({
        "time_utc": times,
        "open": [100.0] * 10, "high": [100.05] * 10, "low": [99.95] * 10, "close": [100.0] * 10,
    })
    (parquet_root / "year=2026").mkdir(parents=True)
    bars.to_parquet(parquet_root / "year=2026" / "01.parquet", index=False)

    sig = pd.DataFrame({
        "time_utc": [times[0]],
        "entry_flag": [1], "side": ["BUY"], "session": ["TYO"],
    })
    sig_dir = positions_root / "rsi_zone" / "a20" / "year=2026"
    sig_dir.mkdir(parents=True)
    sig.to_parquet(sig_dir / "01.parquet", index=False)

    env = {"PIP_SIZE": "0.01", "RR_TP_PIPS": "50", "RR_SL_PIPS": "50"}
    result = s5._process_one("rsi_zone", "a20", 2026, 1, parquet_root, positions_root, events_root, env)
    assert result == "wrote"

    out_path = events_root / "rsi_zone" / "a20" / "year=2026" / "01.parquet"
    assert out_path.exists()
    df = pd.read_parquet(out_path)
    assert (df["type"] == "open").any()


def test_process_one_skips_when_inputs_missing(tmp_path):
    result = s5._process_one(
        "rsi_zone", "a20", 2026, 1,
        tmp_path / "parquet_data", tmp_path / "positions", tmp_path / "pos_events", {},
    )
    assert result == "skipped"


def test_run_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(s5.concurrent.futures, "ProcessPoolExecutor", concurrent.futures.ThreadPoolExecutor)

    parquet_root = tmp_path / "parquet_data"
    times = pd.date_range("2026-01-05", periods=10, freq="5min", tz="UTC")
    bars = pd.DataFrame({
        "time_utc": times,
        "open": [100.0] * 10, "high": [100.05] * 10, "low": [99.95] * 10, "close": [100.0] * 10,
    })
    (parquet_root / "year=2026").mkdir(parents=True)
    bars.to_parquet(parquet_root / "year=2026" / "01.parquet", index=False)

    sig = pd.DataFrame({"time_utc": [times[0]], "entry_flag": [1], "side": ["BUY"], "session": ["TYO"]})
    sig_dir = tmp_path / "positions" / "rsi_zone" / "a20" / "year=2026"
    sig_dir.mkdir(parents=True)
    sig.to_parquet(sig_dir / "01.parquet", index=False)

    args = s5.argparse.Namespace(
        pip_size=None, tp_pips=None, sl_pips=None, max_entries=None,
        abn_burst_pips=None, abn_forward_block_bars=None, lot=None, eod_utc=None, jobs=1,
    )
    s5.run(args)

    out_path = tmp_path / "pos_events" / "rsi_zone" / "a20" / "year=2026" / "01.parquet"
    assert out_path.exists()
