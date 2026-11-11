# env-paths

| 保証 | 対応テスト |
|---|---|
| `get_backtest_data_root()` は、環境変数 `DRIP_SIM_DATA` が未設定なら `~/drip_sim_data` を返す | `test_default_data_root_is_under_home` |
| `get_backtest_data_root()` は、`DRIP_SIM_DATA` が設定されていればその値を返す | `test_env_override` |
| `get_backtest_data_root()` は、`DRIP_SIM_DATA` が空白のみなら `~/drip_sim_data` を返す | `test_env_whitespace_only_falls_back_to_default` |
| `get_bt_data_root()` は `get_backtest_data_root()` 直下の `bt_data` を返す | `test_derived_paths_compose_under_data_root` |
| `get_parquet_root()` は `get_backtest_data_root()` 直下の `parquet_data` を返す | `test_derived_paths_compose_under_data_root` |
| `get_strategies_root()` は `get_backtest_data_root()` 直下の `strategies` を返す | `test_derived_paths_compose_under_data_root` |
| `get_logs_root()` は `get_backtest_data_root()` 直下の `logs` を返す | `test_derived_paths_compose_under_data_root` |
| `get_import_root()` はリポジトリ直下の `import/` を返す | `test_import_root_is_repo_import_dir` |
| `ensure_dirs()` は `get_backtest_data_root()` と、その直下の `bt_data`・`parquet_data`・`strategies`・`logs` をすべて作る | `test_ensure_dirs_creates_all` |
