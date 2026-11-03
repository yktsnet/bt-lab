from datetime import date

import numpy as np
import pandas as pd
import pytest

import core.s_monthly_sim as sim


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


def test_run_writes_daily_csv_for_snapshot_strategies(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))

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
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))

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
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    args = sim.argparse.Namespace(
        pip_size=None, tp_pips=None, sl_pips=None, max_entries=None,
        abn_burst_pips=None, abn_forward_block_bars=None, spread_pips=None, month="2026-02",
    )
    sim.run(args)
    assert "no snapshot for 2026-01" in capsys.readouterr().out


# 月次シムと S3 → S5 → S6 の突き合わせ -------------------------------------------

PARITY_STRATEGY = (
    "import numpy as np\n"
    "def apply_entry_flag(df, params):\n"
    "    df = df.copy()\n"
    "    # 'feat' は S1c が焼き込んだ列を想定（compute_all では作れない）\n"
    "    df['entry_flag'] = (df['feat'] > 0).astype(int)\n"
    "    k = np.arange(len(df)) % 7\n"
    "    df['buy_sell'] = np.where(k < 3, 'BUY', np.where(k < 5, 'SELL', ''))\n"
    "    return df\n"
)


def _setup_sim_month(tmp_path, strategy_src):
    rank_root = tmp_path / "rank" / "all"
    snap_dir = rank_root / "snapshots" / "2026-01"
    snap_dir.mkdir(parents=True)
    sdir = tmp_path / "strategies" / "rsi_zone"
    sdir.mkdir(parents=True)
    (sdir / "a20.py").write_text(strategy_src)
    pd.DataFrame([{"id": "rsi_zone", "slug": "a20", "pips_avg_per_entry": 0.9}]).to_csv(
        snap_dir / "rank_by_pips_avg.csv", index=False
    )

    # 平日5日分の M5。17:00 を越えるバーも含め、日をまたぐ状態も通す
    times = pd.date_range("2026-02-02", "2026-02-06 23:55", freq="5min", tz="UTC")
    rng = np.random.RandomState(7)
    close = 100 + np.cumsum(rng.randn(len(times)) * 0.04)
    df = pd.DataFrame({
        "time_utc": times,
        "open": close + rng.randn(len(times)) * 0.01,
        "high": close + 0.05,
        "low": close - 0.05,
        "close": close,
        "feat": rng.randn(len(times)),
    })
    pq_dir = tmp_path / "parquet_data" / "year=2026"
    pq_dir.mkdir(parents=True)
    df.to_parquet(pq_dir / "02.parquet", index=False)
    return sdir / "a20.py", pq_dir / "02.parquet"


def _sim_args(**kw):
    base = dict(
        pip_size=None, tp_pips=None, sl_pips=None, max_entries=None,
        abn_burst_pips=None, abn_forward_block_bars=None, spread_pips=None, month="2026-02",
    )
    base.update(kw)
    return sim.argparse.Namespace(**base)


def test_run_matches_s3_s5_s6_entries_and_pips_per_day(monkeypatch, tmp_path):
    import core.s3_calc_positions as s3
    import core.s5_position_engine as s5
    import core.s6_position_pips as s6

    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    monkeypatch.delenv("ENTRY_INTERVAL_MIN", raising=False)
    strategy_path, pq_path = _setup_sim_month(tmp_path, PARITY_STRATEGY)

    sim.run(_sim_args(tp_pips="8", sl_pips="5"))

    # 同じ戦略・月・引数を S3（既定の30分間隔）→ S5 → S6 に通す
    pos = tmp_path / "positions" / "rsi_zone" / "a20" / "year=2026" / "02.parquet"
    assert s3._process_strategy_month(strategy_path, pq_path, pos, entry_interval_min=30) is True
    env = {"RR_TP_PIPS": "8", "RR_SL_PIPS": "5"}
    assert s5._process_one(
        "rsi_zone", "a20", 2026, 2, tmp_path / "parquet_data", tmp_path / "positions",
        tmp_path / "pos_events", env,
    ) == "wrote"
    ev_path = tmp_path / "pos_events" / "rsi_zone" / "a20" / "year=2026" / "02.parquet"
    assert s6._process_one(ev_path, env) == "wrote"

    ev = pd.read_parquet(ev_path)
    closes = ev[ev["type"] == "close"].copy()
    closes["day"] = pd.to_datetime(closes["time_utc"], utc=True).dt.strftime("%Y-%m-%d")
    expected = closes.groupby("day")["pips_net"].agg(["count", "sum"])
    assert expected["count"].sum() > 5  # 突き合わせる中身がある
    assert {"TP", "SL"} <= set(closes["abnormal"])  # TP・SL で閉じた行も含めて合わせる

    out_dir = tmp_path / "monthly" / "2026-02" / "ALL"
    for day, row in expected.iterrows():
        got = pd.read_csv(out_dir / f"{day}.csv").iloc[0]
        assert got["entries"] == row["count"], day
        assert got["pips_sum"] == pytest.approx(row["sum"], abs=0.011), day


def test_run_does_not_open_positions_on_bars_without_side(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    monkeypatch.delenv("ENTRY_INTERVAL_MIN", raising=False)
    src = (
        "def apply_entry_flag(df, params):\n"
        "    df = df.copy()\n"
        "    df['entry_flag'] = 1\n"
        "    df['buy_sell'] = ''\n"
        "    return df\n"
    )
    _setup_sim_month(tmp_path, src)

    sim.run(_sim_args())

    out_dir = tmp_path / "monthly" / "2026-02" / "ALL"
    csvs = list(out_dir.glob("*.csv"))
    assert csvs
    for c in csvs:
        assert (pd.read_csv(c)["entries"] == 0).all()
