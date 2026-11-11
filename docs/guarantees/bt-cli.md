# bt-cli

## ステージの定義（`STAGES`・`PIPELINE_ORDER`・`PHASES`）

| 保証 | 対応テスト |
|---|---|
| `STAGES` の各ステージ名は、`core/` 配下に実在するスクリプトファイルを指す | `test_stage_scripts_exist` |
| `PIPELINE_ORDER` は `["s1b", "s1c", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]` の固定順である | `test_pipeline_order_is_s1b_through_s8` |
| `PIPELINE_ORDER` は `STAGES` のキーの部分集合である | `test_pipeline_order_is_s1b_through_s8` |
| `PHASES`（`bt flow` のフェーズ分割）を先頭から順に連結すると `PIPELINE_ORDER` と完全一致する | `test_phases_cover_pipeline_order_exactly` |
| `STAGES` の `eval` は `s_selection_eval.py` を指す | `test_eval_stage_is_registered_but_outside_pipeline_order`（`tests/test_s_selection_eval.py`） |
| `eval` は `PIPELINE_ORDER` にも `PHASES` にも入らない | `test_eval_stage_is_registered_but_outside_pipeline_order`（`tests/test_s_selection_eval.py`） |

## `bt` の起動とステージの実行

| 保証 | 対応テスト |
|---|---|
| 引数無しで呼ぶと、`stages:` を含む使い方を標準出力に表示して終了コード `0` を返す | `test_no_args_prints_help_and_exits_0` |
| `STAGES` に無いステージ名を渡すと、標準エラーに `unknown stage` を出して終了コード `2` を返す | `test_unknown_stage_exits_2` |
| `bt <stage> [options]` は `subprocess.run` で `[sys.executable, core/<script>, *extra_args]` を起動し、追加引数をそのまま渡す | `test_stage_dispatch_forwards_extra_args_to_subprocess`, `test_stage_dispatch_with_no_extra_args` |
| `all` に追加引数を渡すと、標準エラーに `does not forward extra args` を出して終了コード `2` を返す | `test_all_rejects_extra_args` |
| `all` は、いずれかのステージが非ゼロ終了コードを返した時点で中断し、後続のステージを実行しない | `test_all_aborts_on_first_stage_failure` |

## `bt flow`

| 保証 | 対応テスト |
|---|---|
| `flow` に追加引数を渡すと、標準エラーに `does not take extra args` を出して終了コード `2` を返す | `test_flow_rejects_extra_args` |
| `flow` は `q` の入力で、何も実行せずに終了コード `0` を返す | `test_flow_quit_immediately_runs_nothing` |
| `flow` はフェーズ番号以外の入力に `Invalid choice` を表示し、メニューに戻る | `test_flow_invalid_choice_then_quit` |
| `flow` は、選んだフェーズの確認に `n` と答えると、そのフェーズを実行せずに `Skipped.` を表示する | `test_flow_declining_confirmation_skips_phase` |
| `flow` は、選んだフェーズの確認に `y` と答えると、フェーズ内のステージを順に実行する | `test_flow_runs_selected_phase_stages_in_order` |
| `flow` は、Position engine フェーズの実行前に TP/SL pips の入力を求める | `test_flow_position_engine_phase_prompts_for_tp_sl` |
| `flow` は、入力された TP/SL pips を `--tp-pips`/`--sl-pips` としてステージに渡す | `test_flow_position_engine_phase_prompts_for_tp_sl` |
| `flow` は、フェーズ内のステージが非ゼロ終了コードを返すとそのフェーズを中断し、標準エラーに `Phase failed` を出してメニューに戻る | `test_flow_aborts_phase_on_stage_failure_and_returns_to_menu` |
| `flow` の `v` は `_view_results` を呼ぶ | `test_flow_view_results_menu_entry` |

## S8 の結果の履歴（`_run_stage`）

| 保証 | 対応テスト |
|---|---|
| `_run_stage` は、`s8` が終了コード `0` で成功すると `rank/all/*.csv` を `rank/all/history/<timestamp>/` へコピーする | `test_run_stage_archives_rank_output_after_s8_success` |
| `_run_stage` は、`s8` が失敗したときはコピーしない | `test_run_stage_does_not_archive_on_s8_failure` |
| `_run_stage` は、`s8` 以外のステージが成功してもコピーしない | `test_run_stage_does_not_archive_for_non_s8_stages` |

## 結果の一覧と表示（`_result_entries`・`_view_results`）

| 保証 | 対応テスト |
|---|---|
| `_result_entries` は `rank/all` → `rank/all/history/<timestamp>`（新しい順）→ `monthly/<YYYY-MM>` の順に結果ディレクトリを並べる | `test_result_entries_lists_latest_history_then_monthly` |
| `_view_results` は、結果が1つも無ければ `no results found` を表示する | `test_view_results_no_results_prints_message` |
| `_view_results` は、選んだディレクトリの CSV の中身を表示する | `test_view_results_selects_and_prints_csv` |

## `fzf` での選択（`_fzf_select`）

| 保証 | 対応テスト |
|---|---|
| `_fzf_select` は、`fzf` が `PATH` に無ければ標準エラーに `fzf not found` を出して `None` を返す | `test_fzf_select_not_found_in_path` |
| `_fzf_select` は `subprocess.run(["fzf", f"--prompt={prompt}> "], input="\n".join(choices), capture_output=True, text=True)` を呼ぶ | `test_fzf_select_invokes_real_subprocess_with_expected_args` |
| `_fzf_select` は、`fzf` が終了コード `0` で空でない行を返せばその文字列を返す | `test_fzf_select_invokes_real_subprocess_with_expected_args` |
| `_fzf_select` は、`fzf` が非ゼロ終了コードを返すと `None` を返す | `test_fzf_select_returns_none_on_nonzero_exit` |
| `_fzf_select` は、`fzf` の出力が空なら `None` を返す | `test_fzf_select_returns_none_on_empty_choice` |

## 最終実行の表示（`_last_run_text`）

| 保証 | 対応テスト |
|---|---|
| `_last_run_text` は、対象ディレクトリが無ければ `never run` を返す | `test_last_run_text_never_run_for_missing_dir` |
| `_last_run_text` は、対象ディレクトリにファイルが1つも無ければ `never run` を返す | `test_last_run_text_never_run_for_empty_dir` |
| `_last_run_text` は、最終更新から1日未満なら `updated today` を返す | `test_last_run_text_updated_today` |
| `_last_run_text` は、最終更新から1日以上2日未満なら `updated 1 day ago` を返す | `test_last_run_text_updated_one_day_ago` |
| `_last_run_text` は、最終更新から2日以上なら `updated N days ago` を返す | `test_last_run_text_updated_n_days_ago` |
| `_last_run_text` は、ファイルが複数あれば最も新しい mtime を最終更新とする | `test_last_run_text_uses_latest_file_among_many` |
