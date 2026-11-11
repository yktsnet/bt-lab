## 引数を変えたら計算し直し、S6・月次シム・S1c の計算を S3〜S5 と registry に揃える
id: 04
branch-slug: rerun-and-calc-consistency
status: open
type: fix
対象: core/s3_calc_positions.py, core/s5_position_engine.py, core/s6_position_pips.py, core/s_monthly_sim.py, core/s1_enrich_parquet.py, tests/test_s3_calc_positions.py, tests/test_s5_position_engine.py, tests/test_s6_position_pips.py, tests/test_s_monthly_sim.py, tests/test_s1_enrich_parquet.py, docs/guarantees/s1-enrich-parquet.md, docs/guarantees/s3-calc-positions.md, docs/guarantees/s5-position-engine.md, docs/guarantees/s6-position-pips.md, docs/guarantees/s-monthly-sim.md, docs/overview.md
内容: 段ごとの計算が引数や他の段と食い違う4点を直す。(1) S3・S5・S6 が、引数を変えても既存の出力を飛ばして計算し直さない。(2) S6 が TP/SL で閉じた pips を価格ではなく引数から決めるので、S5 と違う値を渡すと pips が実際の値幅と合わない。(3) 月次シムが特徴量をその日のバーだけで計算し、S3 の30分間隔の絞り込みも掛けないため、S3〜S6 と同じ候補・同じ日でも結果が一致しない。(4) S1c が `lib/features.py` の `compute_all` の固定の一覧を焼き込み、`import/feature_registry.yaml` を読まない。README・conventions.md は registry を S1c の単一情報源と書いている。
対象外: 月をまたぐ特徴量のウォームアップ（S1c が月ごとのファイルで計算するため、月初のバーで RSI などが欠ける件）。S4・S7・S8 のスキップと再計算の扱い。月次シムの出力を eval で使うこと。`compute_all` が計算する特徴量の種類を増やす・減らすこと
仮定: 月次シムは消さずに S3〜S6 と同じ計算に揃える（eval が使っていないので消す案もある）。S1c は registry に従わせる側で直し、文書の記述は変えない。docs/overview.md は PR #17 のマージ後に main にある前提で書き換える
確認: `PYTHONPATH=. pytest -q` が通る。下の「新たに宣言する保証」がそれぞれテストで確かめられている。合成データ（`examples/sample/generate_data.py`）で `bt.py all` を流したあと、`bt.py s5 --tp-pips 40 --sl-pips 15` と `bt.py s6` を流すと `pos_events/` が書き直され、TP で閉じた行の `pips_net` が 40 − スプレッド（既定 0.3）= 39.7 になる
人が見るもの: なし

---

### 保証
- 新たに宣言する保証:
  - S3 は、出力が入力より新しくても、その出力を作ったときの `--entry-interval` と今回の値が違えば計算し直す。同じ値なら従来どおり飛ばす
  - S5 は、出力が入力より新しくても、その出力を作ったときの売買の引数（PIP_SIZE・TP・SL・ロット・同時保有上限・急変動の幅とブロック本数・EOD 時刻）のどれかが今回と違えば計算し直す。同じなら従来どおり飛ばす
  - S6 は、`pips_net` を付け終えたファイルでも、付けたときの PIP_SIZE・スプレッドと今回の値が違えば付け直す。同じなら従来どおり飛ばす
  - S6 は、TP・SL で閉じた行も、ほかの理由で閉じた行と同じく `close_price` と `entry` の差から pips を出す。TP/SL の引数は使わない。S5 を `--tp-pips 40` で流せば、S6 に引数を渡さなくても TP の行は 40 − スプレッドになる
  - 月次シムは、同じ戦略・同じ日・同じ売買の引数なら、S3（既定の30分間隔）→ S5 → S6 と同じエントリー件数と pips の合計を出す
  - 月次シムは、`buy_sell`（または `side`）が BUY・SELL でないバーではポジションを建てない（いまは BUY として建てる）
  - S1c は registry の `precompute` にある列だけを焼き込む。registry にあって `compute_all` が計算しない列があれば、その名前を出して失敗する
- 維持する保証（docs/guarantees/ から）:
  - s1-enrich-parquet.md（S1c）: close 列欠損のスキップ、欠損列の追加、冪等、int ms の `time_utc` の変換、`--year` の絞り込み、書き込み失敗時に元ファイルを壊さない
  - s3-calc-positions.md（S3）: 既存の各保証（直近 N か月の絞り込み、Ban ファイルの読み込み、セッション列、出力パス、30分間隔の絞り込み、`run` の通し）
  - s5-position-engine.md（S5）: TP・SL・EOD・急変動のブロック・同時保有上限・入力欠損は skipped・イベントファイルの書き出し
  - s6-position-pips.md（S6）: TP/SL 以外の理由は価格差から算出、価格欠損は NaN、`pips_net` の書き込み、同じ条件で付け終えたファイルは skipped
  - s-monthly-sim.md（月次シム）: 営業日、対象月、`min_avg` での絞り込み、スナップショット欠損時の挙動、日次 CSV の列と置き場、書き込み失敗時に壊れた出力を残さない、スナップショット無しの月を飛ばす
- 廃止する保証:
  - s6-position-pips.md「`_calc_pips` は TP/SL で閉じた行に、固定 pips（`RR_TP_PIPS`/`RR_SL_PIPS`）からスプレッドを引いた値を書く」。`test_calc_pips_tp_and_sl_use_fixed_pip_values` を、TP/SL の行も価格差から出すことを確かめるテストに書き換える

### core/s3_calc_positions.py・core/s5_position_engine.py・core/s6_position_pips.py

出力を作ったときの引数を出力と一緒に残し、次の実行で今回の引数と比べる。残し方（parquet のメタデータ、横に置く小さなファイルなど）は実行者が決めてよい。ただし次を守る。

- 引数を残していない既存の出力（この変更より前に作ったもの）は、引数が違うものとして計算し直す
- 書き込みは atomic（`.tmp` に書いてから `os.replace`）にする。S5・S6 の出力の書き込みは今は直接書いているので、ここで揃える
- S3 の引数で比べるのは `--entry-interval` だけでよい。`--months-limit`・`--ban-file`・`--jobs` は出力の中身を変えない（どの月・どの戦略を処理するかを変えるだけ）

S6 は `_calc_pips` の TP/SL の分岐をやめ、閉じた行はすべて `sign × (close_price − entry) / PIP_SIZE − SPREAD_PIPS` にする。S5 が TP/SL で閉じた行の `close_price` には TP/SL の価格が入っている（`_build_positions` の `cp`）。S6 の CLI から `--tp-pips`・`--sl-pips` を外すかは実行者が決めてよいが、残すなら使われないことを help に書く。

### core/s_monthly_sim.py

S3〜S6 と同じ計算になるよう、次の3点を揃える。S5 の `_build_positions` と S6 の pips の計算を呼んで使い、同じ処理を写さない。

- 特徴量は、日ごとの `compute_all` をやめ、S1c が焼き込んだ月の parquet の列を使う
- エントリーは S3 と同じく、分が `ENTRY_INTERVAL_MIN`（既定30）の倍数のバーだけを残す
- `buy_sell`（または `side`）が BUY・SELL でない行はエントリーにしない

日次 CSV の列（`tid`/`slug`/`entries`/`pips_sum`/`pips_avg`）と置き場は変えない。

### core/s1_enrich_parquet.py

`lib.feature_registry` で registry の `precompute` を読み、`compute_all` の結果からその列だけを足す。registry にあって `compute_all` に無い列があれば、名前を並べて失敗する（終了コード 0 以外）。いまは両者が一致しているので、焼き込む列は変わらない。

### docs/guarantees/

s1-enrich-parquet.md・s3-calc-positions.md・s5-position-engine.md・s6-position-pips.md・s-monthly-sim.md の表に、新たに宣言する保証と対応テストを足し、s6-position-pips.md の廃止する保証を書き換える。

### docs/overview.md

「S5 の建て方と閉じ方」の S6 の段落（TP/SL の pips を引数の値から決めるので S5 と S6 に同じ値を渡す）、「選抜が当たっているかを確かめる」の月次シムが S7 の数値と一致しないとする段落、「全体に共通する決まり」の「引数を変えてやり直すときは出力を消す」を、この変更後の事実に書き換える。
