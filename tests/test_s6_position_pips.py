import concurrent.futures

import pandas as pd

import core.s6_position_pips as s6


def test_fv_iv_defaults_and_fallback():
    assert s6._fv({}, "X", 1.5) == 1.5
    assert s6._fv({"X": "bad"}, "X", 2.0) == 2.0
    assert s6._iv({"X": "5"}, "X", 1) == 5


def test_calc_pips_tp_and_sl_are_computed_from_price_delta_not_args():
    # TP/SL の引数に何を渡しても、価格差（40 pips / 15 pips）がそのまま出る
    env = {"RR_TP_PIPS": "30", "RR_SL_PIPS": "10", "PIP_SIZE": "0.01", "SPREAD_PIPS": "0.3"}
    df = pd.DataFrame([
        {"type": "open", "abnormal": "", "side": "BUY", "close_price": None, "entry": 100.0},
        {"type": "close", "abnormal": "TP", "side": "BUY", "close_price": 100.40, "entry": 100.0},
        {"type": "close", "abnormal": "SL", "side": "SELL", "close_price": 100.15, "entry": 100.0},
    ])
    out = s6._calc_pips(df, env)
    assert pd.isna(out.loc[0, "pips_net"])
    assert out.loc[1, "pips_net"] == 40 - 0.3
    assert out.loc[2, "pips_net"] == -15 - 0.3


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


def _events_file(tmp_path):
    path = tmp_path / "01.parquet"
    pd.DataFrame([
        {"type": "close", "abnormal": "TP", "side": "BUY", "close_price": 100.3, "entry": 100.0},
    ]).to_parquet(path, index=False)
    return path


def test_process_one_skips_when_done_with_same_pip_size_and_spread(tmp_path):
    path = _events_file(tmp_path)
    env = {"PIP_SIZE": "0.01", "SPREAD_PIPS": "0.3"}
    assert s6._process_one(path, env) == "wrote"
    assert s6._process_one(path, env) == "skipped"


def test_process_one_recomputes_when_spread_or_pip_size_changes(tmp_path):
    path = _events_file(tmp_path)
    assert s6._process_one(path, {"PIP_SIZE": "0.01", "SPREAD_PIPS": "0.3"}) == "wrote"

    assert s6._process_one(path, {"PIP_SIZE": "0.01", "SPREAD_PIPS": "1.0"}) == "wrote"
    assert pd.read_parquet(path).loc[0, "pips_net"] == 30 - 1.0

    assert s6._process_one(path, {"PIP_SIZE": "0.1", "SPREAD_PIPS": "1.0"}) == "wrote"
    assert pd.read_parquet(path).loc[0, "pips_net"] == 3 - 1.0


def test_process_one_recomputes_file_that_has_pips_net_but_no_recorded_args(tmp_path):
    # この変更より前に作ったファイル: pips_net は埋まっているが、付けたときの引数が残っていない
    path = tmp_path / "01.parquet"
    pd.DataFrame([
        {"type": "close", "abnormal": "TP", "side": "BUY", "close_price": 100.3, "entry": 100.0, "pips_net": 99.0},
    ]).to_parquet(path, index=False)

    assert s6._process_one(path, {"PIP_SIZE": "0.01", "SPREAD_PIPS": "0.3"}) == "wrote"
    assert pd.read_parquet(path).loc[0, "pips_net"] == 30 - 0.3


def test_process_one_keeps_s5_args_recorded_in_the_file(tmp_path):
    from core.s3_calc_positions import read_meta, write_parquet_atomic

    path = tmp_path / "01.parquet"
    df = pd.DataFrame([
        {"type": "close", "abnormal": "TP", "side": "BUY", "close_price": 100.3, "entry": 100.0},
    ])
    write_parquet_atomic(df, path, {"drip_sim.s5": {"tp_pips": 30.0}})

    assert s6._process_one(path, {}) == "wrote"
    meta = read_meta(path)
    assert meta["drip_sim.s5"] == {"tp_pips": 30.0}
    assert "drip_sim.s6" in meta


def test_process_one_write_failure_leaves_original_file_untouched(monkeypatch, tmp_path):
    path = _events_file(tmp_path)
    original = path.read_bytes()

    import pyarrow.parquet as pq
    monkeypatch.setattr(pq, "write_table", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))

    assert s6._process_one(path, {}) == "error"
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_run_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
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
    # close_price - entry = 30 pips。引数 tp_pips は効かない
    assert out.loc[0, "pips_net"] == 30 - 0.3
