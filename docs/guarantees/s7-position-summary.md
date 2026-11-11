# s7-position-summary

## 値の丸めと期間（`_r2`・`_quarter`・`_bars_in_window`）

| 保証 | 対応テスト |
|---|---|
| `_r2` は、値を小数第2位に丸める | `test_r2_rounds_to_two_decimals` |
| `_r2` は、`None` をそのまま返す | `test_r2_none_passthrough` |
| `_r2` は、`NaN` と `inf` を `None` に直す | `test_r2_nan_and_inf_become_none` |
| `_quarter` は、月（1〜12）を四半期（1〜4）に直す | `test_quarter_mapping` |
| `_bars_in_window` は、UTC 17:00 より前のバーの数を数える | `test_bars_in_window_counts_hours_before_eod` |

## 集計の CSV（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、`pos_events/` が無ければ `pos_events/ not found` を含むメッセージを表示する | `test_run_no_pos_events_prints_message` |
| `run` は、`summary/all/<year>/` に月次・四半期・年次の CSV を書く | `test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates` |
| `run` の月次の `entries_total` は、`open` 以外の行の数である | `test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates` |
| `run` の月次の `pips_sum_total` は、`pips_net` の合計である | `test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates` |
| `run` の月次の `pips_avg_per_entry` は、1件あたりの `pips_net` の平均である | `test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates` |
| `run` の月次の `bars5m_total` は、UTC 17:00 より前のバーの数である | `test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates` |
| `run` の月次の `entry_rate` は、`entries_total / bars5m_total` である | `test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates` |
| `run` の `pips_sq_sum_total` は、クローズの `pips_net` の2乗の合計で、丸めない | `test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates`, `test_run_pips_sq_sum_total_is_not_rounded_and_sums_across_months` |
| `run` の四半期・年次の `pips_sq_sum_total` は、月次の合計である | `test_run_pips_sq_sum_total_is_not_rounded_and_sums_across_months` |
| `run` は、`type` 列が無いファイルとクローズの行が無いファイルを飛ばし、`no records found` を含むメッセージを表示する | `test_run_skips_files_without_type_column_or_empty_close` |
