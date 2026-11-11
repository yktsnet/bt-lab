# s-monthly-sim

## 対象の月と戦略（`trading_days_in_month`・`_target_months`・`_load_strategies_from_snapshot`）

| 保証 | 対応テスト |
|---|---|
| `trading_days_in_month` は、その月の土日を除いた日付を返す | `test_trading_days_in_month_excludes_weekends` |
| `_target_months` は、`sim_month` を指定するとその1か月だけを返す | `test_target_months_explicit_sim_month` |
| `_target_months` は、`sim_month` が空なら先月までの12か月を古い順に返す | `test_target_months_default_returns_12_months_ending_last_month`, `test_target_months_default_is_12_months_up_to_last_month` |
| `_load_strategies_from_snapshot` は、スナップショットのランク CSV から `pips_avg_per_entry` が `min_avg` 以上の戦略だけを読む | `test_load_strategies_from_snapshot_filters_by_min_avg` |
| `_load_strategies_from_snapshot` は、戦略ファイルが無い行を無視する | `test_load_strategies_from_snapshot_filters_by_min_avg` |
| `_load_strategies_from_snapshot` は、スナップショットが無ければ空のリストを返し、`snapshot not found` を表示する | `test_load_strategies_from_snapshot_missing_snapshot_returns_empty` |

## 日次の集計（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、スナップショットの戦略ごとに `tid`・`slug`・`entries`・`pips_sum`・`pips_avg` 列の日次 CSV を `monthly/<month>/ALL/` に書く | `test_run_writes_daily_csv_for_snapshot_strategies` |
| `run` は、日次 CSV の書き込み中に例外が起きても、壊れた日次 CSV を残さない | `test_run_write_failure_does_not_leave_partial_daily_csv` |
| `run` は、対象月の前月のスナップショットが無ければ `no snapshot for <前月>` を表示する | `test_run_skips_month_without_snapshot` |
| `run` は、前月のスナップショットが無い月に何も書かない | `test_run_writes_nothing_for_month_without_snapshot` |
| `run` は、同じ戦略・月・売買の引数なら、S3（既定の30分間隔）→ S5 → S6 と、日ごと（閉じた日）のエントリー件数と pips の合計が一致する | `test_run_matches_s3_s5_s6_entries_and_pips_per_day` |
| `run` は、特徴量に S1c が焼き込んだ月の parquet の列を使う | `test_run_matches_s3_s5_s6_entries_and_pips_per_day` |
| `run` は、`buy_sell` が BUY・SELL でないバーではポジションを建てない | `test_run_does_not_open_positions_on_bars_without_side` |
