import pandas as pd
import pytest
import yaml

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
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    args = s8.argparse.Namespace(rank_months=None, rf_min=None, recovery_months_max=None, min_sig_per_hour=None, as_of=None)
    s8.run(args)
    assert "Run s7 first" in capsys.readouterr().out


def test_run_ranks_and_filters_by_recovery_factor(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))

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
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))

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
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
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


def _good_rows(slug, year=2025):
    return [{
        "year": year, "month": m, "session": "all", "id": "rsi_zone", "slug": slug,
        "entries_total": 20, "bars5m_total": 1000, "entry_rate": 0.02,
        "pips_sum_total": 10.0, "pips_avg_per_entry": 0.5,
    } for m in range(1, 13)]


def _s8_args(as_of=None):
    return s8.argparse.Namespace(
        rank_months=999, rf_min=0.0, recovery_months_max=999.0, min_sig_per_hour=0.0, as_of=as_of
    )


def _write_ban(path, slugs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump({"entries": [{"id": "rsi_zone", "slug": s} for s in slugs]}))


def test_run_without_as_of_excludes_latest_ban_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    monkeypatch.delenv("S8_AS_OF", raising=False)
    _write_monthly_csv(tmp_path / "summary", 2025, _good_rows("keep") + _good_rows("drop"))
    _write_ban(tmp_path / "ban" / "entry_ban_all_20250101_0000.yaml", ["keep"])  # 古い方は無視される
    _write_ban(tmp_path / "ban" / "entry_ban_all_20260101_0000.yaml", ["drop"])
    _write_ban(tmp_path / "ban" / "asof" / "2025-12" / "entry_ban_all.yaml", ["keep"])  # asof/ は拾わない

    s8.run(_s8_args())

    rank_avg = pd.read_csv(tmp_path / "rank" / "all" / "rank_by_pips_avg.csv")
    assert list(rank_avg["slug"]) == ["keep"]
    assert "ban excluded=1" in capsys.readouterr().out


def test_run_as_of_reads_only_that_months_ban_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    _write_monthly_csv(tmp_path / "summary", 2025, _good_rows("a") + _good_rows("b"))
    _write_ban(tmp_path / "ban" / "asof" / "2025-12" / "entry_ban_all.yaml", ["a"])
    _write_ban(tmp_path / "ban" / "asof" / "2025-11" / "entry_ban_all.yaml", ["b"])
    _write_ban(tmp_path / "ban" / "entry_ban_all_20260101_0000.yaml", ["b"])

    s8.run(_s8_args(as_of="2025-12"))

    snap = pd.read_csv(tmp_path / "rank" / "all" / "snapshots" / "2025-12" / "rank_by_pips_avg.csv")
    assert list(snap["slug"]) == ["b"]
    assert "ban excluded=1" in capsys.readouterr().out


def test_run_without_ban_file_excludes_nobody_and_says_so(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    _write_monthly_csv(tmp_path / "summary", 2025, _good_rows("a") + _good_rows("b"))
    # as-of 月の Ban ファイルが無ければ、最新の Ban があっても使わない
    _write_ban(tmp_path / "ban" / "entry_ban_all_20260101_0000.yaml", ["a"])

    s8.run(_s8_args(as_of="2025-12"))

    snap = pd.read_csv(tmp_path / "rank" / "all" / "snapshots" / "2025-12" / "rank_by_pips_avg.csv")
    assert sorted(snap["slug"]) == ["a", "b"]
    assert "no ban file found" in capsys.readouterr().out


def test_run_all_candidates_banned_yields_empty_rank(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    monkeypatch.delenv("S8_AS_OF", raising=False)
    _write_monthly_csv(tmp_path / "summary", 2025, _good_rows("a"))
    _write_ban(tmp_path / "ban" / "entry_ban_all_20260101_0000.yaml", ["a"])

    s8.run(_s8_args())

    assert pd.read_csv(tmp_path / "rank" / "all" / "rank_by_pips_avg.csv").empty


def _sq_rows(slug, monthly_samples, year=2025):
    """月ごとの pips_net 標本から、s7 が書く月次行を作る。"""
    rows = []
    for m, samples in enumerate(monthly_samples, start=1):
        rows.append({
            "year": year, "month": m, "session": "all", "id": "rsi_zone", "slug": slug,
            "entries_total": len(samples), "bars5m_total": 1000,
            "entry_rate": len(samples) / 1000,
            "pips_sum_total": float(sum(samples)),
            "pips_avg_per_entry": sum(samples) / len(samples),
            "pips_sq_sum_total": float(sum(x * x for x in samples)),
        })
    return rows


def _tstat_summary_rows():
    return (
        _sq_rows("many", [[1, 2], [3, 4]])  # n=4 mean=2.5 sd=sqrt(5/3)
        + _sq_rows("lucky", [[9], [0]])  # n=2 mean=4.5 sd=sqrt(40.5) 偶然の1発
        + _sq_rows("single", [[5]])  # n=1 → NaN
        + _sq_rows("flat", [[2, 2], [2]])  # sd=0 → NaN
    )


def test_pips_tstat_hand_calculated():
    n = pd.Series([4.0])
    t = s8._pips_tstat(n, pd.Series([10.0]), pd.Series([30.0]))
    expected = 2.5 / (((30.0 - 10.0**2 / 4) / 3) ** 0.5 / 4**0.5)
    assert t.iloc[0] == pytest.approx(expected)
    assert expected == pytest.approx(3.8730, abs=1e-4)


def test_pips_tstat_is_nan_for_single_entry_or_zero_deviation():
    t = s8._pips_tstat(
        pd.Series([1.0, 3.0]), pd.Series([5.0, 6.0]), pd.Series([25.0, 12.0])
    )
    assert t.isna().all()


def test_pips_tstat_keeps_small_but_nonzero_deviation_and_nans_float_noise():
    # 100, 100.001, 100.002: 分散は 1e-6。平均 100.001、SE = 0.001/sqrt(3)
    t = s8._pips_tstat(
        pd.Series([3.0]),
        pd.Series([300.003]),
        pd.Series([100.0**2 + 100.001**2 + 100.002**2]),
    )
    assert t.iloc[0] == pytest.approx(100.001 / (0.001 / 3**0.5), rel=1e-3)
    # 0.1 を3回: 2乗和・合計が浮動小数点で割り切れず、分散が 1e-18 程度の正になる
    noise = s8._pips_tstat(
        pd.Series([3.0]), pd.Series([0.1 + 0.1 + 0.1]), pd.Series([0.1**2 * 3])
    )
    assert noise.isna().all()


def test_run_writes_rank_by_tstat_sorted_desc_with_nan_last(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    monkeypatch.delenv("S8_AS_OF", raising=False)
    _write_monthly_csv(tmp_path / "summary", 2025, _tstat_summary_rows())

    s8.run(_s8_args())

    rank_root = tmp_path / "rank" / "all"
    tstat = pd.read_csv(rank_root / "rank_by_tstat.csv")
    avg = pd.read_csv(rank_root / "rank_by_pips_avg.csv")

    assert list(tstat["slug"][:2]) == ["many", "lucky"]
    assert tstat.loc[tstat["slug"] == "many", "pips_tstat"].iloc[0] == pytest.approx(3.8730, abs=1e-4)
    assert tstat.loc[tstat["slug"] == "lucky", "pips_tstat"].iloc[0] == pytest.approx(
        4.5 / ((40.5**0.5) / 2**0.5), abs=1e-4
    )
    assert set(tstat["slug"][2:]) == {"single", "flat"}
    assert tstat["pips_tstat"][2:].isna().all()
    assert tstat["pips_tstat"][:2].notna().all()

    # 対象集合は rank_by_pips_avg.csv と同じで、列は pips_tstat が増えるだけ
    assert set(tstat["slug"]) == set(avg["slug"])
    assert list(tstat.columns) == list(avg.columns) + ["pips_tstat"]
    # 既存の順位は t値の影響を受けない
    assert avg["pips_avg_per_entry"].is_monotonic_decreasing
    assert "pips_sq_sum_total" not in avg.columns


def test_run_tstat_uses_same_candidate_set_after_filters(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    monkeypatch.delenv("S8_AS_OF", raising=False)
    rows = _tstat_summary_rows() + _sq_rows("loser", [[-5, -5], [-5, -5]])
    _write_monthly_csv(tmp_path / "summary", 2025, rows)
    _write_ban(tmp_path / "ban" / "entry_ban_all_20260101_0000.yaml", ["lucky"])

    s8.run(_s8_args())

    rank_root = tmp_path / "rank" / "all"
    tstat = pd.read_csv(rank_root / "rank_by_tstat.csv")
    avg = pd.read_csv(rank_root / "rank_by_pips_avg.csv")
    assert "loser" not in set(tstat["slug"])
    assert "lucky" not in set(tstat["slug"])
    assert set(tstat["slug"]) == set(avg["slug"]) == {"many", "single", "flat"}


def test_run_as_of_writes_tstat_snapshot_and_keeps_existing_one(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    _write_monthly_csv(tmp_path / "summary", 2025, _tstat_summary_rows())

    s8.run(_s8_args(as_of="2025-12"))

    rank_root = tmp_path / "rank" / "all"
    assert not (rank_root / "rank_by_tstat.csv").exists()  # as-of は最新ランクを触らない
    snap_dir = rank_root / "snapshots" / "2025-12"
    assert (snap_dir / "rank_by_pips_avg.csv").exists()
    tstat_snap = snap_dir / "rank_by_tstat.csv"
    assert list(pd.read_csv(tstat_snap)["slug"][:2]) == ["many", "lucky"]

    tstat_snap.write_text("sentinel\n")
    s8.run(_s8_args(as_of="2025-12"))
    assert tstat_snap.read_text() == "sentinel\n"


def test_run_without_pips_sq_sum_total_skips_tstat_but_writes_other_outputs(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    monkeypatch.delenv("S8_AS_OF", raising=False)
    _write_monthly_csv(tmp_path / "summary", 2025, _good_rows("a"))

    s8.run(_s8_args())

    rank_root = tmp_path / "rank" / "all"
    assert not (rank_root / "rank_by_tstat.csv").exists()
    assert list(pd.read_csv(rank_root / "rank_by_pips_avg.csv")["slug"]) == ["a"]
    assert (rank_root / "rank_by_pips_sum.csv").exists()
    assert (rank_root / "dd_filtered.csv").exists()
    assert "pips_sq_sum_total" in capsys.readouterr().out


def test_run_without_pips_sq_sum_total_skips_tstat_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    _write_monthly_csv(tmp_path / "summary", 2025, _good_rows("a"))

    s8.run(_s8_args(as_of="2025-12"))

    snap_dir = tmp_path / "rank" / "all" / "snapshots" / "2025-12"
    assert (snap_dir / "rank_by_pips_avg.csv").exists()
    assert not (snap_dir / "rank_by_tstat.csv").exists()


def test_run_min_sig_per_hour_applies_to_tstat_rank_too(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    monkeypatch.delenv("S8_AS_OF", raising=False)
    # 同じ標本で bars だけ違う: often は signals/hour が 0.5 以上、rare は未満
    often = _sq_rows("often", [[1, 2], [3, 4]])
    rare = _sq_rows("rare", [[1, 2], [3, 4]])
    for r in often:
        r["bars5m_total"] = 10
    for r in rare:
        r["bars5m_total"] = 1_000_000
    _write_monthly_csv(tmp_path / "summary", 2025, often + rare)
    args = s8.argparse.Namespace(
        rank_months=999, rf_min=0.0, recovery_months_max=999.0, min_sig_per_hour=0.5, as_of=None
    )

    s8.run(args)

    rank_root = tmp_path / "rank" / "all"
    tstat = pd.read_csv(rank_root / "rank_by_tstat.csv")
    avg = pd.read_csv(rank_root / "rank_by_pips_avg.csv")
    assert list(tstat["slug"]) == list(avg["slug"]) == ["often"]
