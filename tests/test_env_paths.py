from pathlib import Path

import lib.env_paths as env_paths


def test_default_data_root_is_under_home(monkeypatch):
    monkeypatch.delenv("DRIP_SIM_DATA", raising=False)
    assert env_paths.get_backtest_data_root() == Path.home() / "drip_sim_data"


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    assert env_paths.get_backtest_data_root() == tmp_path


def test_env_whitespace_only_falls_back_to_default(monkeypatch):
    """DRIP_SIM_DATAが空白のみの場合、既定値(~/drip_sim_data)扱いになること。"""
    monkeypatch.setenv("DRIP_SIM_DATA", "   ")
    assert env_paths.get_backtest_data_root() == Path.home() / "drip_sim_data"


def test_derived_paths_compose_under_data_root(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    assert env_paths.get_bt_data_root() == tmp_path / "bt_data"
    assert env_paths.get_parquet_root() == tmp_path / "parquet_data"
    assert env_paths.get_strategies_root() == tmp_path / "strategies"
    assert env_paths.get_logs_root() == tmp_path / "logs"


def test_import_root_is_repo_import_dir():
    app_root = Path(__file__).resolve().parents[1]
    assert env_paths.get_import_root() == app_root / "import"


def test_ensure_dirs_creates_all(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    env_paths.ensure_dirs()
    for sub in ["", "bt_data", "parquet_data", "strategies", "logs"]:
        assert (tmp_path / sub).is_dir()


def test_import_root_ignores_drip_sim_data(monkeypatch, tmp_path):
    app_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    assert env_paths.get_import_root() == app_root / "import"
