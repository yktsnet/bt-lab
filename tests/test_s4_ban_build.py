from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import core.s4_ban_build as s4


def test_jaccard_both_empty_is_1():
    assert s4._jaccard(set(), set()) == 1.0


def test_jaccard_one_empty_is_0():
    assert s4._jaccard({1, 2}, set()) == 0.0


def test_jaccard_partial_overlap():
    assert s4._jaccard({1, 2, 3}, {2, 3, 4}) == 2 / 4


def test_jaccard_dedup_removes_near_duplicate_later_key():
    ts = {
        "a": {1, 2, 3, 4},
        "b": {1, 2, 3, 5},  # jaccard=3/5=0.6 with a
        "c": {10, 11},       # unrelated
    }
    survivors, removed = s4._jaccard_dedup(ts, thr=0.5)
    assert survivors == ["a", "c"]
    assert removed == ["b"]


def test_jaccard_dedup_below_threshold_keeps_all():
    ts = {"a": {1, 2}, "b": {3, 4}}
    survivors, removed = s4._jaccard_dedup(ts, thr=0.5)
    assert survivors == ["a", "b"]
    assert removed == []


def test_parse_year_month():
    assert s4._parse_year_month(Path("root/year=2026/03.parquet")) == (2026, 3)


def test_bars_in_window_counts_hours_in_range(tmp_path):
    times = pd.to_datetime([
        "2026-01-05T05:00:00Z", "2026-01-05T16:00:00Z", "2026-01-05T18:00:00Z",
    ])
    path = tmp_path / "01.parquet"
    pd.DataFrame({"time_utc": times}).to_parquet(path, index=False)
    assert s4._bars_in_window(path) == 2  # 05:00 and 16:00 fall within [0,17)


def test_bars_in_window_missing_file_returns_zero(tmp_path):
    assert s4._bars_in_window(tmp_path / "nope.parquet") == 0


def _write_positions(root, tid, slug, year, month, entry_times):
    d = root / tid / slug / f"year={year}"
    d.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "time_utc": pd.to_datetime(entry_times),
        "entry_flag": [1] * len(entry_times),
    })
    df.to_parquet(d / f"{month:02d}.parquet", index=False)


def test_run_bans_low_rate_strategy_and_keeps_normal_one(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))

    parquet_root = tmp_path / "parquet_data" / "year=2026"
    parquet_root.mkdir(parents=True)
    # 100 bars within the 00:00-17:00 window
    times = pd.date_range("2026-01-05", periods=100, freq="5min", tz="UTC")
    pd.DataFrame({"time_utc": times}).to_parquet(parquet_root / "01.parquet", index=False)

    positions_root = tmp_path / "positions"
    # low_rate: only 1 entry out of many bars -> rate below min_rate
    _write_positions(positions_root, "rsi_zone", "low", 2026, 1, ["2026-01-05T01:00:00Z"])
    # ok: 30 entries -> healthy rate
    ok_times = pd.date_range("2026-01-05", periods=30, freq="10min", tz="UTC")
    _write_positions(positions_root, "rsi_zone", "ok", 2026, 1, ok_times)

    s4.run(months=1, min_rate=0.05, max_rate=0.9, jaccard_thr=0.99, dry_run=False)

    out = capsys.readouterr().out
    assert "rate_ban=1" in out

    ban_dir = tmp_path / "ban"
    ban_files = list(ban_dir.glob("entry_ban_all_*.yaml"))
    assert len(ban_files) == 1
    doc = yaml.safe_load(ban_files[0].read_text())
    reasons = {e["slug"]: e["reason"] for e in doc["entries"]}
    assert reasons.get("low") == "low_rate"
    assert "ok" not in reasons


def test_run_dry_run_does_not_write_ban_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    parquet_root = tmp_path / "parquet_data" / "year=2026"
    parquet_root.mkdir(parents=True)
    times = pd.date_range("2026-01-05", periods=50, freq="5min", tz="UTC")
    pd.DataFrame({"time_utc": times}).to_parquet(parquet_root / "01.parquet", index=False)

    positions_root = tmp_path / "positions"
    ok_times = pd.date_range("2026-01-05", periods=20, freq="10min", tz="UTC")
    _write_positions(positions_root, "rsi_zone", "ok", 2026, 1, ok_times)

    s4.run(months=1, min_rate=0.01, max_rate=0.9, jaccard_thr=0.99, dry_run=True)

    assert not (tmp_path / "ban").exists()


def test_run_no_parquet_files_prints_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    s4.run(months=1, min_rate=0.01, max_rate=0.9, jaccard_thr=0.99, dry_run=False)
    assert "no parquet files found" in capsys.readouterr().out


def test_run_no_positions_dir_prints_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    parquet_root = tmp_path / "parquet_data" / "year=2026"
    parquet_root.mkdir(parents=True)
    times = pd.date_range("2026-01-05", periods=10, freq="5min", tz="UTC")
    pd.DataFrame({"time_utc": times}).to_parquet(parquet_root / "01.parquet", index=False)

    s4.run(months=1, min_rate=0.01, max_rate=0.9, jaccard_thr=0.99, dry_run=False)
    assert "positions/ not found" in capsys.readouterr().out
