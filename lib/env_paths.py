import os
from pathlib import Path


def _from_env(name: str, default: Path) -> Path:
    v = os.environ.get(name, "").strip()
    return Path(v).expanduser() if v else default


def get_backtest_data_root() -> Path:
    return _from_env("BACKTEST_DATA_ROOT", Path.home() / "bt_data" / "backtest")


def get_bt_data_root() -> Path:
    return get_backtest_data_root() / "bt_data"


def get_parquet_root() -> Path:
    return get_backtest_data_root() / "parquet_data"


def get_strategies_root() -> Path:
    return get_backtest_data_root() / "strategies"


def get_logs_root() -> Path:
    return get_backtest_data_root() / "logs"


def get_import_root() -> Path:
    return Path(__file__).resolve().parents[1] / "import"


def ensure_dirs() -> None:
    for p in [
        get_backtest_data_root(),
        get_bt_data_root(),
        get_parquet_root(),
        get_strategies_root(),
        get_logs_root(),
    ]:
        p.mkdir(parents=True, exist_ok=True)
