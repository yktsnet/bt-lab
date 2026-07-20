import pandas as pd
import pytest

import core.s8_strategy_rank as s8


def test_dd_metrics_hand_calculated():
    # cumulative: 10, 5, 25, -5, 10  -> peak sequence: 10,10,25,25,25
    # drawdown from peak: 0,5,0,30,15 -> abs_dd = 30
    pips = pd.Series([10, -5, 20, -30, 15])
    m = s8._dd_metrics(pips)
    assert m["abs_dd"] == 30.0
    total = 10.0
    assert m["recovery_factor"] == round(total / 30.0, 2)
    profit_months = [10, 20, 15]
    avg_profit = sum(profit_months) / len(profit_months)
    assert m["recovery_months"] == round(30.0 / avg_profit, 1)


def test_dd_metrics_no_drawdown_gives_infinite_recovery_factor():
    pips = pd.Series([1.0, 2.0, 3.0])
    m = s8._dd_metrics(pips)
    assert m["abs_dd"] == 0.0
    assert m["recovery_factor"] == float("inf")


def test_dd_metrics_no_profit_months_gives_infinite_recovery_months():
    pips = pd.Series([-1.0, -2.0])
    m = s8._dd_metrics(pips)
    assert m["recovery_months"] == float("inf")


def _write_monthly_csv(root, year, rows):
    d = root / "all" / str(year)
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(d / "monthly_all.csv", index=False)


def test_run_no_summary_dir_prints_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    args = s8.argparse.Namespace(rank_months=None, rf_min=None, recovery_months_max=None, min_sig_per_hour=None, as_of=None)
    s8.run(args)
    assert "Run s7 first" in capsys.readouterr().out


def test_run_ranks_and_filters_by_recovery_factor(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))

    summary_root = tmp_path / "summary"
    rows = []
    # good: steady small gains each month, no big DD -> passes RF filter
    for m in range(1, 7):
        rows.append({
            "year": 2026, "month": m, "session": "all", "id": "rsi_zone", "slug": "good",
            "entries_total": 20, "bars5m_total": 1000, "entry_rate": 0.02,
            "pips_sum_total": 10.0, "pips_avg_per_entry": 0.5,
        })
    # bad: one huge drawdown month -> fails RF filter
    for m, pips in zip(range(1, 7), [5, 5, 5, -100, 5, 5]):
        rows.append({
            "year": 2026, "month": m, "session": "all", "id": "rsi_zone", "slug": "bad",
            "entries_total": 20, "bars5m_total": 1000, "entry_rate": 0.02,
            "pips_sum_total": pips, "pips_avg_per_entry": pips / 20,
        })
    _write_monthly_csv(summary_root, 2026, rows)

    # rank_months=999 so the "recent" window always covers 2026 regardless of real wall-clock date.
    args = s8.argparse.Namespace(rank_months=999, rf_min=2.0, recovery_months_max=6.0, min_sig_per_hour=0.0, as_of=None)
    s8.run(args)

    rank_root = tmp_path / "rank" / "all"
    rank_avg = pd.read_csv(rank_root / "rank_by_pips_avg.csv")
    dd_filtered = pd.read_csv(rank_root / "dd_filtered.csv")

    assert list(rank_avg["slug"]) == ["good"]
    assert "bad" in set(dd_filtered["slug"])


def test_run_min_sig_per_hour_excludes_low_frequency_strategies(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))

    summary_root = tmp_path / "summary"
    rows = [{
        "year": 2026, "month": m, "session": "all", "id": "rsi_zone", "slug": "rare",
        "entries_total": 1, "bars5m_total": 100000, "entry_rate": 0.00001,
        "pips_sum_total": 5.0, "pips_avg_per_entry": 5.0,
    } for m in range(1, 7)]
    _write_monthly_csv(summary_root, 2026, rows)

    args = s8.argparse.Namespace(rank_months=999, rf_min=0.0, recovery_months_max=999.0, min_sig_per_hour=0.5, as_of=None)
    s8.run(args)

    rank_avg = pd.read_csv(tmp_path / "rank" / "all" / "rank_by_pips_avg.csv")
    assert rank_avg.empty


def test_run_as_of_writes_snapshot_not_latest_rank(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    summary_root = tmp_path / "summary"
    rows = [{
        "year": 2025, "month": m, "session": "all", "id": "rsi_zone", "slug": "a",
        "entries_total": 5, "bars5m_total": 1000, "entry_rate": 0.005,
        "pips_sum_total": 3.0, "pips_avg_per_entry": 0.6,
    } for m in range(1, 13)]
    _write_monthly_csv(summary_root, 2025, rows)

    args = s8.argparse.Namespace(rank_months=12, rf_min=0.0, recovery_months_max=999.0, min_sig_per_hour=0.0, as_of="2025-12")
    s8.run(args)

    rank_root = tmp_path / "rank" / "all"
    assert not (rank_root / "rank_by_pips_avg.csv").exists()  # as-of runs do not touch latest rank
    snap = rank_root / "snapshots" / "2025-12" / "rank_by_pips_avg.csv"
    assert snap.exists()
