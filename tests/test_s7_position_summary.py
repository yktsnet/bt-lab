import math

import pandas as pd

import core.s7_position_summary as s7


def test_r2_rounds_to_two_decimals():
    assert s7._r2(1.23456) == 1.23


def test_r2_none_passthrough():
    assert s7._r2(None) is None


def test_r2_nan_and_inf_become_none():
    assert s7._r2(float("nan")) is None
    assert s7._r2(float("inf")) is None


def test_quarter_mapping():
    assert s7._quarter(1) == 1
    assert s7._quarter(3) == 1
    assert s7._quarter(4) == 2
    assert s7._quarter(12) == 4


def test_bars_in_window_counts_hours_before_eod(tmp_path):
    times = pd.to_datetime([
        "2026-01-05T05:00:00Z", "2026-01-05T16:59:00Z", "2026-01-05T18:00:00Z",
    ])
    path = tmp_path / "01.parquet"
    pd.DataFrame({"time_utc": times}).to_parquet(path, index=False)
    assert s7._bars_in_window(path) == 2


def test_run_no_pos_events_prints_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    s7.run()
    assert "pos_events/ not found" in capsys.readouterr().out


def _write_events(root, tid, slug, year, month, records):
    d = root / tid / slug / f"year={year}"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_parquet(d / f"{month:02d}.parquet", index=False)


def test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))

    parquet_root = tmp_path / "parquet_data" / "year=2026"
    parquet_root.mkdir(parents=True)
    times = pd.date_range("2026-01-05", periods=100, freq="5min", tz="UTC")  # all before 17:00 boundary mostly
    pd.DataFrame({"time_utc": times}).to_parquet(parquet_root / "01.parquet", index=False)

    events_root = tmp_path / "pos_events"
    _write_events(events_root, "rsi_zone", "a20", 2026, 1, [
        {"type": "open", "pips_net": None},
        {"type": "close", "pips_net": 10.0},
        {"type": "close", "pips_net": -4.0},
    ])

    s7.run()

    out_dir = tmp_path / "summary" / "all" / "2026"
    monthly = pd.read_csv(out_dir / "monthly_all.csv")
    assert len(monthly) == 1
    row = monthly.iloc[0]
    assert row["entries_total"] == 2
    assert row["pips_sum_total"] == 6.0
    assert row["pips_avg_per_entry"] == 3.0
    bars = s7._bars_in_window(parquet_root / "01.parquet")
    assert row["bars5m_total"] == bars
    assert row["entry_rate"] == round(2 / bars, 2)

    quarterly = pd.read_csv(out_dir / "quarterly_all.csv")
    assert len(quarterly) == 1
    assert quarterly.iloc[0]["entries_total"] == 2

    yearly = pd.read_csv(out_dir / "yearly_all.csv")
    assert len(yearly) == 1
    assert yearly.iloc[0]["pips_sum_total"] == 6.0


def test_run_skips_files_without_type_column_or_empty_close(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    parquet_root = tmp_path / "parquet_data" / "year=2026"
    parquet_root.mkdir(parents=True)
    times = pd.date_range("2026-01-05", periods=10, freq="5min", tz="UTC")
    pd.DataFrame({"time_utc": times}).to_parquet(parquet_root / "01.parquet", index=False)

    events_root = tmp_path / "pos_events"
    _write_events(events_root, "rsi_zone", "noclose", 2026, 1, [{"open": [1]}])
    _write_events(events_root, "rsi_zone", "onlyopen", 2026, 1, [{"type": "open", "pips_net": None}])

    s7.run()
    assert "no records found" in capsys.readouterr().out
