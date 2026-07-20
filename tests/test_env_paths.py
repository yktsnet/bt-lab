from pathlib import Path

import lib.env_paths as env_paths


def test_default_data_root_is_under_home(monkeypatch):
    monkeypatch.delenv("BACKTEST_DATA_ROOT", raising=False)
    assert env_paths.get_backtest_data_root() == Path.home() / "bt_data" / "backtest"


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    assert env_paths.get_backtest_data_root() == tmp_path


def test_env_whitespace_only_falls_back_to_default(monkeypatch):
    """BACKTEST_DATA_ROOTが空白のみの場合、既定値(~/bt_data/backtest)扱いになること。"""
    monkeypatch.setenv("BACKTEST_DATA_ROOT", "   ")
    assert env_paths.get_backtest_data_root() == Path.home() / "bt_data" / "backtest"


def test_derived_paths_compose_under_data_root(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    assert env_paths.get_bt_data_root() == tmp_path / "bt_data"
    assert env_paths.get_parquet_root() == tmp_path / "parquet_data"
    assert env_paths.get_strategies_root() == tmp_path / "strategies"
    assert env_paths.get_logs_root() == tmp_path / "logs"


def test_import_root_is_repo_import_dir():
    app_root = Path(__file__).resolve().parents[1]
    assert env_paths.get_import_root() == app_root / "import"


def test_ensure_dirs_creates_all(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    env_paths.ensure_dirs()
    for sub in ["", "bt_data", "parquet_data", "strategies", "logs"]:
        assert (tmp_path / sub).is_dir()
