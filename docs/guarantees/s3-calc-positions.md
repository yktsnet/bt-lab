# s3-calc-positions

## 対象月と Ban の読み込み（`_filter_recent_months`・`_load_ban_set`）

| 保証 | 対応テスト |
|---|---|
| `_filter_recent_months` は、月次ファイルの一覧の末尾から直近 `n` 件を返す | `test_filter_recent_months_keeps_last_n` |
| `_filter_recent_months` は、`n` が総数以上なら全件を返す | `test_filter_recent_months_keeps_last_n` |
| `_load_ban_set` は、ファイルが無ければ空集合を返し、`not found` を含むメッセージを表示する | `test_load_ban_set_missing_file_returns_empty` |
| `_load_ban_set` は、`None` と空文字列に空集合を返す | `test_load_ban_set_no_path_returns_empty` |
| `_load_ban_set` は、Ban の yaml の `entries` の各行を `id`（または `tid`）と `slug` のペアとして読む | `test_load_ban_set_parses_entries` |
| `_load_ban_set` は、`slug` の無い行を無視する | `test_load_ban_set_parses_entries` |

## セッション列・出力パス・並列数（`_add_session_column`・`_out_path`・`_jobs`）

| 保証 | 対応テスト |
|---|---|
| `_add_session_column` は、`time_utc` 列が無ければ `session` 列を空文字列で埋める | `test_add_session_column_without_time_utc_is_empty_string` |
| `_add_session_column` は、`time_utc` の時刻に応じて `session` 列に `TYO`・`LON` を入れる | `test_add_session_column_assigns_expected_sessions` |
| `_out_path` は `<root>/<kind>/<slug>/year=<year>/<MM>.parquet` のパスを組み立てる | `test_out_path_and_parse_year_month_roundtrip` |
| `_parse_year_month` は、`year=<year>/<MM>.parquet` のパスから `(year, month)` の整数のタプルを取り出す | `test_out_path_and_parse_year_month_roundtrip` |
| `_jobs` は、数値の文字列をそのジョブ数にする | `test_jobs_auto_and_explicit_and_invalid` |
| `_jobs` は、`"auto"` に1以上のジョブ数を返す | `test_jobs_auto_and_explicit_and_invalid` |
| `_jobs` は、数値でない文字列でも例外を出さずに1以上のジョブ数を返す | `test_jobs_auto_and_explicit_and_invalid` |

## 戦略・月ごとの計算（`_process_strategy_month`）

| 保証 | 対応テスト |
|---|---|
| `_process_strategy_month` は、戦略を当てた結果のうち `entry_flag` が立った行だけを出力ファイルに書く | `test_process_strategy_month_writes_only_entry_flag_rows` |
| `_process_strategy_month` は、`entry_interval_min` を指定すると、分がその倍数のバーだけを残す | `test_process_strategy_month_entry_interval_filters_minutes`, `test_process_strategy_month_recomputes_when_entry_interval_changes` |
| `_process_strategy_month` は、出力が入力より新しく、出力を作ったときの `entry_interval_min` が今回と同じなら計算を飛ばして `False` を返す | `test_process_strategy_month_skips_when_output_is_fresh`, `test_process_strategy_month_recomputes_when_entry_interval_changes` |
| `_process_strategy_month` は、出力が入力より新しくても、出力を作ったときの `entry_interval_min` が今回と違えば計算し直す | `test_process_strategy_month_recomputes_when_entry_interval_changes` |
| `_process_strategy_month` は、作ったときの `entry_interval_min` を残していない出力を計算し直す | `test_process_strategy_month_recomputes_output_without_recorded_interval` |
| `_process_strategy_month` は、計算し直した結果エントリーが1つも残らなければ、前に作った出力を消す | `test_process_strategy_month_removes_stale_output_when_no_entry_remains` |
| `_process_strategy_month` は、書き込み中に例外が起きても既存の出力を壊さない | `test_process_strategy_month_write_failure_leaves_existing_output_untouched` |
| `_process_strategy_month` は、同梱の `strategies_md/oscillator/rsi_zone/template.py` から生成した戦略に対しても、`entry_flag`・`buy_sell`・`trend_dir` の3列を持つ出力を書く | `test_process_strategy_month_honors_real_rsi_zone_template_contract` |

## 全体の実行（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、対象月・戦略ごとに `positions/<kind>/<slug>/year=<year>/<MM>.parquet` を書き出す | `test_run_end_to_end_writes_positions` |
| `run` は、`ban/` に Ban ファイルがあっても自動では適用しない | `test_run_does_not_auto_apply_latest_ban_file` |
| `run` は、`--ban-file` で明示した Ban ファイルの戦略を計算しない | `test_run_applies_explicit_ban_file` |
