# cli-common

| 保証 | 対応テスト |
|---|---|
| `add_trading_args(parser)` は `--tp-pips`・`--sl-pips`・`--pip-size`・`--max-entries`・`--abn-burst-pips`・`--abn-forward-block-bars` を足し、指定が無ければどれも `None` にする | `test_add_trading_args_defaults_are_none` |
| `add_trading_args(parser, spread=True, lot=True, eod=True)` は `--spread-pips`・`--lot`・`--eod-utc` を足す | `test_optional_args_only_added_when_enabled` |
| `add_trading_args(parser)` は、`lot=True` を渡さなければ `--lot` を足さない | `test_optional_args_only_added_when_enabled` |
| `apply_env_overrides(env, args)` は、CLI で指定した引数だけを対応する環境変数名（例: `RR_TP_PIPS`）に書く | `test_apply_env_overrides_only_sets_provided_flags` |
| `apply_env_overrides(env, args)` は、CLI で指定していない既存の環境変数をそのまま残す | `test_apply_env_overrides_only_sets_provided_flags`, `test_apply_env_overrides_with_no_cli_args_returns_copy_of_env` |
| `apply_env_overrides(env, args)` は、渡した `env` を変えずに新しい辞書を返す | `test_apply_env_overrides_only_sets_provided_flags`, `test_apply_env_overrides_with_no_cli_args_returns_copy_of_env` |
