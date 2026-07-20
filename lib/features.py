"""
lib/features.py — 素材特徴量計算ライブラリ
- 全て右寄せ（t時点はt以前のデータのみ使用）
- 列名規約: インジケータ名+パラメータのスネーク記法
- 呼び出し元: core/s1_enrich_parquet.py
"""
import numpy as np
import pandas as pd


# ────────────────────────────────────────────
# RSI
# ────────────────────────────────────────────

def rsi(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: rsi{period}"""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).astype("float32")


# ────────────────────────────────────────────
# EMA / SMA
# ────────────────────────────────────────────

def ema(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: ema{period}"""
    return df["close"].ewm(span=period, adjust=False).mean().astype("float32")


def sma(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: sma{period}"""
    return df["close"].rolling(period, min_periods=period).mean().astype("float32")


# ────────────────────────────────────────────
# CCI
# ────────────────────────────────────────────

def cci(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: cci{period}"""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma = tp.rolling(period, min_periods=period).mean()
    md = tp.rolling(period, min_periods=period).apply(
        lambda x: np.mean(np.abs(x - x.mean())), raw=True
    )
    return ((tp - ma) / (0.015 * md.replace(0, np.nan))).astype("float32")


# ────────────────────────────────────────────
# Stochastic %K と %D
# ────────────────────────────────────────────

def stoch_k(df: pd.DataFrame, k_period: int) -> pd.Series:
    """列名: stoch_k{k_period}"""
    low_min = df["low"].rolling(k_period, min_periods=k_period).min()
    high_max = df["high"].rolling(k_period, min_periods=k_period).max()
    rng = (high_max - low_min).replace(0, np.nan)
    return ((df["close"] - low_min) / rng * 100).astype("float32")


def stoch_d(df: pd.DataFrame, k_period: int, d_period: int) -> pd.Series:
    """列名: stoch_d{k_period}_{d_period}"""
    k = stoch_k(df, k_period)
    return k.rolling(d_period, min_periods=d_period).mean().astype("float32")


# ────────────────────────────────────────────
# MACD histogram
# ────────────────────────────────────────────

def macd_hist(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.Series:
    """列名: macd_hist_{fast}_{slow}_{signal}"""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return (macd_line - signal_line).astype("float32")


# ────────────────────────────────────────────
# ATR
# ────────────────────────────────────────────

def atr(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: atr{period}"""
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean().astype("float32")


# ────────────────────────────────────────────
# Bollinger Bands
# ────────────────────────────────────────────

def bb_upper(df: pd.DataFrame, period: int, dev: float) -> pd.Series:
    """列名: bb_upper_{period}_{dev_str}  例: bb_upper_20_2p0"""
    ma = df["close"].rolling(period, min_periods=period).mean()
    std = df["close"].rolling(period, min_periods=period).std()
    return (ma + dev * std).astype("float32")


def bb_lower(df: pd.DataFrame, period: int, dev: float) -> pd.Series:
    """列名: bb_lower_{period}_{dev_str}"""
    ma = df["close"].rolling(period, min_periods=period).mean()
    std = df["close"].rolling(period, min_periods=period).std()
    return (ma - dev * std).astype("float32")


def bb_bandwidth(df: pd.DataFrame, period: int, dev: float) -> pd.Series:
    """列名: bb_bw_{period}_{dev_str}  (bandwidth = (upper-lower)/ma)"""
    ma = df["close"].rolling(period, min_periods=period).mean()
    std = df["close"].rolling(period, min_periods=period).std()
    upper = ma + dev * std
    lower = ma - dev * std
    return ((upper - lower) / ma.replace(0, np.nan)).astype("float32")


# ────────────────────────────────────────────
# Keltner Channel
# ────────────────────────────────────────────

def keltner_upper(df: pd.DataFrame, ema_period: int, atr_period: int, mult: float) -> pd.Series:
    """列名: kc_upper_{ema_period}_{atr_period}_{mult_str}"""
    mid = df["close"].ewm(span=ema_period, adjust=False).mean()
    at = atr(df, atr_period)
    return (mid + mult * at).astype("float32")


def keltner_lower(df: pd.DataFrame, ema_period: int, atr_period: int, mult: float) -> pd.Series:
    """列名: kc_lower_{ema_period}_{atr_period}_{mult_str}"""
    mid = df["close"].ewm(span=ema_period, adjust=False).mean()
    at = atr(df, atr_period)
    return (mid - mult * at).astype("float32")


# ────────────────────────────────────────────
# SuperTrend
# ────────────────────────────────────────────

def supertrend(df: pd.DataFrame, period: int, factor: float) -> pd.Series:
    """
    列名: st_state_{period}_{factor_str}
    値:  1=long, -1=short (float32)
    """
    at = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2
    upper_band = hl2 + factor * at
    lower_band = hl2 - factor * at

    close = df["close"].values
    n = len(close)
    ub = upper_band.values.copy()
    lb = lower_band.values.copy()
    direction = np.ones(n, dtype=np.float32)  # 1=long, -1=short

    for i in range(1, n):
        if np.isnan(ub[i]) or np.isnan(lb[i]):
            direction[i] = direction[i - 1]
            continue
        # adjust bands
        if lb[i] < lb[i - 1] or close[i - 1] < lb[i - 1]:
            lb[i] = lb[i]
        else:
            lb[i] = lb[i - 1]
        if ub[i] > ub[i - 1] or close[i - 1] > ub[i - 1]:
            ub[i] = ub[i]
        else:
            ub[i] = ub[i - 1]
        # direction
        if direction[i - 1] == -1 and close[i] > ub[i]:
            direction[i] = 1
        elif direction[i - 1] == 1 and close[i] < lb[i]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]

    return pd.Series(direction, index=df.index, dtype="float32")


# ────────────────────────────────────────────
# Vortex
# ────────────────────────────────────────────

def vortex_plus(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: vi_plus{period}"""
    vm_plus = (df["high"] - df["low"].shift(1)).abs()
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    vi = vm_plus.rolling(period, min_periods=period).sum() / \
         tr.rolling(period, min_periods=period).sum().replace(0, np.nan)
    return vi.astype("float32")


def vortex_minus(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: vi_minus{period}"""
    vm_minus = (df["low"] - df["high"].shift(1)).abs()
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    vi = vm_minus.rolling(period, min_periods=period).sum() / \
         tr.rolling(period, min_periods=period).sum().replace(0, np.nan)
    return vi.astype("float32")


# ────────────────────────────────────────────
# Z-score (absolute value)
# ────────────────────────────────────────────

def zabs(df: pd.DataFrame, window: int) -> pd.Series:
    """列名: zabs{window}"""
    m = df["close"].rolling(window, min_periods=window).mean()
    s = df["close"].rolling(window, min_periods=window).std()
    z = (df["close"] - m) / s.replace(0, np.nan)
    return z.abs().astype("float32")


# ────────────────────────────────────────────
# Donchian Channel
# ────────────────────────────────────────────

def donchian_upper(df: pd.DataFrame, lookback: int) -> pd.Series:
    """列名: dc_upper{lookback}"""
    return df["high"].rolling(lookback, min_periods=lookback).max().astype("float32")


def donchian_lower(df: pd.DataFrame, lookback: int) -> pd.Series:
    """列名: dc_lower{lookback}"""
    return df["low"].rolling(lookback, min_periods=lookback).min().astype("float32")


# ────────────────────────────────────────────
# Bollinger Band squeeze (bandwidth percentile)
# ────────────────────────────────────────────

def bb_bw_pct(df: pd.DataFrame, period: int, dev: float, window: int = 125) -> pd.Series:
    """
    列名: bb_bw_pct_{period}_{dev_str}
    bandwidth の直近 window 本における百分位 (0〜1)
    """
    bw = bb_bandwidth(df, period, dev)
    return bw.rolling(window, min_periods=window).rank(pct=True).astype("float32")


# ────────────────────────────────────────────
# Heikin-Ashi
# ────────────────────────────────────────────

def ha_close(df: pd.DataFrame) -> pd.Series:
    """列名: ha_close"""
    return ((df["open"] + df["high"] + df["low"] + df["close"]) / 4).astype("float32")


def ha_open(df: pd.DataFrame) -> pd.Series:
    """列名: ha_open  (再帰定義を近似: 前バーのHA open+close の平均)"""
    hc = ha_close(df).to_numpy()
    ho = np.empty(len(df), dtype=np.float32)
    ho[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2
    for i in range(1, len(df)):
        ho[i] = (ho[i - 1] + hc[i - 1]) / 2
    return pd.Series(ho, index=df.index, dtype="float32")


# ────────────────────────────────────────────
# Ichimoku
# ────────────────────────────────────────────

def _midpoint(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
    return (high.rolling(period).max() + low.rolling(period).min()) / 2


def ichimoku_tenkan(df: pd.DataFrame, tenkan: int) -> pd.Series:
    """列名: ichi_tenkan{tenkan}"""
    return _midpoint(df["high"], df["low"], tenkan).astype("float32")


def ichimoku_kijun(df: pd.DataFrame, kijun: int) -> pd.Series:
    """列名: ichi_kijun{kijun}"""
    return _midpoint(df["high"], df["low"], kijun).astype("float32")


def ichimoku_span_a(df: pd.DataFrame, tenkan: int, kijun: int) -> pd.Series:
    """列名: ichi_span_a_{tenkan}_{kijun}  (先行スパンA、シフトなし)"""
    t = ichimoku_tenkan(df, tenkan)
    k = ichimoku_kijun(df, kijun)
    return ((t + k) / 2).astype("float32")


def ichimoku_span_b(df: pd.DataFrame, span_b: int) -> pd.Series:
    """列名: ichi_span_b{span_b}  (先行スパンB、シフトなし)"""
    return _midpoint(df["high"], df["low"], span_b).astype("float32")


# ────────────────────────────────────────────
# SMA
# ────────────────────────────────────────────

# sma() は上で定義済み — compute_all() への追記のみ


# ────────────────────────────────────────────
# ADX / DI+ / DI-  (Wilder DMI)
# ────────────────────────────────────────────

def _dmi(df: pd.DataFrame, period: int):
    """(di_plus, di_minus, adx) を float32 Series で返す内部ヘルパ。"""
    prev_close = df["close"].shift(1)
    prev_high  = df["high"].shift(1)
    prev_low   = df["low"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)

    up   = df["high"] - prev_high
    down = prev_low   - df["low"]

    dm_plus  = pd.Series(
        np.where((up > down) & (up > 0), up, 0.0), index=df.index
    )
    dm_minus = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0), index=df.index
    )

    atr_w = tr.ewm(com=period - 1, adjust=False).mean()
    dip   = 100 * dm_plus.ewm(com=period - 1, adjust=False).mean() / atr_w.replace(0, np.nan)
    dim   = 100 * dm_minus.ewm(com=period - 1, adjust=False).mean() / atr_w.replace(0, np.nan)
    dx    = 100 * (dip - dim).abs() / (dip + dim).replace(0, np.nan)
    adx_v = dx.ewm(com=period - 1, adjust=False).mean()
    return dip.astype("float32"), dim.astype("float32"), adx_v.astype("float32")


def adx(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: adx{period}"""
    _, _, adx_v = _dmi(df, period)
    return adx_v


def di_plus(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: di_plus{period}"""
    dip, _, _ = _dmi(df, period)
    return dip


def di_minus(df: pd.DataFrame, period: int) -> pd.Series:
    """列名: di_minus{period}"""
    _, dim, _ = _dmi(df, period)
    return dim


# ────────────────────────────────────────────
# デイリーピボット (pivot_touch 向け)
# ────────────────────────────────────────────

def _prev_daily_ohlc(df: pd.DataFrame):
    """前日 H/L/C を各バーに対応させた (prev_h, prev_l, prev_c) numpy配列を返す。"""
    dates  = df["time_utc"].dt.date
    daily  = df.groupby(dates).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    prev   = daily.shift(1)
    idx    = dates.values
    return (
        prev["h"].reindex(idx).values.astype("float32"),
        prev["l"].reindex(idx).values.astype("float32"),
        prev["c"].reindex(idx).values.astype("float32"),
    )


def pivot_points(df: pd.DataFrame) -> dict:
    """
    Returns dict: pivot_p, pivot_r1, pivot_s1, pivot_r2, pivot_s2 (float32 Series)
    前日 H/L/C から当日全バーに固定値を付与。
    """
    ph, pl, pc = _prev_daily_ohlc(df)
    p = (ph + pl + pc) / 3
    return {
        "pivot_p":  pd.Series(p,             index=df.index, dtype="float32"),
        "pivot_r1": pd.Series(2 * p - pl,    index=df.index, dtype="float32"),
        "pivot_s1": pd.Series(2 * p - ph,    index=df.index, dtype="float32"),
        "pivot_r2": pd.Series(p + (ph - pl), index=df.index, dtype="float32"),
        "pivot_s2": pd.Series(p - (ph - pl), index=df.index, dtype="float32"),
    }


# ────────────────────────────────────────────
# 前日来高値/安値 (daily_high_break 向け)
# ────────────────────────────────────────────

def prev_day_high_low(df: pd.DataFrame) -> dict:
    """
    Returns dict: prev_day_high_1/5, prev_day_low_1/5 (float32 Series)
    前N日間の日次 H/L を各バーに付与。
    """
    dates = df["time_utc"].dt.date
    daily = df.groupby(dates).agg(h=("high", "max"), l=("low", "min"))
    idx   = dates.values
    result = {}
    for n in [1, 5]:
        rh = daily["h"].shift(1).rolling(n).max()
        rl = daily["l"].shift(1).rolling(n).min()
        result[f"prev_day_high_{n}"] = pd.Series(
            rh.reindex(idx).values.astype("float32"), index=df.index, dtype="float32"
        )
        result[f"prev_day_low_{n}"] = pd.Series(
            rl.reindex(idx).values.astype("float32"), index=df.index, dtype="float32"
        )
    return result


# ────────────────────────────────────────────
# ヘルパ: float値を列名用文字列に変換
# 例: 2.0 -> "2p0", 1.5 -> "1p5", 0.05 -> "0p05"
# ────────────────────────────────────────────

def _fstr(v: float) -> str:
    s = f"{v:.10f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s.replace(".", "p")


# ────────────────────────────────────────────
# 全特徴量を一括計算して返す
# T01〜T26 が必要とする全列を網羅
# ────────────────────────────────────────────

def compute_all(df: pd.DataFrame) -> dict:
    """
    全特徴量を計算し {列名: pd.Series} の dict を返す。
    s1_enrich_parquet.py から呼ばれる。
    """
    cols = {}

    # RSI: 8, 14, 21
    for p in [8, 14, 21]:
        cols[f"rsi{p}"] = rsi(df, p)

    # EMA: 9, 12, 18, 26, 34, 50, 100
    for p in [9, 12, 18, 26, 34, 50, 100]:
        cols[f"ema{p}"] = ema(df, p)

    # CCI: 14, 20, 30
    for p in [14, 20, 30]:
        cols[f"cci{p}"] = cci(df, p)

    # Stochastic %K: 9, 14, 21
    for k_p in [9, 14, 21]:
        cols[f"stoch_k{k_p}"] = stoch_k(df, k_p)

    # Stochastic %D: k=9/14/21 x d=3/5/7
    for k_p in [9, 14, 21]:
        for d_p in [3, 5, 7]:
            cols[f"stoch_d{k_p}_{d_p}"] = stoch_d(df, k_p, d_p)

    # MACD histogram: fast=12/16/20, slow=26/34/40, signal=9/12
    for fast, slow in [(12, 26), (16, 34), (20, 40)]:
        for sig in [9, 12]:
            cols[f"macd_hist_{fast}_{slow}_{sig}"] = macd_hist(df, fast, slow, sig)

    # ATR: 14, 21, 28, 30
    for p in [14, 21, 28, 30]:
        cols[f"atr{p}"] = atr(df, p)

    # Bollinger Bands: period=20/30, dev=1.5/2.0/2.5
    for p in [20, 30]:
        for d in [1.5, 2.0, 2.5]:
            ds = _fstr(d)
            cols[f"bb_upper_{p}_{ds}"] = bb_upper(df, p, d)
            cols[f"bb_lower_{p}_{ds}"] = bb_lower(df, p, d)
            cols[f"bb_bw_{p}_{ds}"]    = bb_bandwidth(df, p, d)

    # Keltner Channel: atr=14/30, mult=1.5/2.0/2.5 (ema_period=20固定)
    for atr_p in [14, 30]:
        for mult in [1.5, 2.0, 2.5]:
            ms = _fstr(mult)
            cols[f"kc_upper_20_{atr_p}_{ms}"] = keltner_upper(df, 20, atr_p, mult)
            cols[f"kc_lower_20_{atr_p}_{ms}"] = keltner_lower(df, 20, atr_p, mult)

    # SuperTrend state: period=7/10/14, factor=2.0/2.5/3.0
    for p in [7, 10, 14]:
        for f in [2.0, 2.5, 3.0]:
            fs = _fstr(f)
            cols[f"st_state_{p}_{fs}"] = supertrend(df, p, f)

    # Vortex: 7, 14, 21
    for p in [7, 14, 21]:
        cols[f"vi_plus{p}"]  = vortex_plus(df, p)
        cols[f"vi_minus{p}"] = vortex_minus(df, p)

    # Z-score abs: 20, 30, 60
    for w in [20, 30, 60]:
        cols[f"zabs{w}"] = zabs(df, w)

    # Donchian: 20, 55, 120, 240
    for lb in [20, 55, 120, 240]:
        cols[f"dc_upper{lb}"] = donchian_upper(df, lb)
        cols[f"dc_lower{lb}"] = donchian_lower(df, lb)

    # Heikin-Ashi
    cols["ha_close"] = ha_close(df)
    cols["ha_open"]  = ha_open(df)

    # Ichimoku: tenkan=7/9, kijun=22/26, span_b=44/52
    for tk in [7, 9]:
        cols[f"ichi_tenkan{tk}"] = ichimoku_tenkan(df, tk)
    for kj in [22, 26]:
        cols[f"ichi_kijun{kj}"] = ichimoku_kijun(df, kj)
    for tk, kj in [(7, 22), (9, 26)]:
        cols[f"ichi_span_a_{tk}_{kj}"] = ichimoku_span_a(df, tk, kj)
    for sb in [44, 52]:
        cols[f"ichi_span_b{sb}"] = ichimoku_span_b(df, sb)

    # SMA: 20, 50, 200
    for p in [20, 50, 200]:
        cols[f"sma{p}"] = sma(df, p)

    # ADX / DI+/DI-: 14, 21 (_dmi を1回呼んで3列まとめて生成)
    for p in [14, 21]:
        dip, dim, adx_v = _dmi(df, p)
        cols[f"adx{p}"]      = adx_v
        cols[f"di_plus{p}"]  = dip
        cols[f"di_minus{p}"] = dim

    # デイリーピボット / 前日来高値安値 (time_utc 必須)
    if "time_utc" in df.columns:
        cols.update(pivot_points(df))
        cols.update(prev_day_high_low(df))

    return cols
