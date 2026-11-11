# generated-strategy

| 保証 | 対応テスト |
|---|---|
| `gt`・`lt` は、閾値との大小関係を満たすバーに `entry_flag=1` を立て、満たさないバーを `0` にする | `test_gt_condition_sets_entry_flag_and_side`, `test_lt_condition_sell_side` |
| エントリーするバーの `buy_sell`・`side` に `side` の指定（`BUY`/`SELL`）を書き、ほかのバーは空文字列にする | `test_gt_condition_sets_entry_flag_and_side`, `test_lt_condition_sell_side` |
| `cross_up` は、左辺が右辺を下から上へ抜けたバーにだけ `entry_flag` を立てる | `test_cross_up_detects_transition` |
| `right` が `"{param_name}"` 形式なら、`params` の値で埋めてから比べる | `test_params_format_string_is_applied_to_right_operand` |
| `left`・`right` が既存の列名でも定数でもなく `sma_N` の形なら、`close` の N 期間単純移動平均を計算して比べる | `test_dynamic_sma_feature_resolution` |
| 未知の `op` には `ValueError` を送出する | `test_unknown_op_raises_value_error` |
