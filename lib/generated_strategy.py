"""
generated_strategy.py
戦略ファイルから呼ばれる apply_kind_strategy の実装。
列が Parquet に存在しない場合、列名パターンから動的に計算する。
"""

from typing import Any
import re
import numpy as np
import pandas as pd


def _fmt(x: Any, params: dict):
    if isinstance(x, str):
        return x.format(**params)
    return x


def _compute_feature(df: pd.DataFrame, name: str) -> pd.Series:
    """
    列名パターンから特徴量を動的に計算する。
    sma_N       close の N 期間単純移動平均
    ema_N       close の N 期間指数移動平均
    zscore_N    close の N 期間 z スコア
    """
    # sma_N
    m = re.fullmatch(r"sma_(\d+)", name)
    if m:
        n = int(m.group(1))
        return df["close"].rolling(n, min_periods=n).mean()

    # ema_N
    m = re.fullmatch(r"ema_(\d+)", name)
    if m:
        n = int(m.group(1))
        return df["close"].ewm(span=n, adjust=False).mean()

    # zscore_N
    m = re.fullmatch(r"zscore_(\d+)", name)
    if m:
        n = int(m.group(1))
        ma = df["close"].rolling(n, min_periods=n).mean()
        std = df["close"].rolling(n, min_periods=n).std()
        return (df["close"] - ma) / std.replace(0, np.nan)

    return None


def _resolve(df: pd.DataFrame, x: Any, params: dict):
    x = _fmt(x, params)
    if not isinstance(x, str):
        return x
    # 列が存在すればそのまま返す
    if x in df.columns:
        return df[x]
    # 数値文字列（負数含む）
    try:
        return float(x)
    except (ValueError, TypeError):
        pass
    # 動的計算を試みる
    computed = _compute_feature(df, x)
    if computed is not None:
        return computed
    # 解決できなかった場合は列名文字列のまま返す（エラーを上位で検出）
    return x


def _cross_up(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a.shift(1) <= b.shift(1)) & (a > b)


def _cross_down(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a.shift(1) >= b.shift(1)) & (a < b)


def _compare(op: str, left: Any, right: Any) -> pd.Series:
    if op == "cross_up":
        return _cross_up(left, right)
    if op == "cross_down":
        return _cross_down(left, right)
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    raise ValueError(f"unknown op: {op}")


def apply_kind_strategy(df: pd.DataFrame, spec: dict, params: dict) -> pd.DataFrame:
    entry = spec["entry"]
    side = str(entry.get("side", "BUY")).upper()
    left = _resolve(df, entry["left"], params)
    right = _resolve(df, entry["right"], params)

    cond = pd.Series(_compare(entry["op"], left, right), index=df.index).fillna(False)
    out = df.copy()
    out["entry_flag"] = cond.astype(int)
    out["buy_sell"] = np.where(out["entry_flag"] == 1, side, "")
    out["side"] = np.where(out["entry_flag"] == 1, side, "")
    return out
