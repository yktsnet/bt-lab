# s-selection-eval

## 集計の対象と出力（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、`rank/all/snapshots/<M>/` の `rank_by_*.csv` ごとに1行を `rank/all/eval/selection_eval.csv` に書く | `test_hand_calculated_row`, `test_all_rank_files_in_snapshot_are_evaluated` |
| `selection_eval.csv` の列は `snapshot`・`rank_file`・`n_universe`・`n_selected`・`univ_mean_pips`・`sel_mean_pips`・`sel_minus_univ`・`topk_mean_pips`・`topk_hit_rate`・`rank_corr` である | `test_hand_calculated_row` |
| `run` は、M+1 の月次データ（S7 の `monthly_all.csv`）が無いスナップショットを集計しない | `test_snapshot_without_next_month_data_is_skipped` |
| `run` は、`--from YYYY-MM`・`--until YYYY-MM` の範囲外のスナップショットを読まない | `test_from_until_limit_snapshot_range_and_do_not_read_outside` |
| `_month_arg` は、`YYYY-MM` の形でない値を引数エラーにする | `test_month_arg_rejects_malformed` |
| `_next_month` は、12月の翌月を翌年の1月にする | `test_next_month_rolls_over_year` |
| `run` は、順位ファイルごとに、集計した月数・`sel_minus_univ` の平均・`sel_minus_univ > 0` の月の割合・`rank_corr` の平均を標準出力に表示する | `test_summary_printed_per_rank_file` |
| `run` は、書き込みに失敗しても既存の `selection_eval.csv` を壊さない | `test_write_failure_leaves_existing_output_untouched` |

## 指標の定義

| 保証 | 対応テスト |
|---|---|
| 母集団（`n_universe`・`univ_mean_pips`）は、M 以前の月次データに一度でも現れた候補である | `test_hand_calculated_row`, `test_summary_printed_per_rank_file` |
| M+1 に行が無い候補は 0 pips として数える | `test_universe_counts_missing_next_month_as_zero_pips`, `test_hand_calculated_row` |
| `sel_mean_pips` は、順位ファイルの全行の M+1 の `pips_sum_total` の平均である | `test_hand_calculated_row`, `test_top_changes_k` |
| `topk_mean_pips` は、上位 K 行の M+1 の `pips_sum_total` の平均である | `test_hand_calculated_row`, `test_top_changes_k` |
| K は `--top` で変えられ、既定は10である | `test_top_changes_k`, `test_top_defaults_to_10` |
| `topk_hit_rate` は、上位 K 行のうち M+1 の `pips_sum_total` が0より大きい行の割合である | `test_topk_hit_rate_counts_only_strictly_positive` |
| `rank_corr` は、選ばれた候補の順位と M+1 の `pips_sum_total` の Spearman 相関で、順位が良いほど稼いでいれば正になる | `test_hand_calculated_row`, `test_rank_corr_is_negative_when_ranking_inverted` |
| `rank_corr` は、選ばれた候補が3件未満なら NaN になる | `test_rank_corr_nan_under_three_selected` |
| `_spearman` は、同順位に平均順位を使い、片方が定数なら NaN を返す | `test_spearman_handles_ties_and_constants` |

## 入力が無いときの扱い（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、スナップショットが無ければ `no snapshots` を表示し、何も書かない | `test_no_snapshots_prints_message_and_writes_nothing` |
| `run` は、月次データが無ければ `monthly_all.csv` を含むメッセージを表示し、何も書かない | `test_no_monthly_data_prints_message_and_writes_nothing` |
| `run` は、どのスナップショットにも M+1 のデータが無ければ `Nothing to evaluate` を表示し、何も書かない | `test_no_next_month_for_any_snapshot_prints_message` |
