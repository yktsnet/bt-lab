## PR記録: feat: 選抜の当たり具合を月ごとに集計する段を足す
issue: 03 (03_selection-eval.md)
PR: https://github.com/yktsnet/drip-sim/pull/16

## 変更内容
- `core/s_selection_eval.py` を新規追加。`rank/all/snapshots/<M>/` の `rank_by_*.csv` ごとに、M+1 の月次データ（s7 の `monthly_all.csv`）がある月だけを集計し、`rank/all/eval/selection_eval.csv` に 1行 = (スナップショット月, 順位ファイル) で書く（`n_universe`, `n_selected`, `univ_mean_pips`, `sel_mean_pips`, `sel_minus_univ`, `topk_mean_pips`, `topk_hit_rate`, `rank_corr`）
- 母集団は M 以前の月次データに現れた候補、M+1 に行が無い候補は 0 pips。Spearman は順位化→Pearson で自前計算（scipy 不使用）
- `--top K`（既定 10）、`--from` / `--until`（範囲外のスナップショットは読まない）。出力は atomic。データが無いときは表示して終了コード 0
- `bt.py` の `STAGES` に `eval` を登録（`PIPELINE_ORDER`・`PHASES` には入れない）
- structure.md / README.md / README.en.md / docs/guarantees.md（§20 新設、§19 に eval の登録を追記）を更新
- 追加コミットで `--from` / `--until` が範囲外を読まないこと（until 側を無効化すると失敗する）と `--top` の既定 10 をテストで固定

## 保証
- 出力列・手計算の値・母集団・0 pips 扱い → tests/test_s_selection_eval.py: test_hand_calculated_row, test_universe_counts_missing_next_month_as_zero_pips
- topk_hit_rate / --top → test_topk_hit_rate_counts_only_strictly_positive, test_top_changes_k, test_top_defaults_to_10
- rank_corr の向き・3件未満 NaN・同順位/定数 → test_rank_corr_is_negative_when_ranking_inverted, test_rank_corr_nan_under_three_selected, test_spearman_handles_ties_and_constants
- M+1 無しの月を飛ばす・全 rank_by_*.csv が対象・標準出力の要約 → test_snapshot_without_next_month_data_is_skipped, test_all_rank_files_in_snapshot_are_evaluated, test_summary_printed_per_rank_file
- --from/--until と範囲外を読まない・形式検証 → test_from_until_limit_snapshot_range_and_do_not_read_outside, test_month_arg_rejects_malformed, test_next_month_rolls_over_year
- データ無しで表示して終了コード 0 / atomic → test_no_snapshots_…, test_no_monthly_data_…, test_no_next_month_for_any_snapshot_…, test_write_failure_leaves_existing_output_untouched
- bt.py に eval を登録し PIPELINE_ORDER 外 → test_eval_stage_is_registered_but_outside_pipeline_order
- 維持: §19 → tests/test_bt_cli.py の既存テスト

## 静的確認結果
- `PYTHONPATH=. pytest -q`: 214 passed
- 合成データで `bt.py all` → `s4 --as-of 2026-06` → `S8_AS_OF=2026-06 bt.py s8` → `bt.py eval` が終了コード 0 で CSV と要約を出力。同梱の合成データが 2026-06〜07 のみで `monthly-backfill` が対象にする直近 3 か月と重ならないため、Issue の確認 2 は `S8_AS_OF` でスナップショットを作る手順に読み替えた（user 承認済み）

## 検証手順
- 実データで `bt.py monthly-backfill` の後に `bt.py eval --until <ホールドアウト前の月>` を回し、`sel_minus_univ` と `rank_corr` を見て順位指標と s8 の絞り方を判断する

## 確認者の判定
| 項目 | 判定 |
|---|---|
| 確認1: `pytest` 全件 | 合 |
| 確認2: `all` → `monthly-backfill --months 3` → `eval` | 否（手順の前提不成立。`S8_AS_OF` での読み替えを user が承認） |
| 保証（出力列・値・相関・範囲・atomic・bt 登録・§19 維持） | すべて合 |
| テストの期待値の出し直し | すべて合 |

---

## 選抜の当たり具合を月ごとに集計する段を足す
id: 03
branch-slug: selection-eval
status: close
depends: 01
type: feat
対象: core/s_selection_eval.py (新規), tests/test_s_selection_eval.py (新規), bt.py, docs/guarantees.md, context/structure.md, README.md, README.en.md
内容: s8 の絞り方が翌月の成績を当てているかを測る仕組みが無い。各月末のスナップショット（M）で選ばれた候補の翌月（M+1）の成績を、全候補と比べて集計する段を足す。この集計で、順位の付け方を採用するか変えるかを判断する。スナップショット内の `rank_by_*.csv` をすべて対象にするので、02 の t値順位が入れば自動で比べられる。
対象外: s8 の閾値や順位指標の変更。`s_monthly_sim` の変更（集計は s7 の月次CSVから行い、シムの日次CSVは使わない）。PBO・Deflated Sharpe などの統計。`bt.py all` の `PIPELINE_ORDER` への追加。
仮定: 翌月の成績は s7 の `monthly_all.csv` の `pips_sum_total` で測る（s5 を回したときの TP/SL・スプレッドがそのまま前提になる）。母集団は「スナップショット月 M 以前の月次CSVに一度でも現れた候補」とし、M+1 に行が無い候補は 0 pips として扱う。上位K件の既定は 10。
確認: `PYTHONPATH=. pytest -q` が全件通る。合成データで `bt.py all` → `bt.py monthly-backfill --months 3` の後に `bt.py eval` を回すと `rank/all/eval/selection_eval.csv` ができ、標準出力に月数・平均差・差がプラスだった月の割合・平均順位相関が出る。
人が見るもの: 実データで回した結果を見て、どの順位（`rank_by_pips_avg` / `rank_by_tstat`）を使うか、s8 の絞り方を変えるかを判断する。`--until` でホールドアウトに取っておく月を決める。

---

### 保証
- 新たに宣言する保証:
  - `s_selection_eval` は `rank/all/snapshots/<M>/` の `rank_by_*.csv` ごとに、M+1 の月次データがある月だけを集計し、1行 = (スナップショット月, 順位ファイル) で次の列を `rank/all/eval/selection_eval.csv` に書く: `n_universe`, `n_selected`, `univ_mean_pips`, `sel_mean_pips`, `sel_minus_univ`, `topk_mean_pips`, `topk_hit_rate`, `rank_corr`
  - `sel_mean_pips` は順位ファイルの全行、`topk_*` は上位K行の、M+1 の候補ごとの `pips_sum_total` の平均。`topk_hit_rate` は上位K行のうち M+1 の `pips_sum_total` > 0 の割合
  - `rank_corr` は選ばれた候補の順位と M+1 の `pips_sum_total` の Spearman 相関（順位の大きい=悪い向きを考慮し、当たっていれば正）。対象が 3 件未満なら NaN
  - `--from YYYY-MM` / `--until YYYY-MM` でスナップショット月の範囲を絞れる。範囲外の月は読まない
  - 出力は atomic に書く。スナップショットや M+1 の月次データが無いときは、その旨を表示して終了コード 0 で終わる
  - `bt.py eval` で実行できる（`STAGES` に登録し、`PIPELINE_ORDER` には入れない）
- 維持する保証（docs/guarantees.md から）:
  - §19 bt.py: `STAGES` の各サブコマンドに対応するスクリプトが実在すること、`PIPELINE_ORDER` が s1b〜s8 で固定されていること、`PHASES` が `PIPELINE_ORDER` を過不足なく分割すること

### core/s_selection_eval.py
- 依存は pandas / numpy のみ（scipy を足さない）。Spearman は順位化してから Pearson で計算する
- 標準出力の要約は順位ファイルごとに: 集計した月数、`sel_minus_univ` の平均、`sel_minus_univ` > 0 の月の割合、`rank_corr` の平均
- `--top K` で上位件数を変えられる

### bt.py
- `STAGES` に `"eval": "s_selection_eval.py"` を足す

### context/structure.md / README.md / README.en.md
- 構成図と stage 一覧に新しい段を1行ずつ足す
