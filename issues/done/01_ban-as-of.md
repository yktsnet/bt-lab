## PR記録: fix: Ban の判定を as-of 時点のデータに限り、適用を s8 に移す
issue: 01 (01_ban-as-of.md)
PR: https://github.com/yktsnet/drip-sim/pull/14

## 変更内容
- s4: `--as-of YYYY-MM` を追加。その月以前の parquet だけから直近 `--months` 件を選んで Ban を判定し、`ban/asof/<YYYY-MM>/entry_ban_all.yaml` に atomic・上書きで書く（YAML に `as_of` を記録）。`--as-of` 無しは従来どおり `ban/entry_ban_all_<timestamp>.yaml`。`YYYY-MM` 以外の値は `ValueError` で拒否する
- s3: `ban/` の最新ファイルを自動で拾う処理を外した。`--ban-file` / `S3_BAN_FILE` の明示指定だけが Ban を適用する
- s8: as-of 指定時は `ban/asof/<as_of>/entry_ban_all.yaml`、無指定なら `ban/` の最新 `entry_ban_all_*.yaml` を読み、Ban された候補を DD フィルタ・ランキングの前に外す。件数を `s8: ban excluded=<n> (<path>)` で表示し、Ban ファイルが無ければ誰も外さずその旨を表示する。全候補が外れても落ちないよう `dd_df` の列を固定した
- backfill: 各月で s4 `--as-of` → s8 → 翌月の月次シム の順に実行し、どれかが失敗したら終了コード 1 で中断する

## 保証
- s4 の as-of（月以前だけで判定・出力先・`as_of` 記録・atomic・冪等・形式検証）→ `tests/test_s4_ban_build.py`
- s3 は自動で Ban を拾わず、明示指定は適用 → `tests/test_s3_calc_positions.py`
- s8 の Ban 適用（as-of 有無・ファイル無し・全除外）→ `tests/test_s8_strategy_rank.py`
- backfill の s4→s8→シム順と中断 → `tests/test_s_monthly_backfill.py`
- 廃止: §18「S8→シム」の順序の保証を S4→S8→シムに置き換え（台帳を更新済み）

## 検証
- `PYTHONPATH=. pytest -q`: 195 passed
- 合成データで `bt.py all` が最後まで通り、`s4 --as-of` と `S8_AS_OF` の s8 も動作を確認

## 実データでの確認（マージ後に user が行う）
- 以前 Ban されて positions が無い候補があるので s3〜s7 を回し直す（計算時間の確認を含む）
- `rank/all/snapshots/` と `monthly/` は先読みを含むので消してから `bt.py monthly-backfill` を回し直す

## 確認者の判定
| 項目 | 判定 |
|---|---|
| `pytest -q` が全件通る | 合 |
| 合成データで `bt.py all` が通り、通常の Ban ができる | 合 |
| `s4 --as-of` で `ban/asof/<YYYY-MM>/entry_ban_all.yaml` ができる | 合 |
| テストの期待値の出し直し（s3 / s4 / s8 / backfill） | 合 |
| 保証節の各項目と台帳（§11・§12・§16・§18） | 合 |

---

## Ban の判定を as-of 時点のデータに限り、適用を s8 に移す
id: 01
branch-slug: ban-as-of
status: close
type: fix
対象: core/s3_calc_positions.py, core/s4_ban_build.py, core/s8_strategy_rank.py, core/s_monthly_backfill.py, tests/test_s3_calc_positions.py, tests/test_s4_ban_build.py, tests/test_s8_strategy_rank.py, tests/test_s_monthly_backfill.py, docs/guarantees.md
内容: いまは s4 が直近N月で作った Ban を s3 が最新ファイルとして自動で拾い、全期間の候補から消している。backfill で過去月のスナップショットを作るときにも未来の月で決めた Ban が適用され、選抜手順のウォークフォワード評価が先読みで汚れる。Ban を「その月末時点までのデータだけで作り、選抜の時点（s8）で適用する」形に変え、backfill の各月が当時知り得た情報だけで選ばれるようにする。
対象外: Jaccard 重複排除の残し方（走査順で先の候補を残す）の変更。順位指標の変更（02）。選抜の当たり具合の集計（03）。s5〜s7 の計算対象の絞り込みによる高速化。
仮定: Ban された候補も s5〜s7 で計算する（s4 の判定に要る s3 は元から全候補を計算しているので、増えるのは s5〜s7 の計算量だけ）。計算量の増加は許容する。s3 の `--ban-file` / `S3_BAN_FILE` の明示指定は計算を省きたいときの手段として残す。
確認: `PYTHONPATH=. pytest -q` が全件通る（pandas/pyarrow が無ければ CLAUDE.md の nix-shell 経由）。合成データで `python3 examples/sample/generate_data.py` → `DRIP_SIM_DATA=<一時ディレクトリ> python3 bt.py all` が最後まで通り、`ban/` に通常の Ban が、`python3 core/s4_ban_build.py --as-of <YYYY-MM>` で `ban/asof/<YYYY-MM>/entry_ban_all.yaml` ができる。
人が見るもの: 実データでの再計算。以前 Ban されて positions が無い候補があるので s3〜s7 を回し直す（計算時間の確認を含む）。既存の `rank/all/snapshots/` と `monthly/` は先読みを含むうえ上書きされないので、消してから `bt.py monthly-backfill` を回し直す。

---

### 保証
- 新たに宣言する保証:
  - s4 は `--as-of YYYY-MM` を受け取ると、その月以前の parquet だけから直近 `--months` 件を選んで Ban を判定し、`ban/asof/<YYYY-MM>/entry_ban_all.yaml` に書く。as-of より後の月の positions は判定に使わない
  - s4 の as-of 出力は atomic に書き、同じ as-of で再実行すると上書きする（冪等）。出力 YAML に `as_of` を記録する
  - s4 は `--as-of` 無しなら従来どおり `ban/entry_ban_all_<timestamp>.yaml` を書く
  - s3 は Ban ファイルを自動では拾わない。`--ban-file` / `S3_BAN_FILE` を明示したときだけ Ban を適用する
  - s8 は as-of 指定時に `ban/asof/<as_of>/entry_ban_all.yaml` を、as-of 無しなら `ban/` の最新の `entry_ban_all_*.yaml` を読み、Ban された候補を DD フィルタ・ランキングの対象から外す。Ban ファイルが無ければ誰も外さず、その旨を表示する
  - backfill は対象月ごとに s4（as-of）→ s8（as-of）→ 翌月の月次シム の順に実行し、どれかが失敗した時点で終了コード 1 で中断する
- 維持する保証（docs/guarantees.md から）:
  - §11 s3: `_load_ban_set` の解析・欠損時の空集合、`run(args)` が明示された Ban 集合を反映して `positions/` を書くこと
  - §12 s4: rate Ban（low_rate / high_rate / no_data）、jaccard_dedup、dry-run は書かない、parquet / positions 無しのメッセージ、atomic write
  - §16 s8: DD フィルタ、`min_sig_per_hour`、as-of はスナップショットだけを書き最新ランクを変えないこと
  - §18 backfill: 月の並びと連続性、失敗時の中断
- 廃止する保証:
  - §18「`run(args)` は対象月ごとにS8（ランキング更新）→ 月次シム、の順で連続実行する」→ 上の s4→s8→シム の順に置き換える。`test_run_invokes_s8_then_sim_for_each_month` は s4 も含めた順序を確かめる形に書き換える

### core/s4_ban_build.py
- `--as-of YYYY-MM` を足す。`_list_recent_parquet` に渡す前に、`year=YYYY/MM.parquet` の (year, month) が as-of 以下のものに絞る
- 出力先は as-of 有りなら `ban/asof/<YYYY-MM>/entry_ban_all.yaml`、無しなら従来のタイムスタンプ付きファイル

### core/s3_calc_positions.py
- `run` の Ban 自動解決（250〜259 行付近、`ban/` の最新ファイルを拾う部分）を外す。明示指定の経路は残す
- `--ban-file` の help から「default: ban/の最新ファイルを自動解決」を外す

### core/s8_strategy_rank.py
- Ban ファイルを読む処理は s3 の `_load_ban_set` と同じ形式（`entries` の `id`/`slug`）。s8 は core 同士の import をしていないので、読み込みは s8 内に持つか `lib/` に切り出すかを実行者が決める（`lib/` に出すなら対象ファイルとテストが増えるので、その場合は s8 内に持つ）
- 外した件数を表示する（例: `s8: ban excluded=<n> (<path>)`）

### core/s_monthly_backfill.py
- S8 の前に `s4_ban_build.py --as-of <snap_month>` をサブプロセスで実行する。失敗したら中断する
