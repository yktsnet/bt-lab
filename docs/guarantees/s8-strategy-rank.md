# s8-strategy-rank

## ドローダウン指標（`_dd_metrics`）

| 保証 | 対応テスト |
|---|---|
| `_dd_metrics` の `abs_dd` は、累積 pips のピークからの最大下落幅である | `test_dd_metrics_hand_calculated`, `test_dd_metrics_no_drawdown_gives_infinite_recovery_factor` |
| `_dd_metrics` の `recovery_factor` は `total_pips / abs_dd` である | `test_dd_metrics_hand_calculated` |
| `_dd_metrics` は、ドローダウンの無い系列に `recovery_factor=inf` を返す | `test_dd_metrics_no_drawdown_gives_infinite_recovery_factor` |
| `_dd_metrics` の `recovery_months` は `abs_dd /（利益月の pips の平均）` である | `test_dd_metrics_hand_calculated` |
| `_dd_metrics` は、利益月が1ヶ月も無い系列に `recovery_months=inf` を返す | `test_dd_metrics_no_profit_months_gives_infinite_recovery_months` |

## t 値（`_pips_tstat`）

| 保証 | 対応テスト |
|---|---|
| `_pips_tstat(n, total, sq_total)` は `平均 / (不偏標準偏差 / √n)` を返す | `test_pips_tstat_hand_calculated` |
| `_pips_tstat` は、`n < 2` なら NaN を返す | `test_pips_tstat_is_nan_for_single_entry_or_zero_deviation` |
| `_pips_tstat` は、標準偏差が0なら NaN を返す | `test_pips_tstat_is_nan_for_single_entry_or_zero_deviation` |
| `_pips_tstat` は、分散が「2乗平均と1のうち大きいほう」の 1e-12 倍以下なら NaN を返し、それより大きければ t 値を返す | `test_pips_tstat_keeps_small_but_nonzero_deviation_and_nans_float_noise`, `test_pips_tstat_nan_threshold_is_1e12_of_max_mean_square_and_one` |

## ランキングと絞り込み（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、サマリーディレクトリが無ければ `Run s7 first` を含むメッセージを表示する | `test_run_no_summary_dir_prints_message` |
| `run` は、`recovery_factor` が `rf_min` に届かない戦略を `rank_by_pips_avg.csv` から外し、`dd_filtered.csv` に入れる | `test_run_ranks_and_filters_by_recovery_factor` |
| `run` は、`recovery_months` が `recovery_months_max` を超える戦略を `dd_filtered.csv` へ回す | `test_run_moves_strategy_over_recovery_months_max_to_dd_filtered` |
| `run` は直近 `rank_months` か月だけを集計する | `test_run_aggregates_only_last_rank_months` |
| `run` は、エントリー頻度が `min_sig_per_hour` 未満の戦略をランキングから外す | `test_run_min_sig_per_hour_excludes_low_frequency_strategies` |

## Ban の適用（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、as-of が無ければ `ban/` の最新の `entry_ban_all_*.yaml`（`ban/asof/` 配下は除く）だけを読み、Ban された候補をランキングから外す | `test_run_without_as_of_excludes_latest_ban_file` |
| `run` は、Ban で外した件数を表示する | `test_run_without_as_of_excludes_latest_ban_file`, `test_run_as_of_reads_only_that_months_ban_file` |
| `run` は、as-of を指定すると `ban/asof/<as_of>/entry_ban_all.yaml` だけを読み、Ban された候補をランキングから外す | `test_run_as_of_reads_only_that_months_ban_file` |
| `run` は、as-of の月の Ban ファイルが無ければ、最新の Ban があっても使わずにどの候補も外さず、`no ban file found` を表示する | `test_run_without_ban_file_excludes_nobody_and_says_so` |
| `run` は、全候補が Ban されてもエラーにせず、空のランキングを書く | `test_run_all_candidates_banned_yields_empty_rank` |

## as-of のスナップショット（`run`）

| 保証 | 対応テスト |
|---|---|
| `run` は、as-of を指定すると `rank/all/rank_by_pips_avg.csv` を変えず、`rank/all/snapshots/<as_of>/` にだけ結果を書く | `test_run_as_of_writes_snapshot_not_latest_rank` |
| `run` は、as-of を指定すると `rank_by_tstat.csv` も `rank/all/snapshots/<as_of>/` に書き、`rank/all/rank_by_tstat.csv` は書かない | `test_run_as_of_writes_tstat_snapshot_and_keeps_existing_one` |
| `run` は、スナップショットに `rank_by_tstat.csv` が既にあれば上書きしない | `test_run_as_of_writes_tstat_snapshot_and_keeps_existing_one` |

## t 値のランキング（`rank_by_tstat.csv`）

| 保証 | 対応テスト |
|---|---|
| `run` は、候補ごとの `pips_tstat` を求め、`rank_by_tstat.csv` に `pips_tstat` の降順で書く | `test_run_writes_rank_by_tstat_sorted_desc_with_nan_last` |
| `rank_by_tstat.csv` は、`pips_tstat` が NaN の候補を末尾に置く | `test_run_writes_rank_by_tstat_sorted_desc_with_nan_last` |
| `rank_by_tstat.csv` の候補は、Ban・DD の絞り込み・`min_sig_per_hour` を通った `rank_by_pips_avg.csv` の候補と同じである | `test_run_tstat_uses_same_candidate_set_after_filters`, `test_run_min_sig_per_hour_applies_to_tstat_rank_too` |
| `rank_by_tstat.csv` の列は、`rank_by_pips_avg.csv` の列に `pips_tstat` を足したものである | `test_run_writes_rank_by_tstat_sorted_desc_with_nan_last` |
| `rank_by_pips_avg.csv` の並びと列は、t 値を書いても変わらない | `test_run_writes_rank_by_tstat_sorted_desc_with_nan_last` |
| `run` は、月次 CSV に `pips_sq_sum_total` が無ければ `rank_by_tstat.csv`（スナップショットを含む）を書かず、その旨を表示する | `test_run_without_pips_sq_sum_total_skips_tstat_but_writes_other_outputs`, `test_run_without_pips_sq_sum_total_skips_tstat_snapshot` |
| `run` は、`pips_sq_sum_total` が無くても `rank_by_pips_avg.csv`・`rank_by_pips_sum.csv`・`dd_filtered.csv` を書く | `test_run_without_pips_sq_sum_total_skips_tstat_but_writes_other_outputs`, `test_run_without_pips_sq_sum_total_skips_tstat_snapshot` |
