# s4-ban-build

## 発火時刻の重なり（`_jaccard`・`_jaccard_dedup`）

| 保証 | 対応テスト |
|---|---|
| `_jaccard` は、両方が空集合なら `1.0` を返す | `test_jaccard_both_empty_is_1` |
| `_jaccard` は、片方だけが空集合なら `0.0` を返す | `test_jaccard_one_empty_is_0` |
| `_jaccard` は、それ以外では積集合の大きさを和集合の大きさで割った値を返す | `test_jaccard_partial_overlap` |
| `_jaccard_dedup` は、類似度が閾値を上回るペアのうち、後から出てきたキーを重複として除く | `test_jaccard_dedup_removes_near_duplicate_later_key` |
| `_jaccard_dedup` は、類似度が閾値未満のペアをすべて残す | `test_jaccard_dedup_below_threshold_keeps_all` |

## 対象月とバー数（`_parse_year_month`・`_bars_in_window`・`_list_recent_parquet`）

| 保証 | 対応テスト |
|---|---|
| `_parse_year_month` は、`year=YYYY/MM.parquet` のパスから `(year, month)` の整数のタプルを取り出す | `test_parse_year_month` |
| `_bars_in_window` は、UTC 0:00 以上 17:00 未満のバーの数を数える | `test_bars_in_window_counts_hours_in_range` |
| `_bars_in_window` は、ファイルが無ければ `0` を返す | `test_bars_in_window_missing_file_returns_zero` |
| `_list_recent_parquet` は、`as_of`（`YYYY-MM`）以前の月に絞ってから直近 `n` 件を返す | `test_list_recent_parquet_as_of_drops_later_months` |

## Ban の判定と書き出し（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、エントリー率が `min_rate` を下回る戦略を `reason: low_rate` で Ban の yaml に書く | `test_run_bans_low_rate_strategy_and_keeps_normal_one` |
| `run` は、エントリー率が `min_rate` から `max_rate` に収まる戦略を Ban しない | `test_run_bans_low_rate_strategy_and_keeps_normal_one` |
| `run` は、エントリー率が `max_rate` を超える戦略を `reason: high_rate` で Ban の yaml に書く | `test_run_bans_high_rate_strategy` |
| `run` は、対象月のバー数が0の戦略を `reason: no_data` で Ban の yaml に書く | `test_run_bans_no_data_strategy_when_bars_in_window_is_zero` |
| `run` は、発火時刻が重なる戦略のうち後のものを `reason: jaccard_dedup` で Ban の yaml に書き、先のものは Ban しない | `test_run_jaccard_dedup_bans_near_duplicate_strategy` |
| `run` は、`dry_run=True` なら Ban の yaml を書かない | `test_run_dry_run_does_not_write_ban_file` |
| `run` は、parquet ファイルが1つも無ければ `no parquet files found` を含むメッセージを表示する | `test_run_no_parquet_files_prints_message` |
| `run` は、`positions/` が無ければ `positions/ not found` を含むメッセージを表示する | `test_run_no_positions_dir_prints_message` |
| `run` は、`as_of` 無しなら `ban/entry_ban_all_<timestamp>.yaml` に書き、`as_of` を記録しない | `test_run_as_of_ignores_positions_after_as_of` |
| `run` は、Ban の yaml の書き込み中に例外が起きても既存の Ban の出力を壊さず、新しいファイルも残さない | `test_run_write_failure_leaves_existing_ban_output_untouched` |

## as-of の Ban（`run` の `as_of`）

| 保証 | 対応テスト |
|---|---|
| `run` は、`as_of` を渡すと結果を `ban/asof/<YYYY-MM>/entry_ban_all.yaml` に書き、yaml に `as_of` を記録する | `test_run_as_of_ignores_positions_after_as_of` |
| `run` は、`as_of` を渡すと、その月より後の月の positions を判定に使わない | `test_run_as_of_ignores_positions_after_as_of` |
| `run` は、同じ `as_of` で再実行すると同じパスを新しい内容で上書きする | `test_run_as_of_rerun_overwrites_same_file` |
| `run` は、`as_of` の Ban の書き込み中に例外が起きても既存の出力を壊さない | `test_run_as_of_write_failure_leaves_existing_output_untouched` |
| `run` は、`YYYY-MM` の形でない `as_of` を `ValueError` で拒む | `test_run_as_of_rejects_malformed_value` |
