import concurrent.futures
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import core.s2_gen_strategies as s2
import core.s3_calc_positions as s3


def _bars(n=40, start="2026-01-05"):
    times = pd.date_range(start, periods=n, freq="5min", tz="UTC")
    close = 100 + np.cumsum(np.random.RandomState(0).randn(n) * 0.01)
    return pd.DataFrame({
        "time_utc": times,
        "open": close,
        "high": close + 0.02,
        "low": close - 0.02,
        "close": close,
        "rsi14": np.tile([10, 90], n // 2),  # alternates buy/sell zone
    })


STRATEGY_SRC = '''
import pandas as pd

KIND = "rsi_zone"

def apply_entry_flag(df, params):
    df = df.copy()
    df["entry_flag"] = (df["rsi14"] <= 20).astype(int)
    df["buy_sell"] = df["entry_flag"].map({1: "BUY", 0: ""})
    return df

PARAMS = {"rsi_period": 14}
'''


def test_filter_recent_months_keeps_last_n():
    files = [Path(f"{i}.parquet") for i in range(5)]
    assert s3._filter_recent_months(files, 2) == files[-2:]
    assert s3._filter_recent_months(files, 10) == files


def test_load_ban_set_missing_file_returns_empty(tmp_path, capsys):
    result = s3._load_ban_set(str(tmp_path / "nope.yaml"))
    assert result == set()
    assert "not found" in capsys.readouterr().out


def test_load_ban_set_no_path_returns_empty():
    assert s3._load_ban_set(None) == set()
    assert s3._load_ban_set("") == set()


def test_load_ban_set_parses_entries(tmp_path):
    ban_path = tmp_path / "ban.yaml"
    ban_path.write_text(yaml.dump({
        "entries": [
            {"id": "rsi_zone", "slug": "a"},
            {"tid": "rsi_zone", "slug": "b"},
            {"id": "rsi_zone"},  # missing slug -> ignored
        ]
    }))
    result = s3._load_ban_set(str(ban_path))
    assert result == {("rsi_zone", "a"), ("rsi_zone", "b")}


def test_add_session_column_without_time_utc_is_empty_string():
    df = pd.DataFrame({"close": [1.0, 2.0]})
    out = s3._add_session_column(df)
    assert (out["session"] == "").all()


def test_add_session_column_assigns_expected_sessions():
    times = pd.to_datetime(["2026-01-05T03:00:00Z", "2026-01-05T10:00:00Z"])
    df = pd.DataFrame({"time_utc": times})
    out = s3._add_session_column(df)
    assert list(out["session"]) == ["TYO", "LON"]


def test_out_path_and_parse_year_month_roundtrip(tmp_path):
    out = s3._out_path(tmp_path, "rsi_zone", "a20", 2026, 3)
    assert out == tmp_path / "rsi_zone" / "a20" / "year=2026" / "03.parquet"
    assert s3._parse_year_month(Path("root/year=2026/03.parquet")) == (2026, 3)


def test_jobs_auto_and_explicit_and_invalid(monkeypatch):
    monkeypatch.delenv("ENTRY_JOBS", raising=False)
    assert s3._jobs("auto") >= 1
    assert s3._jobs("4") == 4
    assert s3._jobs("not-a-number") >= 1  # falls back to cpu_count


def test_process_strategy_month_writes_only_entry_flag_rows(tmp_path):
    strategy_path = tmp_path / "a20.py"
    strategy_path.write_text(STRATEGY_SRC)
    parquet_path = tmp_path / "01.parquet"
    _bars().to_parquet(parquet_path, index=False)
    out_path = tmp_path / "out.parquet"

    wrote = s3._process_strategy_month(strategy_path, parquet_path, out_path, entry_interval_min=0)
    assert wrote is True

    result = pd.read_parquet(out_path)
    assert (result["entry_flag"] == 1).all()
    assert set(result["side"]) <= {"BUY"}


def test_process_strategy_month_entry_interval_filters_minutes(tmp_path):
    strategy_path = tmp_path / "a20.py"
    strategy_path.write_text(STRATEGY_SRC)
    parquet_path = tmp_path / "01.parquet"
    _bars().to_parquet(parquet_path, index=False)
    out_path = tmp_path / "out.parquet"

    # entry_interval_min=30 keeps only bars whose minute is a multiple of 30
    wrote = s3._process_strategy_month(strategy_path, parquet_path, out_path, entry_interval_min=30)
    if wrote:
        result = pd.read_parquet(out_path)
        assert (result["time_utc"].dt.minute % 30 == 0).all()


def test_process_strategy_month_skips_when_output_is_fresh(tmp_path):
    strategy_path = tmp_path / "a20.py"
    strategy_path.write_text(STRATEGY_SRC)
    parquet_path = tmp_path / "01.parquet"
    _bars().to_parquet(parquet_path, index=False)
    out_path = tmp_path / "out.parquet"

    assert s3._process_strategy_month(strategy_path, parquet_path, out_path, entry_interval_min=0) is True
    # second call: out_path mtime >= inputs -> should be skipped (returns False)
    assert s3._process_strategy_month(strategy_path, parquet_path, out_path, entry_interval_min=0) is False


def test_process_strategy_month_honors_real_rsi_zone_template_contract(monkeypatch, tmp_path):
    """実在するstrategies_md/oscillator/rsi_zone/template.pyがS2で生成され、S3を通した際に
    apply_entry_flagの3カラム契約(entry_flag/buy_sell/trend_dir, conventions.md)を満たすこと。"""
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    s2.main()

    strategy_path = tmp_path / "strategies" / "rsi_zone" / "distance_from_mid20_rsi_period14.py"
    assert strategy_path.exists()

    # rsi14: distance_from_mid=20 -> upper=70(SELL zone), lower=30(BUY zone)
    times = pd.date_range("2026-01-05", periods=6, freq="5min", tz="UTC")
    df = pd.DataFrame({
        "time_utc": times,
        "open": [100.0] * 6, "high": [100.05] * 6, "low": [99.95] * 6, "close": [100.0] * 6,
        "rsi14": [90, 90, 50, 50, 10, 10],
    })
    parquet_path = tmp_path / "bars.parquet"
    df.to_parquet(parquet_path, index=False)
    out_path = tmp_path / "out.parquet"

    wrote = s3._process_strategy_month(strategy_path, parquet_path, out_path, entry_interval_min=0)
    assert wrote is True

    result = pd.read_parquet(out_path)
    assert set(result.columns) >= {"entry_flag", "buy_sell", "trend_dir"}
    assert (result["entry_flag"] == 1).all()
    assert set(result["buy_sell"]) == {"SELL", "BUY"}
    assert (result.loc[result["buy_sell"] == "SELL", "trend_dir"] == "UP").all()
    assert (result.loc[result["buy_sell"] == "BUY", "trend_dir"] == "DOWN").all()


def test_run_end_to_end_writes_positions(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("ENTRY_INTERVAL_MIN", "0")
    # Avoid real subprocess/spawn overhead & pickling friction in the sandbox.
    monkeypatch.setattr(s3.concurrent.futures, "ProcessPoolExecutor", concurrent.futures.ThreadPoolExecutor)

    parquet_root = tmp_path / "parquet_data"
    (parquet_root / "year=2026").mkdir(parents=True)
    _bars().to_parquet(parquet_root / "year=2026" / "01.parquet", index=False)

    strategies_root = tmp_path / "strategies" / "rsi_zone"
    strategies_root.mkdir(parents=True)
    (strategies_root / "a20.py").write_text(STRATEGY_SRC)

    args = s3.argparse.Namespace(months_limit=None, ban_file=None, jobs="1", entry_interval=0)
    s3.run(args)

    out_path = tmp_path / "positions" / "rsi_zone" / "a20" / "year=2026" / "01.parquet"
    assert out_path.exists()
    result = pd.read_parquet(out_path)
    assert (result["entry_flag"] == 1).all()
