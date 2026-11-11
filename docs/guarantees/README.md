# Guarantee Ledger

このリポが外へ約束している振る舞いと、それを守るテストの一覧である。約束が破れればテストが落ちるので、
ここに書いたことは気づかないうちに実装とずれていかない。**ここに載っていない振る舞いは約束ではなく、予告なく変わりうる**。
対象は `lib/`・`core/`・`bt.py` の関数と CLI、書き出すファイル（parquet・yaml・csv）の列と値である。外から観測できない内部の処理は、テストが直接呼んでいても対象外とする。[docs/design-decisions.md](../design-decisions.md) と同格の文書である。

- 目的: いま何を約束しているかを1か所で読む。変更の前に、破ってはいけない約束をここから引く。テストの無い約束を Gaps に残す
- 分け方: 約束の対象（`lib/` のモジュール・`core/` の stage・`bt.py` の CLI）ごとに1ファイル。テストファイルや Issue の単位では分けない。新しい対象を作ったときだけファイルを足す
- 書き方: 各ファイルに「保証｜対応テスト」の表を1つ置き、1行に約束を1つ、宣言文で書く。表の行が約束の全文で、表の外に本文を書かない。出典・経緯・設計の理由は書かない（`docs/design-decisions.md` が持つ）。対話メニューの見た目と、手で確かめる操作は載せない。約束が10行以上のファイルは、内容のまとまりで `##` の見出しを立て、見出しごとに3行以上の表を置く（ファイルは分けない）。10行未満のファイルは見出しを置かない。見出しは行の主語になる名詞句にする。同じ名前のテストが別のファイルにもあれば、置き場を添える
- 引き方: 変更の前に、その対象のファイルを開いて守る約束を読む。テストが落ちたら、テストの名前で台帳を検索すると、破れた約束の行が見つかる。約束が守られていることは、全テストを流す CI が確かめる
- 運用: 変更の前にこの README を読み、変更が触れるファイルから Issue の「維持する保証」を引く。約束を足す・変える・消すときは、承認を受けた文のまま該当するファイルの表に行を足す・直す・消し、対応テストも同じ変更で直す。Issue や作業ごとにファイルや節を起こさない。テストの無い約束は Gaps に書き、テストを足したら表へ移す

## Files

| 約束の対象 |
|---|
| [env-paths](env-paths.md) |
| [yaml-loader](yaml-loader.md) |
| [grid](grid.md) |
| [feature-registry](feature-registry.md) |
| [session-util](session-util.md) |
| [cli-common](cli-common.md) |
| [features](features.md) |
| [generated-strategy](generated-strategy.md) |
| [s1-enrich-parquet](s1-enrich-parquet.md) |
| [s2-gen-strategies](s2-gen-strategies.md) |
| [s3-calc-positions](s3-calc-positions.md) |
| [s4-ban-build](s4-ban-build.md) |
| [s5-position-engine](s5-position-engine.md) |
| [s6-position-pips](s6-position-pips.md) |
| [s7-position-summary](s7-position-summary.md) |
| [s8-strategy-rank](s8-strategy-rank.md) |
| [s-monthly-sim](s-monthly-sim.md) |
| [s-monthly-backfill](s-monthly-backfill.md) |
| [s-selection-eval](s-selection-eval.md) |
| [bt-cli](bt-cli.md) |

## Gaps

- `get_import_root()` が `DRIP_SIM_DATA` の影響を受けないこと。テストは `DRIP_SIM_DATA` を設定せずに呼んでいる
- `add_trading_args` が、`spread=True`・`eod=True` を渡さなければ `--spread-pips`・`--eod-utc` を足さないこと。テストが見ている属性名は `spread`・`eod` で、実際の `spread_pips`・`eod_utc` が足されていても通る
- `compute_all` が、`import/feature_registry.yaml` の `precompute` に無いキーを返さないこと。テストは registry の一覧が出力に含まれることだけを確かめている
- `prev_day_high_low` が、前日の無い最初の日の `prev_day_low_1`・`prev_day_high_5`・`prev_day_low_5` を `NaN` にすること。テストは `prev_day_high_1` だけを確かめている
- S1c の `main` が、`--year` を指定するとその年のファイルだけを処理すること。テスト（`test_main_year_filter_processes_only_matching_year`）は処理したファイルの数だけを見ていて、どの年かは見ていない
- S3 の `_add_session_column` が、`NYC` の時間帯に `NYC` を入れること。テストは `TYO`・`LON` だけである
- S3 の `_jobs` が、未指定と数値でない値のときに CPU 数を返すこと。テストは1以上であることだけを見ている
- S3 の `run` が `entry_interval` の設定を反映すること。`run` のテストはどれも `entry_interval=0` である
- S3 の `run` が、環境変数 `S3_BAN_FILE` で指定した Ban ファイルを適用すること。テストは引数の `ban_file` だけである
- S4 の `_jaccard_dedup` が、類似度がちょうど閾値のペアも重複とすること。テストの類似度は閾値を上回る値だけである
- S4 の `run` が、`jaccard_dedup` を `min_rate`〜`max_rate` に収まる戦略同士にだけ当てること。テストには、率で Ban される戦略と重複する戦略を同時に置いた場合が無い
- S5 の `_build_positions` が、`entry_flag` の立ったバーの次のバーで建てること。テストは建てたバーの時刻と価格を見ていない
- S5・S6 の `_iv` が、数値として読めない設定値に既定値を返すこと。テストは `_fv` の場合だけである
- S7 の `run` が四半期・年次の CSV に書く `pips_avg_per_entry`・`bars5m_total`・`entry_rate`、年次の `entries_total`、四半期の `pips_sum_total` の値。テストが値を見ているのは、四半期の `entries_total`・`pips_sq_sum_total` と、年次の `pips_sum_total`・`pips_sq_sum_total` だけである
- S8 の `run` が直近 `rank_months` か月だけを集計すること。テストは `rank_months=999` などで全期間を含めている
- S8 の `run` が、`recovery_months` が `recovery_months_max` を超える戦略を `dd_filtered.csv` へ回すこと。テストで落ちる戦略は `recovery_factor` だけで落ちている
- 月次シムの `_target_months` が、`sim_month` が空のとき先月までの12か月を返すこと。テストは件数と並び順しか見ていない
- 月次シムの `run` が、前月のスナップショットが無い月に何も書かないこと。テストはメッセージしか確かめていない
- `_months_to_backfill(n)` が直近の `n` か月を返すこと。テストは件数・並び順・連続性しか見ていない
- `bt eval` が、データが無いとき終了コード `0` で終わること。テストは表示と、何も書かないことしか確かめていない
- `_result_entries` が `monthly/<YYYY-MM>` を新しい順に並べること。テストの `monthly/` は1件だけである
- `_last_run_text` の `updated N days ago` の N が経過日数の切り捨てであること。テストは経過がちょうど3日の場合だけである
