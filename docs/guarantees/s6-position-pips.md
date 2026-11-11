# s6-position-pips

## pips の計算（`_fv`・`_calc_pips`）

| 保証 | 対応テスト |
|---|---|
| `_fv` は、設定値が無ければ既定値を返す | `test_fv_iv_defaults_and_fallback`（`tests/test_s6_position_pips.py`） |
| `_fv` は、設定値が数値として読めなければ例外を出さずに既定値を返す | `test_fv_iv_defaults_and_fallback`（`tests/test_s6_position_pips.py`） |
| `_calc_pips` は、閉じた行の `pips_net` を、`(close_price - entry) / PIP_SIZE` に売買方向（BUY・SELL）の符号を付け、`SPREAD_PIPS` を引いた値にする | `test_calc_pips_tp_and_sl_are_computed_from_price_delta_not_args`, `test_calc_pips_other_reason_computed_from_price_delta` |
| `_calc_pips` は、TP・SL で閉じた行にも価格差を使い、`RR_TP_PIPS`・`RR_SL_PIPS` を使わない | `test_calc_pips_tp_and_sl_are_computed_from_price_delta_not_args` |
| `_calc_pips` は、`close_price` が欠けた行の `pips_net` を `NaN` にする | `test_calc_pips_missing_price_yields_nan` |
| S5 を `RR_TP_PIPS=40` で流したイベントファイルに引数無しで `_process_one` を当てると、TP で閉じた行の `pips_net` は `40 − 0.3`（既定のスプレッド）になる | `test_s5_tp_40_then_s6_without_args_gives_40_minus_spread` |

## イベントファイルへの書き込み（`_process_one`・`run`）

| 保証 | 対応テスト |
|---|---|
| `_process_one` は、`pips_net` を計算してファイルに書き、`"wrote"` を返す | `test_process_one_writes_pips_net_column` |
| `_process_one` は、`pips_net` を付け終えたファイルで、付けたときの `PIP_SIZE`・`SPREAD_PIPS` が今回と同じなら何もせず `"skipped"` を返す | `test_process_one_skips_when_done_with_same_pip_size_and_spread` |
| `_process_one` は、`pips_net` を付け終えたファイルでも、付けたときの `PIP_SIZE`・`SPREAD_PIPS` が今回と違えば付け直す | `test_process_one_recomputes_when_spread_or_pip_size_changes` |
| `_process_one` は、付けたときの値を残していないファイルの `pips_net` を付け直す | `test_process_one_recomputes_file_that_has_pips_net_but_no_recorded_args` |
| `_process_one` は、付け直すとき、S5 がファイルに残した引数の記録を保つ | `test_process_one_keeps_s5_args_recorded_in_the_file` |
| `_process_one` は、書き込み中に例外が起きると `"error"` を返し、元のファイルを壊さない | `test_process_one_write_failure_leaves_original_file_untouched` |
| `run` は、`pos_events/` 配下のファイルに `pips_net` 列を書く | `test_run_end_to_end`（`tests/test_s6_position_pips.py`） |
