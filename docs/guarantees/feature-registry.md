# feature-registry

| 保証 | 対応テスト |
|---|---|
| `load_feature_registry(path)` は、`precompute`・`runtime_only` のどちらかが無ければ、無いキーを空リストで補って返す | `test_load_feature_registry_fills_missing_sections` |
| `available_feature_names(path)` は、`precompute` と `runtime_only` の特徴量名を合わせた集合を返す | `test_available_feature_names_union_of_both_sections` |
| `available_feature_names(path)` は、空文字列の `name` を無視する | `test_available_feature_names_ignores_blank_names` |
| `available_feature_names(path)` は、要素が素の文字列のリストも受け付ける | `test_available_feature_names_accepts_plain_string_list` |
| `precompute_specs(path)` は、`precompute` の各行を `name` 以外のフィールドも含めた辞書のまま返す | `test_precompute_specs_returns_raw_rows` |
