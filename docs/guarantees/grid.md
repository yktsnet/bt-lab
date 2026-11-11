# grid

| 保証 | 対応テスト |
|---|---|
| `expand_param_grid` は、空の辞書に空の辞書1件だけのリストを返す | `test_empty_params_returns_single_empty_dict` |
| `expand_param_grid` は、スカラー値だけの辞書を展開せず、その辞書1件のリストを返す | `test_scalar_values_are_wrapped_as_single_option` |
| `expand_param_grid` は、リスト値の直積を辞書のリストとして返す | `test_cartesian_product_of_list_values` |
| `expand_param_grid` は、スカラーとリストが混在すると、スカラーを全組み合わせで同じ値のまま持ち、リスト値だけを展開する | `test_mixed_scalar_and_list_values` |
