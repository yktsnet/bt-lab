import numpy as np
import pandas as pd

from lib.generated_strategy import apply_kind_strategy


def _df():
    return pd.DataFrame({
        "close": [1.0, 2.0, 3.0, 2.0, 1.0, 4.0],
    })


def test_gt_condition_sets_entry_flag_and_side():
    spec = {"entry": {"left": "close", "op": "gt", "right": "2.0", "side": "buy"}}
    out = apply_kind_strategy(_df(), spec, {})
    assert list(out["entry_flag"]) == [0, 0, 1, 0, 0, 1]
    assert list(out["buy_sell"]) == ["", "", "BUY", "", "", "BUY"]
    assert list(out["side"]) == ["", "", "BUY", "", "", "BUY"]


def test_lt_condition_sell_side():
    spec = {"entry": {"left": "close", "op": "lt", "right": "2.0", "side": "SELL"}}
    out = apply_kind_strategy(_df(), spec, {})
    assert list(out["entry_flag"]) == [1, 0, 0, 0, 1, 0]
    assert list(out["buy_sell"]) == ["SELL", "", "", "", "SELL", ""]


def test_cross_up_detects_transition():
    df = pd.DataFrame({"close": [1.0, 1.0, 1.0, 1.0]})
    df["fast"] = [0.5, 1.5, 0.5, 2.0]
    spec = {"entry": {"left": "fast", "op": "cross_up", "right": "close", "side": "BUY"}}
    out = apply_kind_strategy(df, spec, {})
    # fast crosses above close(=1.0) at index1 (0.5->1.5) and index3 (0.5->2.0)
    assert list(out["entry_flag"]) == [0, 1, 0, 1]


def test_params_format_string_is_applied_to_right_operand():
    spec = {"entry": {"left": "close", "op": "gt", "right": "{thresh}", "side": "BUY"}}
    out = apply_kind_strategy(_df(), spec, {"thresh": "2.5"})
    assert list(out["entry_flag"]) == [0, 0, 1, 0, 0, 1]


def test_dynamic_sma_feature_resolution():
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]})
    spec = {"entry": {"left": "close", "op": "gt", "right": "sma_2", "side": "BUY"}}
    out = apply_kind_strategy(df, spec, {})
    # sma_2 = rolling mean of 2: [nan, 1.5, 2.5, 3.5, 4.5]; close > sma_2 -> True from idx1 on
    assert list(out["entry_flag"]) == [0, 1, 1, 1, 1]


def test_unknown_op_raises_value_error():
    df = _df()
    spec = {"entry": {"left": "close", "op": "bogus", "right": "1.0", "side": "BUY"}}
    import pytest
    with pytest.raises(ValueError):
        apply_kind_strategy(df, spec, {})
