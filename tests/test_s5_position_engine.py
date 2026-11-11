import concurrent.futures
from pathlib import Path

import pandas as pd
import pytest

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
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
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


def _setup_month(tmp_path):
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
    sig_dir = positions_root / "rsi_zone" / "a20" / "year=2026"
    sig_dir.mkdir(parents=True)
    pd.DataFrame({
        "time_utc": [times[0]], "entry_flag": [1], "side": ["BUY"], "session": ["TYO"],
    }).to_parquet(sig_dir / "01.parquet", index=False)
    return parquet_root, positions_root, events_root


def _process(tmp_path, env):
    roots = (tmp_path / "parquet_data", tmp_path / "positions", tmp_path / "pos_events")
    if not roots[0].exists():
        _setup_month(tmp_path)
    return s5._process_one("rsi_zone", "a20", 2026, 1, *roots, env)


def test_process_one_skips_when_fresh_and_trade_args_unchanged(tmp_path):
    env = {"RR_TP_PIPS": "50", "RR_SL_PIPS": "50"}
    assert _process(tmp_path, env) == "wrote"
    assert _process(tmp_path, env) == "skipped"


@pytest.mark.parametrize("changed", [
    {"PIP_SIZE": "0.1"},
    {"RR_TP_PIPS": "40"},
    {"RR_SL_PIPS": "15"},
    {"LOT_PER_ENTRY": "0.5"},
    {"MAX_ENTRIES_PER_STRAT": "1"},
    {"ABN_BURST_HL_PIPS": "25"},
    {"ABN_FORWARD_BLOCK_BARS": "1"},
    {"EOD_UTC": "00:20"},
])
def test_process_one_recomputes_when_any_trade_arg_changes(tmp_path, changed):
    base = {"RR_TP_PIPS": "50", "RR_SL_PIPS": "50"}
    assert _process(tmp_path, base) == "wrote"
    assert _process(tmp_path, {**base, **changed}) == "wrote"


def test_process_one_recomputes_output_without_recorded_args(tmp_path):
    parquet_root, positions_root, events_root = _setup_month(tmp_path)
    out_path = events_root / "rsi_zone" / "a20" / "year=2026" / "01.parquet"
    out_path.parent.mkdir(parents=True)
    # この変更より前に作った出力: 売買の引数を残していない
    pd.DataFrame({"type": ["open"]}).to_parquet(out_path, index=False)

    assert _process(tmp_path, {}) == "wrote"
    assert "close_price" in pd.read_parquet(out_path).columns


def test_process_one_removes_stale_output_when_no_event_remains(tmp_path):
    assert _process(tmp_path, {"RR_TP_PIPS": "50", "RR_SL_PIPS": "50"}) == "wrote"
    out_path = tmp_path / "pos_events" / "rsi_zone" / "a20" / "year=2026" / "01.parquet"
    assert out_path.exists()

    # 急変動の幅を全バーの値幅（10 pips）より小さくすると、どのバーでも建てられない
    assert _process(tmp_path, {"RR_TP_PIPS": "50", "RR_SL_PIPS": "50", "ABN_BURST_HL_PIPS": "5"}) == "skipped"
    assert not out_path.exists()


def test_process_one_write_failure_leaves_existing_output_untouched(monkeypatch, tmp_path):
    env = {"RR_TP_PIPS": "50", "RR_SL_PIPS": "50"}
    assert _process(tmp_path, env) == "wrote"
    out_path = tmp_path / "pos_events" / "rsi_zone" / "a20" / "year=2026" / "01.parquet"
    original = out_path.read_bytes()

    import pyarrow.parquet as pq
    monkeypatch.setattr(pq, "write_table", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))

    assert _process(tmp_path, {**env, "RR_TP_PIPS": "40"}) == "error"
    assert out_path.read_bytes() == original


def test_s5_tp_40_then_s6_without_args_gives_40_minus_spread(tmp_path):
    import core.s6_position_pips as s6

    parquet_root, positions_root, events_root = _setup_month(tmp_path)
    # 次のバーで建てた後、40 pips 上のバーで TP に届く
    bars_path = parquet_root / "year=2026" / "01.parquet"
    bars = pd.read_parquet(bars_path)
    bars.loc[3, "high"] = 100.0 + 0.45
    bars.to_parquet(bars_path, index=False)

    env = {"RR_TP_PIPS": "40", "RR_SL_PIPS": "50", "ABN_BURST_HL_PIPS": "100"}
    assert _process(tmp_path, env) == "wrote"
    out_path = events_root / "rsi_zone" / "a20" / "year=2026" / "01.parquet"
    assert s6._process_one(out_path, {}) == "wrote"

    out = pd.read_parquet(out_path)
    tp = out[(out["type"] == "close") & (out["abnormal"] == "TP")]
    assert len(tp) == 1
    assert tp["pips_net"].iloc[0] == pytest.approx(40 - 0.3)


def test_build_positions_opens_on_bar_after_entry_flag():
    env = {"PIP_SIZE": "0.01", "RR_TP_PIPS": "50", "RR_SL_PIPS": "50"}
    rows = [
        _row("2026-01-05T01:00", 100.00, 100.01, 99.99, 100.00, entry_flag=1, side="BUY"),
        _row("2026-01-05T01:05", 100.03, 100.04, 100.02, 100.03),
        _row("2026-01-05T01:10", 100.07, 100.08, 100.06, 100.07),
    ]
    opens = [o for o in s5._build_positions(rows, "rsi_zone", env) if o["type"] == "open"]
    assert len(opens) == 1
    assert opens[0]["time_utc"] == "2026-01-05T01:05"
    assert opens[0]["entry"] == 100.03


def test_iv_returns_default_for_non_numeric():
    assert s5._iv({"X": "bad"}, "X", 4) == 4
