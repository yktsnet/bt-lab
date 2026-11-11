# features

## オシレーターと移動平均

| 保証 | 対応テスト |
|---|---|
| `rsi(df, period)` は、価格が一定なら全区間 `NaN` を返す | `test_rsi_constant_price_is_nan_due_to_zero_avg_loss` |
| `rsi(df, period)` は、小さな下落1回を除いて値上がりが続くと、終端値が90を超える | `test_rsi_mostly_gains_with_one_small_loss_is_high` |
| `ema(df, span)` は `close.ewm(span=span, adjust=False).mean()` と同じ値を返す | `test_ema_matches_pandas_ewm_definition` |
| `sma(df, period)` は `close` の `period` 期間の単純移動平均を返し、値の揃わない先頭は `NaN` にする | `test_sma_rolling_mean_with_min_periods` |
| `stoch_k(df, period)` は0〜100の範囲に収まる | `test_stoch_k_bounded_between_0_and_100` |
| `stoch_d(df, period, smooth)` は `stoch_k` の `smooth` 期間の単純移動平均と一致する | `test_stoch_d_is_rolling_mean_of_stoch_k` |
| `macd_hist(df, fast, slow, signal)` は、価格が一定なら絶対値が `1e-6` 未満になる | `test_macd_hist_zero_when_flat_price` |

## 値幅とバンドの指標

| 保証 | 対応テスト |
|---|---|
| `atr(df, period)` は非負の値を返す | `test_atr_positive_for_nonzero_ranges` |
| `bb_upper`・`bb_lower(df, period, k)` は、両方に値のある区間で upper >= lower になる | `test_bollinger_bands_upper_above_lower_and_bandwidth_nonnegative` |
| `bb_bandwidth(df, period, k)` は非負の値を返す | `test_bollinger_bands_upper_above_lower_and_bandwidth_nonnegative` |
| `donchian_upper`・`donchian_lower(df, period)` は、両方に値のある区間で upper >= lower になる | `test_donchian_upper_lower_track_rolling_extremes` |
| `zabs(df, period)` は非負の値を返す | `test_zabs_is_nonnegative` |

## トレンドと平均足の指標

| 保証 | 対応テスト |
|---|---|
| `supertrend(df, period, mult)` の状態は `1.0` か `-1.0` だけを取る | `test_supertrend_state_is_1_or_minus_1` |
| `vortex_plus`・`vortex_minus(df, period)` は入力と同じ長さの系列を返す | `test_vortex_plus_minus_have_expected_columns_shape` |
| `ha_close(df)` は `(open + high + low + close) / 4` と一致する | `test_ha_close_is_average_of_ohlc` |
| `ha_open(df)` の先頭値は、最初のバーの `(open + close) / 2` と一致する | `test_ha_open_first_value_is_average_of_first_open_close` |
| `adx`・`di_plus`・`di_minus(df, period)` は非負の値を返す | `test_adx_di_returns_nonnegative_series` |

## 前日のデータから作る日次特徴量

| 保証 | 対応テスト |
|---|---|
| `pivot_points(df)` は `pivot_p`・`pivot_r1`・`pivot_s1`・`pivot_r2`・`pivot_s2` の5キーを返す | `test_pivot_points_uses_previous_day_ohlc` |
| `pivot_points(df)` は、前日の無い最初の日の `pivot_p` を `NaN` にする | `test_pivot_points_uses_previous_day_ohlc` |
| `prev_day_high_low(df)` は `prev_day_high_1`・`prev_day_low_1`・`prev_day_high_5`・`prev_day_low_5` の4キーを返す | `test_prev_day_high_low_shifts_by_one_day` |
| `prev_day_high_low(df)` は、前日の無い最初の日の `prev_day_high_1` を `NaN` にする | `test_prev_day_high_low_shifts_by_one_day` |

## `compute_all` の出力

| 保証 | 対応テスト |
|---|---|
| `compute_all(df)` は、どのキーにも入力と同じ長さの系列を返す | `test_compute_all_returns_float32_series_for_every_key` |
| `compute_all(df)` は、どのキーにも `float32` の系列を返す | `test_compute_all_returns_float32_series_for_every_key` |
| `compute_all(df)` は、`import/feature_registry.yaml` の `precompute` にある特徴量をすべて返す | `test_compute_all_covers_every_precompute_feature_in_registry` |
| `compute_all(df)` は、`time_utc` 列の無い入力には日次特徴量（`pivot_p`・`prev_day_high_1` など）を返さない | `test_compute_all_without_time_utc_skips_daily_features` |
| `compute_all(df)` は、`time_utc` 列の無い入力にも日次特徴量以外（`rsi14` など）を返す | `test_compute_all_without_time_utc_skips_daily_features` |
| `compute_all(df)` のキーは、どれも `[a-z][a-z0-9_]*` のスネーク記法である | `test_compute_all_keys_follow_snake_case_naming_convention` |
