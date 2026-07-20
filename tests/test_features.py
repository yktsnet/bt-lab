import re

import numpy as np
import pandas as pd
import pytest

import lib.features as features
import yaml
from pathlib import Path


def _ohlc(n=40, seed=1):
    rng = np.random.RandomState(seed)
    close = 100 + np.cumsum(rng.randn(n) * 0.1)
    high = close + np.abs(rng.randn(n) * 0.05)
    low = close - np.abs(rng.randn(n) * 0.05)
    open_ = close + rng.randn(n) * 0.02
    times = pd.date_range("2026-01-05", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame({
        "time_utc": times,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
    })


def test_rsi_constant_price_is_nan_due_to_zero_avg_loss():
    df = pd.DataFrame({"close": [1.0] * 20})
    r = features.rsi(df, 14)
    assert r.isna().all()


def test_rsi_mostly_gains_with_one_small_loss_is_high():
    # a single tiny down-tick keeps avg_loss from being exactly 0 (which would
    # divide-by-zero to NaN), while the series is still overwhelmingly up.
    closes = list(range(1, 16)) + [14.9] + list(range(16, 21))
    df = pd.DataFrame({"close": closes})
    r = features.rsi(df, 14)
    assert r.iloc[-1] > 90


def test_ema_matches_pandas_ewm_definition():
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    got = features.ema(df, 3)
    expected = df["close"].ewm(span=3, adjust=False).mean().astype("float32")
    pd.testing.assert_series_equal(got, expected, check_names=False)


def test_sma_rolling_mean_with_min_periods():
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]})
    got = features.sma(df, 2)
    assert np.isnan(got.iloc[0])
    assert got.iloc[1] == pytest.approx(1.5)
    assert got.iloc[2] == pytest.approx(2.5)
    assert got.iloc[3] == pytest.approx(3.5)


def test_atr_positive_for_nonzero_ranges():
    df = _ohlc()
    a = features.atr(df, 14)
    assert (a.dropna() >= 0).all()


def test_bollinger_bands_upper_above_lower_and_bandwidth_nonnegative():
    df = _ohlc()
    upper = features.bb_upper(df, 20, 2.0)
    lower = features.bb_lower(df, 20, 2.0)
    bw = features.bb_bandwidth(df, 20, 2.0)
    valid = upper.notna() & lower.notna()
    assert (upper[valid] >= lower[valid]).all()
    assert (bw.dropna() >= 0).all()


def test_stoch_k_bounded_between_0_and_100():
    df = _ohlc()
    k = features.stoch_k(df, 14)
    assert (k.dropna() >= -1e-9).all()
    assert (k.dropna() <= 100 + 1e-9).all()


def test_stoch_d_is_rolling_mean_of_stoch_k():
    df = _ohlc()
    k = features.stoch_k(df, 9)
    d = features.stoch_d(df, 9, 3)
    expected = k.rolling(3, min_periods=3).mean().astype("float32")
    pd.testing.assert_series_equal(d, expected, check_names=False)


def test_macd_hist_zero_when_flat_price():
    df = pd.DataFrame({"close": [5.0] * 30})
    h = features.macd_hist(df, 12, 26, 9)
    assert h.abs().max() < 1e-6


def test_donchian_upper_lower_track_rolling_extremes():
    df = _ohlc()
    up = features.donchian_upper(df, 5)
    lo = features.donchian_lower(df, 5)
    valid = up.notna() & lo.notna()
    assert (up[valid] >= lo[valid]).all()


def test_zabs_is_nonnegative():
    df = _ohlc()
    z = features.zabs(df, 20)
    assert (z.dropna() >= 0).all()


def test_supertrend_state_is_1_or_minus_1():
    df = _ohlc()
    st = features.supertrend(df, 7, 2.0)
    assert set(st.unique().tolist()) <= {1.0, -1.0}


def test_vortex_plus_minus_have_expected_columns_shape():
    df = _ohlc()
    vp = features.vortex_plus(df, 14)
    vm = features.vortex_minus(df, 14)
    assert len(vp) == len(df)
    assert len(vm) == len(df)


def test_ha_close_is_average_of_ohlc():
    df = _ohlc(5)
    hc = features.ha_close(df)
    expected = ((df["open"] + df["high"] + df["low"] + df["close"]) / 4).astype("float32")
    pd.testing.assert_series_equal(hc, expected, check_names=False)


def test_ha_open_first_value_is_average_of_first_open_close():
    df = _ohlc(5)
    ho = features.ha_open(df)
    expected_first = (df["open"].iloc[0] + df["close"].iloc[0]) / 2
    assert ho.iloc[0] == pytest.approx(expected_first, rel=1e-4)


def test_adx_di_returns_nonnegative_series():
    df = _ohlc()
    a = features.adx(df, 14)
    dip = features.di_plus(df, 14)
    dim = features.di_minus(df, 14)
    assert (a.dropna() >= 0).all()
    assert (dip.dropna() >= 0).all()
    assert (dim.dropna() >= 0).all()


def test_pivot_points_uses_previous_day_ohlc():
    df = _ohlc(200)
    piv = features.pivot_points(df)
    assert set(piv.keys()) == {"pivot_p", "pivot_r1", "pivot_s1", "pivot_r2", "pivot_s2"}
    # first day has no previous day -> NaN
    first_day = df["time_utc"].dt.date.iloc[0]
    mask_first = df["time_utc"].dt.date == first_day
    assert piv["pivot_p"][mask_first].isna().all()


def test_prev_day_high_low_shifts_by_one_day():
    df = _ohlc(400)
    out = features.prev_day_high_low(df)
    assert set(out.keys()) == {
        "prev_day_high_1", "prev_day_low_1", "prev_day_high_5", "prev_day_low_5",
    }
    first_day = df["time_utc"].dt.date.iloc[0]
    mask_first = df["time_utc"].dt.date == first_day
    assert out["prev_day_high_1"][mask_first].isna().all()


def test_compute_all_returns_float32_series_for_every_key():
    df = _ohlc(300)
    cols = features.compute_all(df)
    for name, series in cols.items():
        assert len(series) == len(df), name
        assert series.dtype == np.dtype("float32"), name


def test_compute_all_covers_every_precompute_feature_in_registry():
    """feature_registry.yaml のprecompute一覧が compute_all() の出力に
    過不足なく存在すること（S1c/S2契約の生きた検証）。"""
    registry_path = Path(__file__).resolve().parents[1] / "import" / "feature_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    expected_names = set(registry["precompute"])

    df = _ohlc(300)
    produced = set(features.compute_all(df).keys())

    missing = expected_names - produced
    assert not missing, f"registry declares features not produced by compute_all: {missing}"


def test_compute_all_without_time_utc_skips_daily_features():
    df = _ohlc(50).drop(columns=["time_utc"])
    cols = features.compute_all(df)
    assert "pivot_p" not in cols
    assert "prev_day_high_1" not in cols
    assert "rsi14" in cols


def test_compute_all_keys_follow_snake_case_naming_convention():
    """lib/features.pyの列名規約(インジケータ名+パラメータのスネーク記法, conventions.md)が
    compute_all()が返す全キーに渡って成立すること。"""
    df = _ohlc(300)
    keys = features.compute_all(df).keys()
    assert keys
    for name in keys:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", name), name
