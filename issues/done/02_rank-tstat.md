## s8 にエントリー数を考慮した順位（t値）を足し、順位基準の記述を実装に合わせる
id: 02
branch-slug: rank-tstat
status: close
depends: 01
type: feat
対象: core/s7_position_summary.py, core/s8_strategy_rank.py, tests/test_s7_position_summary.py, tests/test_s8_strategy_rank.py, docs/guarantees.md, README.md, README.en.md, docs/design-decisions.md
内容: いまの順位 `pips_avg_per_entry` は、エントリーが少なく偶然当たった候補を上に出しやすい。1エントリーあたり pips の t値（平均 ÷ 標準誤差）で並べた順位を、既存の順位と並べて出す。既存の順位は置き換えず、どちらを使うかは 03 の集計結果を見て user が決める。あわせて、README と design-decisions の「Recovery Factor 基準で並べる」という記述を実装（RF・回復月数は足切り、順位は平均pips）に合わせる。
対象外: 既存の `rank_by_pips_avg.csv` / `rank_by_pips_sum.csv` の並び順の変更。`s_monthly_sim` が読むスナップショットの切り替え。選抜の当たり具合の集計（03）。Deflated Sharpe などの多重検定の補正。
仮定: t値は1エントリーあたり pips_net の標本から計算する（月次pipsの t値ではない）。標準偏差は不偏（n-1）。s8 は s7 の月次CSVしか読まないので、s7 に2乗和の列を足して s8 で合算する。
確認: `PYTHONPATH=. pytest -q` が全件通る。合成データで `bt.py all` が通り、`rank/all/rank_by_tstat.csv` ができ、`--as-of` 指定時は `rank/all/snapshots/<as_of>/` に `rank_by_pips_avg.csv` と `rank_by_tstat.csv` の両方ができる。
人が見るもの: README / design-decisions の書き換えは日本語の文書なので、コミット前に jp-proofreader に校正させる（実行者が行う）。

---

### 保証
- 新たに宣言する保証:
  - s7 の月次・四半期・年次CSVは `pips_sq_sum_total`（そのグループの各クローズの `pips_net` の2乗の合計）を持つ
  - s8 は直近 `rank_months` の集計から、候補ごとに `pips_tstat` = 平均 ÷ (不偏標準偏差 / √n) を計算し、`rank_by_tstat.csv` に `pips_tstat` の降順で書く。n < 2 または標準偏差 0 の候補は `pips_tstat` を NaN にして末尾に置く
  - `rank_by_tstat.csv` の対象集合（Ban・DD フィルタ・`min_sig_per_hour` を通った候補）は `rank_by_pips_avg.csv` と同じで、並び順だけが違う
  - s8 は as-of 指定時、`rank_by_tstat.csv` もスナップショットに書く（既存のスナップショットがあれば書かない扱いは `rank_by_pips_avg.csv` と同じ）
  - 月次CSVに `pips_sq_sum_total` が無い（古い s7 の出力）場合、s8 は `rank_by_tstat.csv` を書かずにその旨を表示し、ほかの出力は従来どおり書く
- 維持する保証（docs/guarantees.md から）:
  - §15 s7: `entries_total`・`pips_sum_total`・`pips_avg_per_entry`・`bars5m_total`・`entry_rate` の集計値、不正ファイルのスキップ
  - §16 s8: `_dd_metrics` の各値、DD フィルタ、`min_sig_per_hour`、as-of はスナップショットだけを書くこと、01 で足した Ban の適用
  - `rank_by_pips_avg.csv` / `rank_by_pips_sum.csv` の並び順と列（既存列は消さない）

### core/s7_position_summary.py
- 月次の集計で `pips_net` の2乗和を `pips_sq_sum_total` として持ち、四半期・年次は月次の合計で出す。`MONTHLY_COLS` / `QUARTERLY_COLS` / `YEARLY_COLS` に足す
- `pips_sum_total` と同じく `_r2` で丸めると t値の精度が落ちるので、2乗和は丸めないか桁を多めに残す

### core/s8_strategy_rank.py
- `rank_agg` の集計（258 行付近）に `pips_sq_sum_total` の合計を足し、`pips_tstat` を計算する
- `rank_by_tstat.csv` を `rank_by_pips_avg.csv` と同じ列＋`pips_tstat` で書く

### README.md / README.en.md / docs/design-decisions.md
- 「Recovery Factor 基準で並べる」とある箇所（README.md 5・92・101 行付近、README.en.md の対応箇所、design-decisions.md の「ランキングはDDフィルタを通してから〜」の節）を、「RF と回復月数で足切りし、残った候補を平均pipsと t値で並べる」に直す
- 経緯は書かず、現時点の事実だけを書く
