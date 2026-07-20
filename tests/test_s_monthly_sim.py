from datetime import date

import numpy as np
import pandas as pd
import pytest

import core.s_monthly_sim as sim


def test_hm_parses_hhmm_and_iso():
    assert sim._hm("17:00") == 17 * 60
    assert sim._hm("2026-01-05T09:30:00Z") == 9 * 60 + 30
    assert sim._hm(None) is None


def test_trading_days_in_month_excludes_weekends():
    days = sim.trading_days_in_month(date(2026, 1, 1))
    assert all(d.weekday() < 5 for d in days)
    assert date(2026, 1, 3) not in days  # Saturday
    assert date(2026, 1, 5) in days  # Monday


def test_target_months_explicit_sim_month():
    assert sim._target_months("2026-03") == [date(2026, 3, 1)]


def test_target_months_default_returns_12_months_ending_last_month():
    months = sim._target_months("")
    assert len(months) == 12
    assert months == sorted(months)


def test_load_strategies_from_snapshot_filters_by_min_avg(tmp_path):
    rank_root = tmp_path / "rank"
    strategies_root = tmp_path / "strategies"
    snap_dir = rank_root / "snapshots" / "2026-05"
    snap_dir.mkdir(parents=True)

    (strategies_root / "rsi_zone").mkdir(parents=True)
    (strategies_root / "rsi_zone" / "good.py").write_text("# strat")
    (strategies_root / "rsi_zone" / "low.py").write_text("# strat")

    pd.DataFrame([
        {"id": "rsi_zone", "slug": "good", "pips_avg_per_entry": 0.5},
        {"id": "rsi_zone", "slug": "low", "pips_avg_per_entry": 0.1},
        {"id": "rsi_zone", "slug": "missing_file", "pips_avg_per_entry": 0.9},
    ]).to_csv(snap_dir / "rank_by_pips_avg.csv", index=False)

    files = sim._load_strategies_from_snapshot("2026-05", rank_root, strategies_root, min_avg=0.3)
    names = sorted(f.name for f in files)
    assert names == ["good.py"]


def test_load_strategies_from_snapshot_missing_snapshot_returns_empty(tmp_path, capsys):
    files = sim._load_strategies_from_snapshot("2026-05", tmp_path / "rank", tmp_path / "strategies")
    assert files == []
    assert "snapshot not found" in capsys.readouterr().out


def _row(t, o, h, l, c, entry_flag=0, side="", own=1):
    return {
        "time_utc": t, "open": o, "high": h, "low": l, "close": c,
        "entry_flag": entry_flag, "side": side, "is_own_session": own,
    }


def test_build_positions_records_tp_close():
    env = {"PIP_SIZE": "0.01", "RR_TP_PIPS": "10", "RR_SL_PIPS": "5", "SPREAD_PIPS": "0.0"}
    rows = [
        _row("2026-01-05T01:00", 100.0, 100.05, 99.95, 100.0, entry_flag=1, side="BUY"),
        _row("2026-01-05T01:05", 100.0, 100.05, 99.95, 100.0),
        _row("2026-01-05T01:10", 100.10, 100.15, 100.05, 100.12),
    ]
    out = sim._build_positions(rows, env)
    assert len(out) == 1
    assert out[0]["why"] == "TP"
    assert out[0]["pips_net"] == 10.0


def test_run_writes_daily_csv_for_snapshot_strategies(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))

    rank_root = tmp_path / "rank" / "all"
    strategies_root = tmp_path / "strategies"
    parquet_root = tmp_path / "parquet_data"

    snap_dir = rank_root / "snapshots" / "2026-01"
    snap_dir.mkdir(parents=True)
    (strategies_root / "rsi_zone").mkdir(parents=True)
    strat_src = (
        "import pandas as pd\n"
        "def apply_entry_flag(df, params):\n"
        "    df = df.copy()\n"
        "    df['entry_flag'] = 1\n"
        "    df['buy_sell'] = 'BUY'\n"
        "    return df\n"
    )
    (strategies_root / "rsi_zone" / "a20.py").write_text(strat_src)
    pd.DataFrame([{"id": "rsi_zone", "slug": "a20", "pips_avg_per_entry": 0.9}]).to_csv(
        snap_dir / "rank_by_pips_avg.csv", index=False
    )

    (parquet_root / "year=2026").mkdir(parents=True)
    times = pd.date_range("2026-02-02", periods=20, freq="5min", tz="UTC")  # Monday
    close = 100 + np.cumsum(np.random.RandomState(1).randn(20) * 0.01)
    df = pd.DataFrame({
        "time_utc": times, "open": close, "high": close + 0.02, "low": close - 0.02, "close": close,
    })
    df.to_parquet(parquet_root / "year=2026" / "02.parquet", index=False)

    args = sim.argparse.Namespace(
        pip_size=None, tp_pips=None, sl_pips=None, max_entries=None,
        abn_burst_pips=None, abn_forward_block_bars=None, spread_pips=None, month="2026-02",
    )
    sim.run(args)

    out_dir = tmp_path / "monthly" / "2026-02" / "ALL"
    csvs = list(out_dir.glob("*.csv"))
    assert len(csvs) >= 1
    result = pd.read_csv(csvs[0])
    assert set(result.columns) == {"tid", "slug", "entries", "pips_sum", "pips_avg"}
    assert result.iloc[0]["tid"] == "rsi_zone"


def test_run_write_failure_does_not_leave_partial_daily_csv(monkeypatch, tmp_path):
    """run()の日次CSV書き込みは.tmpへ書いてからos.replaceする（atomic write契約, conventions.md）
    ため、書き込み中に例外が起きても壊れた出力ファイルが残らない。"""
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))

    rank_root = tmp_path / "rank" / "all"
    strategies_root = tmp_path / "strategies"
    parquet_root = tmp_path / "parquet_data"

    snap_dir = rank_root / "snapshots" / "2026-01"
    snap_dir.mkdir(parents=True)
    (strategies_root / "rsi_zone").mkdir(parents=True)
    strat_src = (
        "import pandas as pd\n"
        "def apply_entry_flag(df, params):\n"
        "    df = df.copy()\n"
        "    df['entry_flag'] = 1\n"
        "    df['buy_sell'] = 'BUY'\n"
        "    return df\n"
    )
    (strategies_root / "rsi_zone" / "a20.py").write_text(strat_src)
    pd.DataFrame([{"id": "rsi_zone", "slug": "a20", "pips_avg_per_entry": 0.9}]).to_csv(
        snap_dir / "rank_by_pips_avg.csv", index=False
    )

    (parquet_root / "year=2026").mkdir(parents=True)
    times = pd.date_range("2026-02-02", periods=20, freq="5min", tz="UTC")  # Monday
    close = 100 + np.cumsum(np.random.RandomState(1).randn(20) * 0.01)
    df = pd.DataFrame({
        "time_utc": times, "open": close, "high": close + 0.02, "low": close - 0.02, "close": close,
    })
    df.to_parquet(parquet_root / "year=2026" / "02.parquet", index=False)

    monkeypatch.setattr(
        pd.DataFrame, "to_csv",
        lambda self, *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )

    args = sim.argparse.Namespace(
        pip_size=None, tp_pips=None, sl_pips=None, max_entries=None,
        abn_burst_pips=None, abn_forward_block_bars=None, spread_pips=None, month="2026-02",
    )
    with pytest.raises(OSError):
        sim.run(args)

    out_dir = tmp_path / "monthly" / "2026-02" / "ALL"
    assert not list(out_dir.glob("*.csv"))


def test_run_skips_month_without_snapshot(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    args = sim.argparse.Namespace(
        pip_size=None, tp_pips=None, sl_pips=None, max_entries=None,
        abn_burst_pips=None, abn_forward_block_bars=None, spread_pips=None, month="2026-02",
    )
    sim.run(args)
    assert "no snapshot for 2026-01" in capsys.readouterr().out
