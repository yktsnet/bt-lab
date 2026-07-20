import argparse

import lib.cli_common as cli_common


def _parser(**kwargs):
    p = argparse.ArgumentParser()
    cli_common.add_trading_args(p, **kwargs)
    return p


def test_add_trading_args_defaults_are_none():
    p = _parser()
    args = p.parse_args([])
    assert args.tp_pips is None
    assert args.sl_pips is None
    assert args.pip_size is None
    assert args.max_entries is None
    assert args.abn_burst_pips is None
    assert args.abn_forward_block_bars is None


def test_optional_args_only_added_when_enabled():
    p = _parser()
    args = p.parse_args([])
    assert not hasattr(args, "spread")
    assert not hasattr(args, "lot")
    assert not hasattr(args, "eod")

    p2 = _parser(spread=True, lot=True, eod=True)
    args2 = p2.parse_args(["--spread-pips", "0.5", "--lot", "0.2", "--eod-utc", "16:30"])
    assert args2.spread_pips == 0.5
    assert args2.lot == 0.2
    assert args2.eod_utc == "16:30"


def test_apply_env_overrides_only_sets_provided_flags():
    p = _parser()
    args = p.parse_args(["--tp-pips", "40"])
    env = {"RR_SL_PIPS": "10"}
    out = cli_common.apply_env_overrides(env, args)
    assert out["RR_TP_PIPS"] == "40.0"
    assert out["RR_SL_PIPS"] == "10"  # untouched
    assert env == {"RR_SL_PIPS": "10"}  # original dict not mutated


def test_apply_env_overrides_with_no_cli_args_returns_copy_of_env():
    p = _parser()
    args = p.parse_args([])
    env = {"RR_TP_PIPS": "30"}
    out = cli_common.apply_env_overrides(env, args)
    assert out == env
    assert out is not env
