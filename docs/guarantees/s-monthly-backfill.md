# s-monthly-backfill

| 保証 | 対応テスト |
|---|---|
| `_months_to_backfill(n)` は `n` か月分の `YYYY-MM` を古い順に返す | `test_months_to_backfill_length_and_ordering` |
| `_months_to_backfill(n)` が返す月は連続している | `test_months_to_backfill_consecutive` |
| `run` は、対象月 M ごとに S4（`--as-of M`）→ S8（`S8_AS_OF=M`）→ 月次シム（`SIM_MONTH` は M の翌月）の順に実行する | `test_run_invokes_s4_s8_then_sim_for_each_month` |
| `run` は、S4 が失敗するとその時点で終了コード `1` で止まり、S8・月次シムを実行しない | `test_run_aborts_on_s4_failure` |
| `run` は、S8 が失敗するとその時点で終了コード `1` で止まり、月次シムを実行しない | `test_run_aborts_on_s8_failure` |
| `run` は、月次シムが失敗するとその時点で終了コード `1` で止まる | `test_run_aborts_on_sim_failure` |
