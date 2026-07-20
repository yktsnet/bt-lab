"""
rsi_zone - RSI が中立から離れた領域での反転

詳細思想は SPEC.md を参照。
"""
import pandas as pd
import numpy as np

KIND = "rsi_zone"
CATEGORY = "oscillator"
DESCRIPTION = "RSI が中立から離れた領域での反転"

PARAMS_GRID = {
    "rsi_period": [14, 21],
    "distance_from_mid": [20, 25, 30],
}


def required_features(params: dict) -> list[str]:
    return [f"rsi{params['rsi_period']}"]


def apply_indicators(df, params: dict):
    return df


def apply_entry_flag(df, params: dict):
    df["entry_flag"] = False
    df["buy_sell"] = pd.NA
    df["trend_dir"] = pd.NA

    rsi_period = params["rsi_period"]
    distance = params["distance_from_mid"]
    v = df[f"rsi{rsi_period}"]
    upper = 50 + distance
    lower = 50 - distance

    sell = v >= upper
    buy = v <= lower

    df.loc[sell, "entry_flag"] = True
    df.loc[sell, "buy_sell"] = "SELL"
    df.loc[sell, "trend_dir"] = "UP"

    df.loc[buy, "entry_flag"] = True
    df.loc[buy, "buy_sell"] = "BUY"
    df.loc[buy, "trend_dir"] = "DOWN"

    return df
