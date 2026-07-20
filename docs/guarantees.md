# Guarantee Ledger

## Guarantees

### 1. `tests/test_env_paths.py` — lib/env_paths.py (get_backtest_data_root / get_bt_data_root / get_parquet_root / get_strategies_root / get_logs_root / get_import_root / ensure_dirs)

- `get_backtest_data_root()` は `BACKTEST_DATA_ROOT` 環境変数が未設定の場合、既定値 `~/bt_data/backtest` を返す
- `get_backtest_data_root()` は `BACKTEST_DATA_ROOT` が設定されていればその値をそのまま返す
- `get_backtest_data_root()` は `BACKTEST_DATA_ROOT` が空白文字のみの場合も既定値にフォールバックする
- `get_bt_data_root()`/`get_parquet_root()`/`get_strategies_root()`/`get_logs_root()` は、それぞれ `BACKTEST_DATA_ROOT` 配下の `bt_data`/`parquet_data`/`strategies`/`logs` を返す
- `get_import_root()` はリポジトリルート直下の `import/` ディレクトリを返す（`BACKTEST_DATA_ROOT` に依存しない）
- `ensure_dirs()` はルート自身と `bt_data`/`parquet_data`/`strategies`/`logs` の全ディレクトリを作成する

| 保証（要約） | 対応テスト |
|---|---|
| 既定値へのフォールバック | `test_default_data_root_is_under_home` |
| 環境変数オーバーライド | `test_env_override` |
| 空白のみの環境変数は既定値扱い | `test_env_whitespace_only_falls_back_to_default` |
| 派生パスの構成 | `test_derived_paths_compose_under_data_root` |
| `import/` ルートの固定 | `test_import_root_is_repo_import_dir` |
| 全ディレクトリの作成 | `test_ensure_dirs_creates_all` |

### 2. `tests/test_yaml_loader.py` — lib/yaml_loader.py (load_yaml)

- 有効なYAMLファイルを読むと、その内容をPythonオブジェクト（辞書・リスト）として返す
- 空ファイルを読むと `None` を返す

| 保証（要約） | 対応テスト |
|---|---|
| マッピングの読み込み | `test_load_yaml_reads_mapping` |
| 空ファイルは `None` | `test_load_yaml_empty_file_returns_none` |

*（区切り内は `load_yaml` 一つだけなので主語を繰り返さない）*

### 3. `tests/test_grid.py` — lib/grid.py (expand_param_grid)

- 空の辞書を渡すと、空辞書1件だけのリストを返す
- スカラー値のみの辞書を渡すと、そのままの値を持つ辞書1件のリストを返す（展開されずラップされるだけ）
- リスト値を含む場合、全リスト値の直積（カルテシアン積）を辞書のリストとして返す
- スカラーとリストが混在する場合、スカラーは全組み合わせで固定値のまま保持され、リスト値のみ展開される

| 保証（要約） | 対応テスト |
|---|---|
| 空グリッド | `test_empty_params_returns_single_empty_dict` |
| スカラーのみはラップ | `test_scalar_values_are_wrapped_as_single_option` |
| 直積展開 | `test_cartesian_product_of_list_values` |
| スカラー/リスト混在 | `test_mixed_scalar_and_list_values` |

### 4. `tests/test_feature_registry.py` — lib/feature_registry.py (load_feature_registry / available_feature_names / precompute_specs)

- `load_feature_registry(path)` は `precompute`/`runtime_only` のいずれかが欠けていても、欠けたキーを空リストで補って返す
- `available_feature_names(path)` は `precompute` と `runtime_only` 両セクションの特徴量名を統合した集合を返す
- `available_feature_names(path)` は空文字列の `name` を無視する
- `available_feature_names(path)` は要素が辞書形式（`name:` キー付き）と素の文字列リスト形式のどちらでも同じ結果を返す
- `precompute_specs(path)` は `precompute` セクションの各行を、`name` 以外のフィールド（例: `period`）を含めた生の辞書のまま返す

| 保証（要約） | 対応テスト |
|---|---|
| 欠損セクションの補完 | `test_load_feature_registry_fills_missing_sections` |
| 両セクションの名前の和集合 | `test_available_feature_names_union_of_both_sections` |
| 空名の無視 | `test_available_feature_names_ignores_blank_names` |
| 素の文字列リスト形式も受理 | `test_available_feature_names_accepts_plain_string_list` |
| 生の行データを保持 | `test_precompute_specs_returns_raw_rows` |

### 5. `tests/test_session_util.py` — lib/session_util.py (decide_session / normalize_session_label / is_own)

- `decide_session(t, params)` は `SESS_TYO`/`SESS_LON`/`SESS_NYC` の時間帯定義に基づき、対象時刻が属するセッション名（`"TYO"`/`"LON"`/`"NYC"`）を返す
- `decide_session(t, params)` はセッション範囲の開始境界を含む（inclusive）
- `decide_session(t, params)` はいずれの範囲にも属さない時刻に対して空文字列を返す
- `normalize_session_label(label)` は `"LDN"` を `"LON"` に正規化し、他のラベルはそのまま返す
- `is_own(label, own)` は正規化後のラベルが一致すれば `1`、しなければ `0` を返す

| 保証（要約） | 対応テスト |
|---|---|
| セッション判定（TYO/NYC） | `test_decide_session_tyo`, `test_decide_session_nyc` |
| 開始境界を含む | `test_decide_session_lon_boundary_inclusive_start` |
| 非該当は空文字列 | `test_decide_session_outside_all_ranges_returns_empty` |
| LDN→LON正規化 | `test_normalize_session_label_maps_ldn_to_lon` |
| is_own の一致判定 | `test_is_own_matches_after_normalization` |

### 6. `tests/test_cli_common.py` — lib/cli_common.py (add_trading_args / apply_env_overrides)

- `add_trading_args(parser)` は `--tp-pips`/`--sl-pips`/`--pip-size`/`--max-entries`/`--abn-burst-pips`/`--abn-forward-block-bars` を追加し、未指定時のデフォルトは全て `None` になる
- `add_trading_args(parser, spread=True, lot=True, eod=True)` を指定したときのみ `--spread-pips`/`--lot`/`--eod-utc` が追加される（デフォルトでは存在しない属性になる）
- `apply_env_overrides(env, args)` はCLIで指定された引数のみ対応する環境変数名（例: `RR_TP_PIPS`）を上書きし、指定されていない既存の環境変数はそのまま残す
- `apply_env_overrides(env, args)` は渡された `env` 辞書を直接変更せず、常に新しい辞書を返す

| 保証（要約） | 対応テスト |
|---|---|
| 共通トレーディング引数のデフォルト | `test_add_trading_args_defaults_are_none` |
| オプション引数はフラグ指定時のみ追加 | `test_optional_args_only_added_when_enabled` |
| CLI指定分のみ環境変数を上書き | `test_apply_env_overrides_only_sets_provided_flags` |
| 元の辞書は不変・コピーを返す | `test_apply_env_overrides_with_no_cli_args_returns_copy_of_env` |

### 7. `tests/test_features.py` — lib/features.py (rsi / ema / sma / atr / bb_upper・bb_lower・bb_bandwidth / stoch_k・stoch_d / macd_hist / donchian_upper・donchian_lower / zabs / supertrend / vortex_plus・vortex_minus / ha_close・ha_open / adx・di_plus・di_minus / pivot_points / prev_day_high_low / compute_all)

- `rsi(df, period)` は価格が一定（値動きが無い）とき、平均下落がゼロになり全区間が `NaN` になる
- `rsi(df, period)` は一度だけの小さな下落を除き値上がりが継続する場合、終端値が90超になる
- `ema(df, span)` は `pandas.Series.ewm(span=span, adjust=False).mean()` と同一の値を返す
- `sma(df, period)` は指定期間の単純移動平均で、`period-1` 個目までは `NaN` になる
- `atr(df, period)` は非ゼロのレンジがある限り常に非負の値を返す
- `bb_upper`/`bb_lower(df, period, k)` は有効な区間で常に upper >= lower であり、`bb_bandwidth` は常に非負になる
- `stoch_k(df, period)` は常に0〜100の範囲に収まる
- `stoch_d(df, period, smooth)` は `stoch_k` の指定期間の単純移動平均と一致する
- `macd_hist(df, fast, slow, signal)` は価格が完全にフラットな場合、ほぼゼロ（`1e-6` 未満）になる
- `donchian_upper`/`donchian_lower(df, period)` は有効な区間で常に upper >= lower になる
- `zabs(df, period)` は常に非負の値を返す
- `supertrend(df, period, mult)` の状態列は `1.0` または `-1.0` のいずれかの値のみを取る
- `vortex_plus`/`vortex_minus(df, period)` はいずれも入力と同じ長さの系列を返す
- `ha_close(df)` は `(open+high+low+close)/4` と一致する
- `ha_open(df)` の先頭値は最初のバーの `(open+close)/2` と一致する
- `adx`/`di_plus`/`di_minus(df, period)` はいずれも常に非負の値を返す
- `pivot_points(df)` は `pivot_p`/`pivot_r1`/`pivot_s1`/`pivot_r2`/`pivot_s2` の5キーを返し、前日データが無い最初の日は `pivot_p` が全て `NaN` になる
- `prev_day_high_low(df)` は `prev_day_high_1`/`prev_day_low_1`/`prev_day_high_5`/`prev_day_low_5` の4キーを返し、前日データが無い最初の日は `NaN` になる
- `compute_all(df)` は返す全キーについて、入力と同じ長さかつ `float32` 型の系列を返す
- `compute_all(df)` が返すキー集合は、`import/feature_registry.yaml` の `precompute` 一覧を過不足なくカバーする
- `compute_all(df)` は `time_utc` 列が無い入力に対して、日次特徴量（`pivot_p`/`prev_day_high_1` 等）を除外し、それ以外（`rsi14` 等）は計算する
- `compute_all(df)` が返す全キーは、インジケータ名+パラメータのスネーク記法（`[a-z][a-z0-9_]*`）の列命名規則（conventions.md）に従う

| 保証（要約） | 対応テスト |
|---|---|
| RSI: 値動き無しはNaN | `test_rsi_constant_price_is_nan_due_to_zero_avg_loss` |
| RSI: 上昇継続で高値 | `test_rsi_mostly_gains_with_one_small_loss_is_high` |
| EMA: ewm定義と一致 | `test_ema_matches_pandas_ewm_definition` |
| SMA: rolling mean | `test_sma_rolling_mean_with_min_periods` |
| ATR: 非負 | `test_atr_positive_for_nonzero_ranges` |
| Bollinger: upper>=lower・bandwidth非負 | `test_bollinger_bands_upper_above_lower_and_bandwidth_nonnegative` |
| StochK: 0-100範囲 | `test_stoch_k_bounded_between_0_and_100` |
| StochD: StochKの移動平均 | `test_stoch_d_is_rolling_mean_of_stoch_k` |
| MACD hist: フラット価格でゼロ | `test_macd_hist_zero_when_flat_price` |
| Donchian: upper>=lower | `test_donchian_upper_lower_track_rolling_extremes` |
| zabs: 非負 | `test_zabs_is_nonnegative` |
| Supertrend: 状態は±1のみ | `test_supertrend_state_is_1_or_minus_1` |
| Vortex: 長さ一致 | `test_vortex_plus_minus_have_expected_columns_shape` |
| HA close: OHLC平均 | `test_ha_close_is_average_of_ohlc` |
| HA open: 先頭値の定義 | `test_ha_open_first_value_is_average_of_first_open_close` |
| ADX/DI: 非負 | `test_adx_di_returns_nonnegative_series` |
| Pivot points: キー集合・初日NaN | `test_pivot_points_uses_previous_day_ohlc` |
| 前日高安: キー集合・初日NaN | `test_prev_day_high_low_shifts_by_one_day` |
| compute_all: float32・長さ一致 | `test_compute_all_returns_float32_series_for_every_key` |
| compute_all: registryとの整合 | `test_compute_all_covers_every_precompute_feature_in_registry` |
| compute_all: time_utc無しは日次特徴量除外 | `test_compute_all_without_time_utc_skips_daily_features` |
| compute_all: 全キーがスネーク記法 | `test_compute_all_keys_follow_snake_case_naming_convention` |

*（区切り内に多数の特徴量関数が混在するため、行ごとに関数名を明示する）*

### 8. `tests/test_generated_strategy.py` — lib/generated_strategy.py (apply_kind_strategy)

- `gt`/`lt` 演算子は、指定した閾値との大小関係で `entry_flag`（0/1）と `buy_sell`/`side`（`"BUY"`/`"SELL"`/空文字列）を設定する
- `cross_up` 演算子は、左辺が右辺を下から上に抜けた時点でのみ `entry_flag` を立てる
- `right` に `"{param_name}"` 形式の文字列を指定すると、`params` 辞書の値でフォーマットされてから比較に使われる
- `left`/`right` が既存の列名でも定数でもない場合、`sma_N` パターンの列名として動的に `close` のN期間単純移動平均を計算して比較に使う
- 未知の `op` を指定すると `ValueError` を送出する

| 保証（要約） | 対応テスト |
|---|---|
| gt/lt演算子とentry_flag/side | `test_gt_condition_sets_entry_flag_and_side`, `test_lt_condition_sell_side` |
| cross_up検出 | `test_cross_up_detects_transition` |
| パラメータ文字列フォーマット | `test_params_format_string_is_applied_to_right_operand` |
| 動的sma特徴量解決 | `test_dynamic_sma_feature_resolution` |
| 未知演算子はValueError | `test_unknown_op_raises_value_error` |

*（区切り内は `apply_kind_strategy` 一つだけなので主語を繰り返さない）*

### 9. `tests/test_s1_enrich_parquet.py` — core/s1_enrich_parquet.py (_load_parquet / _enrich_file / main)

- `_load_parquet(path)` は `close` 列が無いファイルを読み込むと `None` を返し、「missing close column」を含むメッセージを表示する
- `_enrich_file(path)` は欠けている特徴量列を計算して書き込み、追加した列数を返す
- `_enrich_file(path)` は既に全特徴量が存在するファイルに対して何も追加せず、追加列数として `0` を返す（冪等）
- `_enrich_file(path)` は `time_utc` 列が整数ミリ秒（Unixタイム）で保存されていても日時型に変換してから処理する
- `main(args)` は `--year` を指定すると、その年のディレクトリ（`year=YYYY/`）のファイルのみを処理する
- `main(args)` は `--year` を指定しない場合、全年のファイルを処理する
- `_enrich_file(path)` の書き込みは `.tmp` へ書いてから `os.replace` する手順を踏むため、書き込み中に例外が起きても元のファイルは壊れた状態で残らない（atomic write契約, conventions.md）

| 保証（要約） | 対応テスト |
|---|---|
| close列欠損はスキップ | `test_load_parquet_skips_files_missing_close_column` |
| 欠損特徴量列の追加 | `test_enrich_file_adds_missing_feature_columns` |
| 冪等性 | `test_enrich_file_is_idempotent` |
| int ms time_utcの変換 | `test_enrich_file_converts_int_ms_time_utc` |
| `--year`指定で対象年のみ処理 | `test_main_year_filter_processes_only_matching_year` |
| `--year`未指定で全年処理 | `test_main_default_processes_all_years` |
| 書き込み失敗時の元ファイルの保全 | `test_enrich_file_write_failure_leaves_original_file_untouched` |

### 10. `tests/test_s2_gen_strategies.py` — core/s2_gen_strategies.py (_expand_grid / _make_slug / _vstr / main)

- `_expand_grid(params)` はパラメータグリッドの直積（カルテシアン積）を辞書のリストとして展開する
- `_make_slug(params)` はキーをソートした順に整形し、スラグ文字列を生成する
- `_vstr(value)` は浮動小数点数を末尾の `0` を除いた表記に変換し（例: `2.0`→`"2p0"`、`1.25`→`"1p25"`）、整数はそのまま文字列化する
- `main()` は `strategies_md/<kind>/template.py` の `PARAMS_GRID` を展開し、組み合わせごとに `strategies/<kind>/<slug>.py` を生成する。生成物には `SLUG`/`PARAMS` が書き込まれる
- `main()` は同じ入力で再実行しても既存ファイルを再生成しない（`created=0`/`kept=N`/`updated=0`/`deleted=0`）
- `main()` は生成対象から外れたファイル（手動で置かれたものを含む）を削除する
- `main()` は必要な特徴量が `feature_registry.yaml` に無い組み合わせを全てスキップし、生成しない
- `main()` のファイル更新は `.tmp` へ書いてから `os.replace` する手順を踏むため、書き込み中に例外が起きても既存の戦略ファイルは壊れた状態で残らない（atomic write契約, conventions.md）

| 保証（要約） | 対応テスト |
|---|---|
| グリッドの直積展開 | `test_expand_grid_cartesian_product` |
| スラグ生成（キーソート＋浮動小数整形） | `test_make_slug_sorts_keys_and_formats_floats` |
| 浮動小数の文字列表現 | `test_vstr_formats_float_without_trailing_zeros` |
| 組み合わせごとのファイル生成 | `test_main_generates_one_file_per_grid_combo` |
| 再実行は冪等（全件keep） | `test_main_second_run_keeps_everything` |
| 対象外ファイルの削除 | `test_main_deletes_stray_files_not_in_desired_set` |
| 特徴量不足はスキップ | `test_main_skips_combos_with_missing_required_features` |
| 書き込み失敗時の既存ファイルの保全 | `test_main_write_failure_leaves_existing_strategy_file_untouched` |

### 11. `tests/test_s3_calc_positions.py` — core/s3_calc_positions.py (_filter_recent_months / _load_ban_set / _add_session_column / _out_path・_parse_year_month / _jobs / _process_strategy_month / run)

- `_filter_recent_months(files, n)` は月次ファイル一覧の末尾から直近 `n` 件のみを返す（`n` が総数以上ならそのまま全件返す）
- `_load_ban_set(path)` はファイルが存在しない場合、空集合を返し「not found」を含むメッセージを表示する
- `_load_ban_set(None)`/`_load_ban_set("")` は空集合を返す
- `_load_ban_set(path)` はban yamlの `entries` 各行を `id`（または `tid`）と `slug` のペアとして読み込み、`slug` が無い行は無視する
- `_add_session_column(df)` は `time_utc` 列が無い場合、`session` 列を空文字列で埋める
- `_add_session_column(df)` は `time_utc` の時刻に応じて `session` 列に `"TYO"`/`"LON"`/`"NYC"` を割り当てる
- `_out_path(root, kind, slug, year, month)` は `<root>/<kind>/<slug>/year=<year>/<month>.parquet` の形式でパスを組み立て、`_parse_year_month(path)` はその逆変換（`year`/`month` の整数タプル）を行う
- `_jobs(raw)` は `"auto"`・未指定・数値文字列をそれぞれ解釈し、数値以外の文字列（`ENTRY_JOBS`の不正値）が来た場合もクラッシュせずCPU数にフォールバックする
- `_process_strategy_month(...)` は戦略を適用した結果から `entry_flag` が立った行のみを出力ファイルに書き込む
- `_process_strategy_month(...)` は `entry_interval_min` を指定すると、その分刻みに一致する時刻のバーのみを残す
- `_process_strategy_month(...)` は出力ファイルが入力より新しい場合、再計算をスキップする（`False` を返す）
- `_process_strategy_month(...)` は実在する `strategies_md/oscillator/rsi_zone/template.py` から生成された戦略ファイルに対しても、`apply_entry_flag` の3カラム契約（`entry_flag`/`buy_sell`/`trend_dir`、conventions.md記載）を満たす出力を書き込む
- `run(args)` はban集合や`entry_interval`設定を反映しつつ、対象月・戦略ごとに `positions/<kind>/<slug>/year=<year>/<month>.parquet` を書き出す

| 保証（要約） | 対応テスト |
|---|---|
| 直近N件のフィルタ | `test_filter_recent_months_keeps_last_n` |
| ban未検出は空集合 | `test_load_ban_set_missing_file_returns_empty` |
| パス未指定は空集合 | `test_load_ban_set_no_path_returns_empty` |
| banエントリの解析 | `test_load_ban_set_parses_entries` |
| session列: time_utc無しは空文字列 | `test_add_session_column_without_time_utc_is_empty_string` |
| session列: 時刻に応じた割当 | `test_add_session_column_assigns_expected_sessions` |
| 出力パスの往復変換 | `test_out_path_and_parse_year_month_roundtrip` |
| ENTRY_JOBSの解決とフォールバック | `test_jobs_auto_and_explicit_and_invalid` |
| entry_flag行のみ出力 | `test_process_strategy_month_writes_only_entry_flag_rows` |
| entry_interval_minでの分フィルタ | `test_process_strategy_month_entry_interval_filters_minutes` |
| 出力が新しい場合はスキップ | `test_process_strategy_month_skips_when_output_is_fresh` |
| 実物のrsi_zone templateの3カラム契約 | `test_process_strategy_month_honors_real_rsi_zone_template_contract` |
| end-to-endでpositions/を生成 | `test_run_end_to_end_writes_positions` |

### 12. `tests/test_s4_ban_build.py` — core/s4_ban_build.py (_jaccard / _jaccard_dedup / _parse_year_month / _bars_in_window / run)

- `_jaccard(a, b)` は両方空集合なら `1.0`、片方だけ空なら `0.0`、それ以外は通常のJaccard係数（積集合/和集合）を返す
- `_jaccard_dedup(sets, thr)` は類似度が閾値以上のペアのうち、後から出てきたキーを重複として除外する
- `_jaccard_dedup(sets, thr)` は閾値未満のペアは全て残す
- `_parse_year_month(path)` は `year=YYYY/MM.parquet` 形式のパスから `(year, month)` の整数タプルを取り出す
- `_bars_in_window(path)` はUTC 0:00〜17:00の範囲内にあるバー数を数える
- `_bars_in_window(path)` はファイルが存在しない場合、`0` を返す
- `run(...)` はエントリー率が `min_rate` を下回る戦略を `reason: low_rate` としてban yamlに書き出し、正常な戦略はbanしない
- `run(...)` はエントリー率が `max_rate` を超える戦略を `reason: high_rate` としてban yamlに書き出す
- `run(...)` は対象月のバー数が0（`_bars_in_window`が0を返すケース）の戦略を `reason: no_data` としてban yamlに書き出す
- `run(...)` は `min_rate`〜`max_rate` に収まる戦略同士を対象に `_jaccard_dedup` を適用し、除外された戦略を `reason: jaccard_dedup` としてban yamlに書き出す
- `run(..., dry_run=True)` はban yamlファイルを書き出さない
- `run(...)` はparquetファイルが1つも無い場合、「no parquet files found」を含むメッセージを表示する
- `run(...)` は `positions/` ディレクトリが無い場合、「positions/ not found」を含むメッセージを表示する
- `run(...)` のban yaml書き込みは一時ファイル→`os.replace`の手順を踏むため、書き込み中に例外が起きても既存のban出力（実際の出力パス）は壊れた状態で残らない（atomic write契約, conventions.md）

| 保証（要約） | 対応テスト |
|---|---|
| Jaccard係数の基本ケース | `test_jaccard_both_empty_is_1`, `test_jaccard_one_empty_is_0`, `test_jaccard_partial_overlap` |
| 重複除外（閾値以上） | `test_jaccard_dedup_removes_near_duplicate_later_key` |
| 重複除外（閾値未満は全残し） | `test_jaccard_dedup_below_threshold_keeps_all` |
| year/monthパースの逆変換 | `test_parse_year_month` |
| 時間窓のバー数集計 | `test_bars_in_window_counts_hours_in_range` |
| ファイル無しは0 | `test_bars_in_window_missing_file_returns_zero` |
| low_rateのban | `test_run_bans_low_rate_strategy_and_keeps_normal_one` |
| high_rateのban | `test_run_bans_high_rate_strategy` |
| no_dataのban | `test_run_bans_no_data_strategy_when_bars_in_window_is_zero` |
| jaccard_dedupのban（end-to-end） | `test_run_jaccard_dedup_bans_near_duplicate_strategy` |
| dry-runは書き出さない | `test_run_dry_run_does_not_write_ban_file` |
| parquet無しのメッセージ | `test_run_no_parquet_files_prints_message` |
| positions/無しのメッセージ | `test_run_no_positions_dir_prints_message` |
| 書き込み失敗時の既存出力の保全 | `test_run_write_failure_leaves_existing_ban_output_untouched` |

### 13. `tests/test_s5_position_engine.py` — core/s5_position_engine.py (_hm / _fv・_iv / _build_positions / _process_one / run)

- `_hm(value)` は `"HH:MM"` 形式・ISO日時（`T`区切り・空白区切りの両方）を分単位（0〜1439）に変換し、`None`/空文字列に対しては `None` を返す
- `_fv`/`_iv` は環境設定値が未設定または数値として解釈できない場合、デフォルト値にフォールバックする（クラッシュしない）
- `_build_positions(...)` は `entry_flag` が立った次のバーでポジション（pending order）を開き、BUYが `high >= entry+TP` に達すると `abnormal="TP"` でクローズする
- `_build_positions(...)` はSELLが `high >= entry+SL` に達すると `abnormal="SL"` でクローズする
- `_build_positions(...)` は `EOD_UTC` 到達時に未決済のポジションを強制的にクローズする（`abnormal="EOD"`）
- `_build_positions(...)` は直前の急変（`high-low` が `ABN_BURST_HL_PIPS` 以上）を検知すると、その後 `ABN_FORWARD_BLOCK_BARS` 本のエントリーをブロックする
- `_build_positions(...)` は `MAX_ENTRIES_PER_STRAT` を超えるオープンを行わない
- `_process_one(...)` は該当するparquetとsignalファイルが揃っている場合にのみ `"wrote"` を返し、`pos_events/<kind>/<slug>/year=<year>/<month>.parquet` を書き出す
- `_process_one(...)` は入力ファイルが見つからない場合、`"skipped"` を返す
- `run(args)` は全戦略・全月を処理し、`pos_events/` 配下にイベントファイルを書き出す

| 保証（要約） | 対応テスト |
|---|---|
| _hm: 時刻文字列の分単位変換 | `test_hm_parses_hhmm`, `test_hm_parses_iso_timestamp_with_t_separator`, `test_hm_parses_iso_timestamp_with_space_separator`, `test_hm_none_or_empty_returns_none` |
| _fv/_iv: フォールバック | `test_fv_iv_defaults_and_fallback` |
| pending open + TP | `test_build_positions_opens_then_hits_tp` |
| SL | `test_build_positions_hits_sl` |
| EOD強制クローズ | `test_build_positions_eod_forces_close` |
| スパーク後の順方向ブロック | `test_build_positions_spark_blocks_forward_entries` |
| 最大エントリー数の制限 | `test_build_positions_max_entries_per_strat_caps_opens` |
| イベントファイル書き込み | `test_process_one_writes_events_parquet` |
| 入力欠損はskipped | `test_process_one_skips_when_inputs_missing` |
| end-to-end実行 | `test_run_end_to_end` |

### 14. `tests/test_s6_position_pips.py` — core/s6_position_pips.py (_fv・_iv / _calc_pips / _process_one / run)

- `_fv`/`_iv` は環境設定値が未設定または数値として解釈できない場合、デフォルト値にフォールバックする（クラッシュしない）
- `_calc_pips(df, env)` はTP/SLでクローズした行に対し、固定pips（`RR_TP_PIPS`/`RR_SL_PIPS`）からスプレッド（`SPREAD_PIPS`）を差し引いた値を `pips_net` に書き込む
- `_calc_pips(df, env)` はTP/SL以外の理由（例: EOD/NET）でクローズした行に対し、`(close_price-entry)/PIP_SIZE` を売買方向（BUY/SELL）に応じた符号で計算する
- `_calc_pips(df, env)` は `close_price` が欠損している行に対し `pips_net` を `NaN` にする
- `_process_one(path, env)` は `pips_net` を計算してファイルに書き込み、`"wrote"` を返す
- `_process_one(path, env)` は `pips_net` が既に埋まっているファイルに対しては何もせず、`"skipped"` を返す
- `run(args)` は `pos_events/` 配下の全ファイルに対し `pips_net` 列を書き込む

| 保証（要約） | 対応テスト |
|---|---|
| _fv/_iv: フォールバック | `test_fv_iv_defaults_and_fallback` |
| TP/SLは固定pips-スプレッド | `test_calc_pips_tp_and_sl_use_fixed_pip_values` |
| その他理由は価格差から算出 | `test_calc_pips_other_reason_computed_from_price_delta` |
| 価格欠損はNaN | `test_calc_pips_missing_price_yields_nan` |
| pips_netの書き込み | `test_process_one_writes_pips_net_column` |
| 既存値がある場合はskipped | `test_process_one_skips_when_pips_net_already_populated` |
| end-to-end実行 | `test_run_end_to_end` |

### 15. `tests/test_s7_position_summary.py` — core/s7_position_summary.py (_r2 / _quarter / _bars_in_window / run)

- `_r2(value)` は小数第2位に四捨五入する
- `_r2(None)` は `None` をそのまま返す
- `_r2(nan)`/`_r2(inf)` は `None` に変換する
- `_quarter(month)` は月番号（1〜12）を四半期番号（1〜4）に変換する
- `_bars_in_window(path)` はEOD境界（UTC 17:00）より前のバー数を数える
- `run()` は `pos_events/` が存在しない場合、「pos_events/ not found」を含むメッセージを表示する
- `run()` は月次・四半期・年次のCSVを生成し、`entries_total`（open以外の件数）・`pips_sum_total`（`pips_net`合計）・`pips_avg_per_entry`（1件あたり平均）・`bars5m_total`（EOD前バー数）・`entry_rate`（`entries_total`/`bars5m_total`）を正しく集計する
- `run()` は `type` 列が無い、またはクローズ行が無いファイルをスキップし、「no records found」を含むメッセージを表示する

| 保証（要約） | 対応テスト |
|---|---|
| 四捨五入 | `test_r2_rounds_to_two_decimals` |
| Noneはそのまま | `test_r2_none_passthrough` |
| NaN/InfはNone | `test_r2_nan_and_inf_become_none` |
| 四半期マッピング | `test_quarter_mapping` |
| EOD前バー数の集計 | `test_bars_in_window_counts_hours_before_eod` |
| pos_events/無しのメッセージ | `test_run_no_pos_events_prints_message` |
| 月次/四半期/年次の集計値 | `test_run_produces_monthly_quarterly_yearly_csv_with_correct_aggregates` |
| 不正ファイルのスキップ | `test_run_skips_files_without_type_column_or_empty_close` |

### 16. `tests/test_s8_strategy_rank.py` — core/s8_strategy_rank.py (_dd_metrics / run)

- `_dd_metrics(pips)` は累積損益の推移からピークとの差（絶対ドローダウン `abs_dd`）を計算する
- `_dd_metrics(pips)` は `recovery_factor`（総利益 / `abs_dd`）を計算し、ドローダウンが無い場合は無限大を返す
- `_dd_metrics(pips)` は `recovery_months`（`abs_dd` / 利益月の平均利益）を計算し、利益月が無い場合は無限大を返す
- `run(args)` はサマリーディレクトリが存在しない場合、「Run s7 first」を含むメッセージを表示する
- `run(args)` は直近 `rank_months` 分の月次データを集計し、`recovery_factor`/`recovery_months` のフィルタ条件を満たさない戦略を `rank_by_pips_avg.csv` から除外し `dd_filtered.csv` に振り分ける
- `run(args)` は `min_sig_per_hour` 未満のエントリー頻度の戦略を除外する
- `run(args, as_of=...)` を指定すると `rank/all/rank_by_pips_avg.csv`（最新ランク）を変更せず、`rank/all/snapshots/<as_of>/` 配下にのみ結果を書き出す

| 保証（要約） | 対応テスト |
|---|---|
| 絶対ドローダウンの計算 | `test_dd_metrics_hand_calculated` |
| DD無しはrecovery_factor=inf | `test_dd_metrics_no_drawdown_gives_infinite_recovery_factor` |
| 利益月無しはrecovery_months=inf | `test_dd_metrics_no_profit_months_gives_infinite_recovery_months` |
| summary無しのメッセージ | `test_run_no_summary_dir_prints_message` |
| ランキングとDDフィルタ | `test_run_ranks_and_filters_by_recovery_factor` |
| 低頻度戦略の除外 | `test_run_min_sig_per_hour_excludes_low_frequency_strategies` |
| as-ofはsnapshotのみ更新 | `test_run_as_of_writes_snapshot_not_latest_rank` |

### 17. `tests/test_s_monthly_sim.py` — core/s_monthly_sim.py (_hm / trading_days_in_month / _target_months / _load_strategies_from_snapshot / _build_positions / run)

- `_hm(value)` は `"HH:MM"` 形式・ISO日時を分単位に変換し、`None` に対しては `None` を返す
- `trading_days_in_month(month)` は土日を除いた営業日の日付リストを返す
- `_target_months(sim_month)` は `sim_month` を明示指定すると、その1か月分だけを対象にする
- `_target_months("")` は指定が無い場合、直近12か月（先月まで）を対象にする
- `_load_strategies_from_snapshot(...)` はスナップショットのランクCSVから `min_avg` 以上の戦略のみを読み込み、対応する戦略ファイルが存在しない行は無視する
- `_load_strategies_from_snapshot(...)` はスナップショットが存在しない場合、空リストを返し「snapshot not found」を含むメッセージを表示する
- `_build_positions(rows, env)` はTP到達でクローズし、`pips_net` を正しく計算する
- `run(args)` はスナップショット対象の戦略ごとに日次CSV（`tid`/`slug`/`entries`/`pips_sum`/`pips_avg`列）を `monthly/<month>/ALL/` に書き出す
- `run(args)` は対象月にスナップショットが無い場合、「no snapshot for <month>」を含むメッセージを表示してスキップする
- `run(args)` の日次CSV書き込みは `.tmp` へ書いてから `os.replace` する手順を踏むため、書き込み中に例外が起きても壊れた出力ファイルが残らない（atomic write契約, conventions.md）

| 保証（要約） | 対応テスト |
|---|---|
| 時刻文字列の分単位変換 | `test_hm_parses_hhmm_and_iso` |
| 営業日（土日除外） | `test_trading_days_in_month_excludes_weekends` |
| 対象月の明示指定 | `test_target_months_explicit_sim_month` |
| 既定は直近12か月 | `test_target_months_default_returns_12_months_ending_last_month` |
| min_avgでの戦略フィルタ | `test_load_strategies_from_snapshot_filters_by_min_avg` |
| snapshot欠損時の挙動 | `test_load_strategies_from_snapshot_missing_snapshot_returns_empty` |
| TPクローズとpips_net | `test_build_positions_records_tp_close` |
| 日次CSVの書き出し | `test_run_writes_daily_csv_for_snapshot_strategies` |
| 書き込み失敗時に壊れた出力を残さない | `test_run_write_failure_does_not_leave_partial_daily_csv` |
| snapshot無しはスキップ | `test_run_skips_month_without_snapshot` |

### 18. `tests/test_s_monthly_backfill.py` — core/s_monthly_backfill.py (_months_to_backfill / run)

- `_months_to_backfill(n)` は直近 `n` か月分を昇順（古い→新しい）で返す
- `_months_to_backfill(n)` が返す月は連続している（前月の翌月が次の要素になる）
- `run(args)` は対象月ごとにS8（ランキング更新）→ 月次シム、の順で連続実行する
- `run(args)` はS8が失敗した月があれば、その時点で処理を中断する（終了コード1）
- `run(args)` は月次シムが失敗した場合も、その時点で処理を中断する（終了コード1。S8自体は成功済み）

| 保証（要約） | 対応テスト |
|---|---|
| 直近N か月・昇順 | `test_months_to_backfill_length_and_ordering` |
| 月の連続性 | `test_months_to_backfill_consecutive` |
| S8→sim の順で実行 | `test_run_invokes_s8_then_sim_for_each_month` |
| S8失敗で中断 | `test_run_aborts_on_s8_failure` |
| sim失敗で中断 | `test_run_aborts_on_sim_failure` |

### 19. `tests/test_bt_cli.py` — bt.py (STAGES・PIPELINE_ORDER・PHASES / main / _run_stage / _result_entries・_view_results / _last_run_text / _fzf_select)

- `STAGES` に登録された各サブコマンドは、対応する `core/` 配下のスクリプトファイルが実在する
- `PIPELINE_ORDER` は `["s1b","s1c","s2","s3","s4","s5","s6","s7","s8"]` の順で固定され、`STAGES` の部分集合になっている
- `PHASES`（`bt flow` のフェーズ分割）は `PIPELINE_ORDER` の各段を過不足なく分割する
- 引数無しで実行すると終了コード `0` で使い方（`"stages:"`を含む）を表示する
- 未知のサブコマンドを指定すると終了コード `2` で「unknown stage」を含むエラーを表示する
- `bt all` に追加引数を渡すと、転送されない旨のエラーとともに終了コード `2` を返す
- `bt all` は最初に失敗した段でパイプライン全体を中断する
- `bt flow` に追加引数を渡すと終了コード `2` を返す
- `bt flow` で `q` を選ぶと即座に何も実行せず終了コード `0` で終わる
- `bt flow` は無効な選択肢に対して「Invalid choice」を表示し、再度選択を促す
- `bt flow` はフェーズ確認で `n` と答えるとそのフェーズをスキップし「Skipped.」を表示する
- `bt flow` はフェーズを選んで `y` と答えると、そのフェーズに属する段を順番に実行する
- `bt flow` の Position engineフェーズは実行前にTP/SL(pips)の入力を促し、`--tp-pips`/`--sl-pips` として転送する
- `bt flow` で結果ビューア（`v`）を選ぶと結果表示処理を呼び出す
- `_run_stage("s8", ...)` が成功すると、`rank/all/*.csv` を `rank/all/history/<timestamp>/` にコピーして履歴として残す
- `_run_stage("s8", ...)` が失敗すると履歴を残さない
- `s8` 以外の段が成功しても履歴を残さない
- `_result_entries()` は `rank/all`(最新)→履歴（新しい順）→`monthly/<month>` の順で結果一覧を返す
- `_view_results()` は結果が1件も無い場合、「no results found」を含むメッセージを表示する
- `_view_results()` は選択したCSVの内容を表示する
- `bt flow` はいずれかの段が失敗するとそのフェーズを中断し、「Phase failed」を表示してメニューに戻る
- 個別サブコマンド（例: `bt s5 --tp-pips 40 --sl-pips 15`）に渡した追加引数は、対応する `core/` スクリプトへそのまま転送される
- 追加引数が無い個別サブコマンドは、素のスクリプト呼び出しとして転送される
- `_last_run_text(dir)` はディレクトリが存在しない、または空の場合「never run」を返す
- `_last_run_text(dir)` は最新ファイルの更新時刻に応じて「updated today」/「updated N day(s) ago」を返す（複数ファイルがある場合は最新のものを基準にする）
- `_fzf_select(...)` は `fzf` がPATHに無い場合、`None` を返し「fzf not found」を含むエラーを表示する
- `_fzf_select(...)` は選択候補を改行区切りで `fzf` に渡し、`--prompt=<prompt>> ` を付与して起動する
- `_fzf_select(...)` は `fzf` が非0で終了した場合、`None` を返す
- `_fzf_select(...)` は選択結果が空文字列の場合、`None` を返す

| 保証（要約） | 対応テスト |
|---|---|
| STAGESのスクリプト実在性 | `test_stage_scripts_exist` |
| PIPELINE_ORDERの固定 | `test_pipeline_order_is_s1b_through_s8` |
| PHASESの網羅性 | `test_phases_cover_pipeline_order_exactly` |
| 引数無しはヘルプ表示 | `test_no_args_prints_help_and_exits_0` |
| 未知サブコマンドはexit 2 | `test_unknown_stage_exits_2` |
| all + 追加引数はexit 2 | `test_all_rejects_extra_args` |
| all は最初の失敗で中断 | `test_all_aborts_on_first_stage_failure` |
| flow + 追加引数はexit 2 | `test_flow_rejects_extra_args` |
| flowのq即終了 | `test_flow_quit_immediately_runs_nothing` |
| flowの無効選択 | `test_flow_invalid_choice_then_quit` |
| flowのn=スキップ | `test_flow_declining_confirmation_skips_phase` |
| flowのy=フェーズ実行 | `test_flow_runs_selected_phase_stages_in_order` |
| Position engineフェーズのTP/SL入力 | `test_flow_position_engine_phase_prompts_for_tp_sl` |
| flowの結果ビューア呼び出し | `test_flow_view_results_menu_entry` |
| s8成功後の履歴アーカイブ | `test_run_stage_archives_rank_output_after_s8_success` |
| s8失敗時は履歴を残さない | `test_run_stage_does_not_archive_on_s8_failure` |
| s8以外は履歴を残さない | `test_run_stage_does_not_archive_for_non_s8_stages` |
| 結果一覧の順序 | `test_result_entries_lists_latest_history_then_monthly` |
| 結果無しのメッセージ | `test_view_results_no_results_prints_message` |
| 選択CSVの表示 | `test_view_results_selects_and_prints_csv` |
| flowはフェーズ失敗で中断 | `test_flow_aborts_phase_on_stage_failure_and_returns_to_menu` |
| 追加引数のsubprocess転送 | `test_stage_dispatch_forwards_extra_args_to_subprocess` |
| 追加引数無しの転送 | `test_stage_dispatch_with_no_extra_args` |
| never run（ディレクトリ無し/空） | `test_last_run_text_never_run_for_missing_dir`, `test_last_run_text_never_run_for_empty_dir` |
| 更新日数の表示・最新ファイル基準 | `test_last_run_text_updated_today`, `test_last_run_text_updated_one_day_ago`, `test_last_run_text_updated_n_days_ago`, `test_last_run_text_uses_latest_file_among_many` |
| fzf未検出 | `test_fzf_select_not_found_in_path` |
| fzf起動引数 | `test_fzf_select_invokes_real_subprocess_with_expected_args` |
| fzf非0終了 | `test_fzf_select_returns_none_on_nonzero_exit` |
| fzf空選択 | `test_fzf_select_returns_none_on_empty_choice` |

*（区切り内に多数の関数が混在するため、行ごとに主語を明示する）*

## About

対象は `lib/`・`core/`・`bt.py` の公開関数・CLI・書き出しファイル（parquet/yaml/csv）のスキーマと値。対象外はテストが直接叩いていても外部から観測できない純粋な内部処理（例: `core/s3_calc_positions.py` の並列度自動判定のうち観測可能な副作用が無い部分）。**ここに載っていない振る舞いは約束ではなく、予告なく変わりうる。** 地位はdesign-decisions.md相当のドキュメントと同格。
