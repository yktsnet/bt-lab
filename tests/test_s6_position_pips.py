import concurrent.futures

import pandas as pd

import core.s6_position_pips as s6


def test_fv_iv_defaults_and_fallback():
    assert s6._fv({}, "X", 1.5) == 1.5
    assert s6._fv({"X": "bad"}, "X", 2.0) == 2.0
    assert s6._iv({"X": "5"}, "X", 1) == 5


def test_calc_pips_tp_and_sl_use_fixed_pip_values():
    env = {"RR_TP_PIPS": "30", "RR_SL_PIPS": "10", "PIP_SIZE": "0.01", "SPREAD_PIPS": "0.3"}
    df = pd.DataFrame([
        {"type": "open", "abnormal": "", "side": "BUY", "close_price": None, "entry": 100.0},
        {"type": "close", "abnormal": "TP", "side": "BUY", "close_price": 100.30, "entry": 100.0},
        {"type": "close", "abnormal": "SL", "side": "SELL", "close_price": 100.10, "entry": 100.0},
    ])
    out = s6._calc_pips(df, env)
    assert pd.isna(out.loc[0, "pips_net"])
    assert out.loc[1, "pips_net"] == 30 - 0.3
    assert out.loc[2, "pips_net"] == -10 - 0.3


def test_calc_pips_other_reason_computed_from_price_delta():
    env = {"RR_TP_PIPS": "30", "RR_SL_PIPS": "10", "PIP_SIZE": "0.01", "SPREAD_PIPS": "0.0"}
    df = pd.DataFrame([
        {"type": "close", "abnormal": "EOD", "side": "BUY", "close_price": 100.05, "entry": 100.00},
        {"type": "close", "abnormal": "NET", "side": "SELL", "close_price": 99.90, "entry": 100.00},
    ])
    out = s6._calc_pips(df, env)
    assert out.loc[0, "pips_net"] == 5.0  # (100.05-100.00)/0.01 = 5 pips BUY
    assert out.loc[1, "pips_net"] == 10.0  # SELL: -(99.90-100.00)/0.01 = 10 pips


def test_calc_pips_missing_price_yields_nan():
    env = {"RR_TP_PIPS": "30", "RR_SL_PIPS": "10", "PIP_SIZE": "0.01", "SPREAD_PIPS": "0.3"}
    df = pd.DataFrame([
        {"type": "close", "abnormal": "EOD", "side": "BUY", "close_price": None, "entry": 100.0},
    ])
    out = s6._calc_pips(df, env)
    assert pd.isna(out.loc[0, "pips_net"])


def test_process_one_writes_pips_net_column(tmp_path):
    path = tmp_path / "01.parquet"
    df = pd.DataFrame([
        {"type": "close", "abnormal": "TP", "side": "BUY", "close_price": 100.3, "entry": 100.0},
    ])
    df.to_parquet(path, index=False)

    env = {"RR_TP_PIPS": "30", "RR_SL_PIPS": "10", "PIP_SIZE": "0.01", "SPREAD_PIPS": "0.3"}
    result = s6._process_one(path, env)
    assert result == "wrote"

    out = pd.read_parquet(path)
    assert out.loc[0, "pips_net"] == 30 - 0.3


def test_process_one_skips_when_pips_net_already_populated(tmp_path):
    path = tmp_path / "01.parquet"
    df = pd.DataFrame([
        {"type": "close", "abnormal": "TP", "side": "BUY", "close_price": 100.3, "entry": 100.0, "pips_net": 29.7},
    ])
    df.to_parquet(path, index=False)

    result = s6._process_one(path, {})
    assert result == "skipped"


def test_run_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(s6.concurrent.futures, "ProcessPoolExecutor", concurrent.futures.ThreadPoolExecutor)

    events_dir = tmp_path / "pos_events" / "rsi_zone" / "a20" / "year=2026"
    events_dir.mkdir(parents=True)
    pd.DataFrame([
        {"type": "close", "abnormal": "TP", "side": "BUY", "close_price": 100.3, "entry": 100.0},
    ]).to_parquet(events_dir / "01.parquet", index=False)

    args = s6.argparse.Namespace(
        pip_size=None, tp_pips="30", sl_pips="10", max_entries=None,
        abn_burst_pips=None, abn_forward_block_bars=None, spread_pips="0.3", jobs=1,
    )
    s6.run(args)

    out = pd.read_parquet(events_dir / "01.parquet")
    assert out.loc[0, "pips_net"] == 30 - 0.3
