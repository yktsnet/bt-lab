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

