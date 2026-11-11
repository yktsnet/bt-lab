# s1-enrich-parquet

## 特徴量列の焼き込み

| 保証 | 対応テスト |
|---|---|
| `_load_parquet` は、`close` 列が無いファイルに `None` を返す | `test_load_parquet_skips_files_missing_close_column` |
| `_load_parquet` は、`close` 列が無いファイルについて `missing close column` を含むメッセージを表示する | `test_load_parquet_skips_files_missing_close_column` |
| `_enrich_file` は、欠けている特徴量列を計算してファイルに書き込む | `test_enrich_file_adds_missing_feature_columns`, `test_enrich_file_adds_only_columns_listed_in_registry` |
| `_enrich_file` は、足した列数を返す | `test_enrich_file_adds_missing_feature_columns`, `test_enrich_file_adds_only_columns_listed_in_registry` |
| `_enrich_file` は、特徴量列がすべてあるファイルに何も足さず `0` を返す | `test_enrich_file_is_idempotent` |
| `_enrich_file` は、`time_utc` が整数ミリ秒で保存されていても日時に直してから計算する | `test_enrich_file_converts_int_ms_time_utc` |
| `_enrich_file` は、書き込み中に例外が起きても元のファイルを壊さない | `test_enrich_file_write_failure_leaves_original_file_untouched` |
| `main` は、`--year` を指定しなければ全年のファイルを処理する | `test_main_default_processes_all_years` |

## registry に載る列

| 保証 | 対応テスト |
|---|---|
| `_enrich_file` は、`import/feature_registry.yaml` の `precompute` にある列を焼き込む | `test_enrich_file_adds_only_columns_listed_in_registry` |
| `_enrich_file` は、`compute_all` が計算しても registry に無い列は足さない | `test_enrich_file_adds_only_columns_listed_in_registry` |
| `_enrich_file` は、registry の `precompute` に `compute_all` が計算しない列があると、その列名を並べたメッセージで `RegistryMismatch` を送出する | `test_enrich_file_fails_naming_registry_columns_compute_all_lacks` |
| `_enrich_file` は、`RegistryMismatch` を送出するときファイルを書き換えない | `test_enrich_file_fails_naming_registry_columns_compute_all_lacks` |
| `main` は、registry に `compute_all` が計算しない列があると、終了コード `0` 以外で終わる | `test_main_exits_nonzero_when_registry_has_unknown_column` |
| `main` は、registry に `compute_all` が計算しない列があると、その列名を標準エラーに出す | `test_main_exits_nonzero_when_registry_has_unknown_column` |
| リポに同梱の `import/feature_registry.yaml` の `precompute` の列は、すべて `compute_all` が計算する | `test_real_registry_columns_are_all_computed_by_compute_all` |
