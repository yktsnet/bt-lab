# s5-position-engine

## 時刻と設定値の読み取り（`_hm`・`_fv`・`_iv`）

| 保証 | 対応テスト |
|---|---|
| `_hm` は、`"HH:MM"` を0時からの分に直す | `test_hm_parses_hhmm` |
| `_hm` は、ISO の日時（`T` 区切り・空白区切り）の時刻を0時からの分に直す | `test_hm_parses_iso_timestamp_with_t_separator`, `test_hm_parses_iso_timestamp_with_space_separator` |
| `_hm` は、`None` と空文字列に `None` を返す | `test_hm_none_or_empty_returns_none` |
| `_fv` は、設定値が無ければ既定値を返す | `test_fv_iv_defaults_and_fallback`（`tests/test_s5_position_engine.py`） |
| `_fv` は、設定値が数値として読めなければ例外を出さずに既定値を返す | `test_fv_iv_defaults_and_fallback`（`tests/test_s5_position_engine.py`） |
| `_iv` は、設定値が無ければ既定値を返す | `test_fv_iv_defaults_and_fallback`（`tests/test_s5_position_engine.py`） |
| `_iv` は、設定値が数値として読めなければ既定値を返す | `test_iv_returns_default_for_non_numeric`（`tests/test_s5_position_engine.py`） |

## ポジションの建て方と閉じ方（`_build_positions`）

| 保証 | 対応テスト |
|---|---|
| `_build_positions` は、BUY の高値が `entry + RR_TP_PIPS` に届くと `abnormal="TP"` で閉じる | `test_build_positions_opens_then_hits_tp` |
| `_build_positions` は、SELL の高値が `entry + RR_SL_PIPS` に届くと `abnormal="SL"` で閉じる | `test_build_positions_hits_sl` |
| `_build_positions` は、`EOD_UTC` に達すると未決済のポジションを `abnormal="EOD"` で閉じる | `test_build_positions_eod_forces_close` |
| `_build_positions` は、`high - low` が `ABN_BURST_HL_PIPS` 以上のバーのあと、`ABN_FORWARD_BLOCK_BARS` 本のエントリーを建てない | `test_build_positions_spark_blocks_forward_entries` |
| `_build_positions` は、`MAX_ENTRIES_PER_STRAT` を超えてポジションを建てない | `test_build_positions_max_entries_per_strat_caps_opens` |
| `_build_positions` は、`entry_flag` の立ったバーの次のバーで建てる | `test_build_positions_opens_on_bar_after_entry_flag` |

## 戦略・月ごとの計算（`_process_one`・`run`）

| 保証 | 対応テスト |
|---|---|
| `_process_one` は、月の parquet と signal のファイルが揃っていれば `pos_events/<kind>/<slug>/year=<year>/<MM>.parquet` を書いて `"wrote"` を返す | `test_process_one_writes_events_parquet` |
| `_process_one` は、入力のファイルが無ければ `"skipped"` を返す | `test_process_one_skips_when_inputs_missing` |
| `_process_one` は、出力が入力より新しく、出力を作ったときの売買の引数（`PIP_SIZE`・`RR_TP_PIPS`・`RR_SL_PIPS`・`LOT_PER_ENTRY`・`MAX_ENTRIES_PER_STRAT`・`ABN_BURST_HL_PIPS`・`ABN_FORWARD_BLOCK_BARS`・`EOD_UTC`）がすべて今回と同じなら `"skipped"` を返す | `test_process_one_skips_when_fresh_and_trade_args_unchanged` |
| `_process_one` は、出力が入力より新しくても、売買の引数のどれかが今回と違えば計算し直す | `test_process_one_recomputes_when_any_trade_arg_changes` |
| `_process_one` は、作ったときの売買の引数を残していない出力を計算し直す | `test_process_one_recomputes_output_without_recorded_args` |
| `_process_one` は、計算し直した結果イベントが1つも無ければ、前に作った出力を消す | `test_process_one_removes_stale_output_when_no_event_remains` |
| `_process_one` は、書き込み中に例外が起きると `"error"` を返し、既存の出力を壊さない | `test_process_one_write_failure_leaves_existing_output_untouched` |
| `run` は、全戦略・全月を処理して `pos_events/` にイベントファイルを書き出す | `test_run_end_to_end`（`tests/test_s5_position_engine.py`） |
