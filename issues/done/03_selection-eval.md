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
