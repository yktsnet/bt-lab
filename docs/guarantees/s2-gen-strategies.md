# s2-gen-strategies

## パラメータの展開と slug（`_expand_grid`・`_make_slug`・`_vstr`）

| 保証 | 対応テスト |
|---|---|
| `_expand_grid` は、パラメータグリッドの直積を辞書のリストとして返す | `test_expand_grid_cartesian_product` |
| `_make_slug` は、キーをソートした順に並べて slug を作る | `test_make_slug_sorts_keys_and_formats_floats` |
| `_vstr` は、浮動小数点数の小数点を `p` に置き換えた文字列を返す（`2.0` → `"2p0"`、`1.25` → `"1p25"`） | `test_vstr_formats_float_without_trailing_zeros`, `test_make_slug_sorts_keys_and_formats_floats` |
| `_vstr` は、整数をそのまま文字列にする | `test_vstr_formats_float_without_trailing_zeros` |

## 戦略ファイルの生成（`main`）

| 保証 | 対応テスト |
|---|---|
| `main` は、`strategies_md/` の kind の `template.py` の `PARAMS_GRID` を展開し、組み合わせごとに `strategies/<kind>/<slug>.py` を生成する | `test_main_generates_one_file_per_grid_combo` |
| `main` は、生成したファイルに `SLUG` と `PARAMS` を書く | `test_main_generates_one_file_per_grid_combo` |
| `main` は、同じ入力で再実行すると既存のファイルを作り直さない（`created=0`・`kept=N`・`updated=0`・`deleted=0`） | `test_main_second_run_keeps_everything` |
| `main` は、生成対象から外れたファイル（手で置いたものを含む）を消す | `test_main_deletes_stray_files_not_in_desired_set` |
| `main` は、必要な特徴量が `feature_registry.yaml` に無い組み合わせを生成しない | `test_main_skips_combos_with_missing_required_features` |
| `main` は、書き込み中に例外が起きても既存の戦略ファイルを壊さない | `test_main_write_failure_leaves_existing_strategy_file_untouched` |
