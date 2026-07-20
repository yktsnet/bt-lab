"""共有CLI引数: TP/SL・ロット・EODなど売買パラメータの上書き用。

各ステージのrun()/main()はenv:dict（既存の_fv/_iv経由での読み出し）をそのまま使う。
このヘルパーはCLI引数をenv dictへの上書きに変換するだけで、計算ロジック側には
一切手を入れない。env var単体でもこれまで通り動く（CLI引数が最優先）。
"""
from __future__ import annotations

import argparse

_TRADING_ARGS = [
    ("--pip-size", "PIP_SIZE", float, "1pipsの価格幅"),
    ("--tp-pips", "RR_TP_PIPS", float, "利確pips"),
    ("--sl-pips", "RR_SL_PIPS", float, "損切pips"),
    ("--max-entries", "MAX_ENTRIES_PER_STRAT", int, "戦略あたり同時保有上限"),
    ("--abn-burst-pips", "ABN_BURST_HL_PIPS", float, "急変動とみなすhigh-low幅"),
    ("--abn-forward-block-bars", "ABN_FORWARD_BLOCK_BARS", int, "急変動後にエントリーを止めるバー数"),
]

_OPTIONAL_ARGS = {
    "spread": ("--spread-pips", "SPREAD_PIPS", float, "スプレッドpips"),
    "lot": ("--lot", "LOT_PER_ENTRY", float, "1エントリーのロット"),
    "eod": ("--eod-utc", "EOD_UTC", str, "強制決済時刻 UTC HH:MM"),
}


def _dest(flag: str) -> str:
    return flag.lstrip("-").replace("-", "_")


def add_trading_args(
    parser: argparse.ArgumentParser, *, spread: bool = False, lot: bool = False, eod: bool = False
) -> None:
    """TP/SL等の共通売買パラメータをCLI引数として追加する。未指定時はNoneのまま
    残り、env var（またはビルトインdefault）が使われる。"""
    for flag, env_key, typ, help_ in _TRADING_ARGS:
        parser.add_argument(flag, type=typ, default=None, help=f"{help_} (env: {env_key})")
    for name, enabled in (("spread", spread), ("lot", lot), ("eod", eod)):
        if enabled:
            flag, env_key, typ, help_ = _OPTIONAL_ARGS[name]
            parser.add_argument(flag, type=typ, default=None, help=f"{help_} (env: {env_key})")


def apply_env_overrides(env: dict, args: argparse.Namespace) -> dict:
    """argparseで指定されたフラグだけをenv dictに上書きした新しいdictを返す。"""
    env = dict(env)
    all_args = _TRADING_ARGS + list(_OPTIONAL_ARGS.values())
    for flag, env_key, _typ, _help in all_args:
        val = getattr(args, _dest(flag), None)
        if val is not None:
            env[env_key] = str(val)
    return env
