import numpy as np
import pandas as pd
import pytest

import core.s1_enrich_parquet as s1c


def _bars(n=40, start="2026-01-05"):
    times = pd.date_range(start, periods=n, freq="5min", tz="UTC")
    close = 100 + np.cumsum(np.random.RandomState(0).randn(n) * 0.1)
    return pd.DataFrame({
        "time_utc": times,
        "open": close,
        "high": close + 0.05,
        "low": close - 0.05,
        "close": close,
    })


def _write(path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_load_parquet_skips_files_missing_close_column(tmp_path, capsys):
    path = tmp_path / "no_close.parquet"
    pd.DataFrame({"open": [1.0, 2.0]}).to_parquet(path, index=False)
    result = s1c._load_parquet(path)
    assert result is None
    assert "missing close column" in capsys.readouterr().out


def test_enrich_file_adds_missing_feature_columns(tmp_path):
    path = tmp_path / "01.parquet"
    _write(path, _bars())
    added = s1c._enrich_file(path)
    assert added > 0

    out = pd.read_parquet(path)
    assert "rsi14" in out.columns
    assert "ema9" in out.columns
    assert "pivot_p" in out.columns  # time_utc present -> daily features included


def test_enrich_file_is_idempotent(tmp_path):
    path = tmp_path / "01.parquet"
    _write(path, _bars())
    s1c._enrich_file(path)
    added_second = s1c._enrich_file(path)
    assert added_second == 0


def test_enrich_file_write_failure_leaves_original_file_untouched(monkeypatch, tmp_path):
    """_enrich_fileは.tmpへ書いてからos.replaceする（atomic write契約, conventions.md）ため、
    書き込み中に例外が起きても元のファイルは壊れた状態で残らない。"""
    path = tmp_path / "01.parquet"
    _write(path, _bars())
    original_bytes = path.read_bytes()

    monkeypatch.setattr(
        pd.DataFrame, "to_parquet",
        lambda self, *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError):
        s1c._enrich_file(path)

    assert path.read_bytes() == original_bytes


def test_enrich_file_converts_int_ms_time_utc(tmp_path):
    path = tmp_path / "01.parquet"
    df = _bars()
    df["time_utc"] = (df["time_utc"].astype("int64") // 1_000_000)
    _write(path, df)
    added = s1c._enrich_file(path)
    assert added > 0
    out = pd.read_parquet(path)
    assert "pivot_p" in out.columns


def test_main_year_filter_processes_only_matching_year(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    parquet_root = tmp_path / "parquet_data"
    _write(parquet_root / "year=2024" / "01.parquet", _bars())
    _write(parquet_root / "year=2025" / "01.parquet", _bars())

    args = s1c.argparse.Namespace(year="2025")
    s1c.main(args)

    out = capsys.readouterr().out
    assert "files=1" in out


def test_main_default_processes_all_years(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    parquet_root = tmp_path / "parquet_data"
    _write(parquet_root / "year=2024" / "01.parquet", _bars())
    _write(parquet_root / "year=2025" / "01.parquet", _bars())

    args = s1c.argparse.Namespace(year=None)
    s1c.main(args)

    out = capsys.readouterr().out
    assert "files=2" in out


def _use_registry(monkeypatch, tmp_path, names):
    import yaml

    import_root = tmp_path / "import"
    import_root.mkdir()
    (import_root / "feature_registry.yaml").write_text(yaml.safe_dump({"precompute": names}))
    monkeypatch.setattr(s1c, "get_import_root", lambda: import_root)


def test_enrich_file_adds_only_columns_listed_in_registry(monkeypatch, tmp_path):
    _use_registry(monkeypatch, tmp_path, ["rsi14", "ema9"])
    path = tmp_path / "01.parquet"
    _write(path, _bars())

    assert s1c._enrich_file(path) == 2

    out = pd.read_parquet(path)
    assert {"rsi14", "ema9"} <= set(out.columns)
    assert "ema12" not in out.columns
    assert "pivot_p" not in out.columns


def test_enrich_file_fails_naming_registry_columns_compute_all_lacks(monkeypatch, tmp_path):
    _use_registry(monkeypatch, tmp_path, ["rsi14", "no_such_feature", "another_missing"])
    path = tmp_path / "01.parquet"
    _write(path, _bars())
    original = path.read_bytes()

    with pytest.raises(s1c.RegistryMismatch) as exc:
        s1c._enrich_file(path)

    assert "no_such_feature" in str(exc.value)
    assert "another_missing" in str(exc.value)
    assert path.read_bytes() == original


def test_main_exits_nonzero_when_registry_has_unknown_column(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    _use_registry(monkeypatch, tmp_path, ["rsi14", "no_such_feature"])
    _write(tmp_path / "parquet_data" / "year=2025" / "01.parquet", _bars())

    with pytest.raises(SystemExit) as exc:
        s1c.main(s1c.argparse.Namespace(year=None))

    assert exc.value.code != 0
    assert "no_such_feature" in capsys.readouterr().err


def test_real_registry_columns_are_all_computed_by_compute_all():
    from lib.features import compute_all

    df = _bars(n=300)
    missing = [c for c in s1c.registry_columns() if c not in compute_all(df)]
    assert missing == []
