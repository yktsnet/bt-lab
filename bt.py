#!/usr/bin/env python3
"""bt — backtestパイプラインの単一エントリーポイント。

各サブコマンドは core/ 配下の対応スクリプトをサブプロセスで起動し、
残りの引数はそのまま転送する（例: `bt s5 --tp-pips 40` は
`core/s5_position_engine.py --tp-pips 40` と等価）。個別スクリプトを
直接呼ぶ場合と挙動は変わらない。`bt <stage> --help` で各段の引数を確認できる。

使用例:
  bt s1b                    # JSONL → parquet
  bt s1c --year 2026        # parquetへ特徴量焼き込み
  bt s2                     # strategies_md → 戦略ファイル生成（冪等）
  bt s3 --months-limit 6
  bt s4 --dry-run
  bt s5 --tp-pips 40 --sl-pips 15
  bt s6
  bt s7
  bt s8 --rank-months 6 --rf-min 2.5
  bt monthly --month 2026-06
  bt monthly-backfill --months 6
  bt all                    # S1b〜S8を順に実行（env var設定のみ、引数転送なし）
  bt flow                   # 対話形式でフェーズを選んで実行（英語プロンプト）

zshの`bt`関数は引数無しで呼ばれると`bt flow`に読み替える（`zsh/bt.sh`）。
引数ありの呼び出しは従来通り直接dispatchするため、AIやスクリプトからの
非対話実行はこれまでと変わらない。
"""
from __future__ import annotations

import csv as csv_mod
import shutil
import subprocess
import sys
import time
from pathlib import Path

CORE = Path(__file__).resolve().parent / "core"

STAGES = {
    "s1b": "s1_export_parquet.py",
    "s1c": "s1_enrich_parquet.py",
    "s2": "s2_gen_strategies.py",
    "s3": "s3_calc_positions.py",
    "s4": "s4_ban_build.py",
    "s5": "s5_position_engine.py",
    "s6": "s6_position_pips.py",
    "s7": "s7_position_summary.py",
    "s8": "s8_strategy_rank.py",
    "monthly": "s_monthly_sim.py",
    "monthly-backfill": "s_monthly_backfill.py",
}

PIPELINE_ORDER = ["s1b", "s1c", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]

# 対話メニュー(`bt flow`)向けのフェーズ分割。使いやすさ・変更頻度で
# S1b〜S8をグルーピングしたもの。PIPELINE_ORDER自体は変えない。
PHASES: list[tuple[str, list[str]]] = [
    ("Data prep", ["s1b", "s1c"]),
    ("Strategy & entry", ["s2", "s3", "s4"]),
    ("Position engine", ["s5"]),
    ("Aggregate & rank", ["s6", "s7", "s8"]),
]


def _run_stage(name: str, extra_args: list[str]) -> int:
    script = CORE / STAGES[name]
    rc = subprocess.run([sys.executable, str(script), *extra_args]).returncode
    if rc == 0 and name == "s8":
        _archive_rank_output()
    return rc


def _archive_rank_output() -> None:
    """s8成功のたびにrank/all/*.csvを rank/all/history/<timestamp>/ へコピーして残す。
    s8自体は現在のrank/all/*.csvを上書きし続けるだけなので、履歴保持はここで行う
    （core/s8_strategy_rank.pyの計算・書き込みロジックには手を入れない）。"""
    from lib.env_paths import get_backtest_data_root

    rank_all = get_backtest_data_root() / "rank" / "all"
    csvs = [f for f in rank_all.glob("*.csv") if f.is_file()] if rank_all.exists() else []
    if not csvs:
        return
    dest = rank_all / "history" / time.strftime("%Y%m%d_%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    for f in csvs:
        shutil.copy2(f, dest / f.name)


def _print_help() -> None:
    print(__doc__)
    print("stages: " + ", ".join(STAGES) + ", all, flow")


def _phase_output_dir(index: int) -> Path:
    from lib.env_paths import get_backtest_data_root, get_parquet_root

    return [
        get_parquet_root(),
        get_backtest_data_root() / "positions",
        get_backtest_data_root() / "pos_events",
        get_backtest_data_root() / "rank",
    ][index]


def _last_run_text(path: Path) -> str:
    latest = None
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                mtime = f.stat().st_mtime
                if latest is None or mtime > latest:
                    latest = mtime
    if latest is None:
        return "never run"
    days = (time.time() - latest) / 86400
    if days < 1:
        return "updated today"
    if days < 2:
        return "updated 1 day ago"
    return f"updated {int(days)} days ago"


def _prompt_trading_args() -> list[str]:
    extra: list[str] = []
    tp = input("  TP pips (blank = keep default): ").strip()
    if tp:
        extra += ["--tp-pips", tp]
    sl = input("  SL pips (blank = keep default): ").strip()
    if sl:
        extra += ["--sl-pips", sl]
    return extra


def _run_phase(index: int) -> int:
    label, stages = PHASES[index]
    print(f"\n{label}: {', '.join(stages)}")
    confirm = input("Run this phase? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Skipped.")
        return 0

    extra_by_stage: dict[str, list[str]] = {}
    if label == "Position engine":
        extra_by_stage["s5"] = _prompt_trading_args()

    for name in stages:
        print(f"\n=== bt {name} ===", flush=True)
        rc = _run_stage(name, extra_by_stage.get(name, []))
        if rc != 0:
            print(f"bt: {name} failed (exit {rc})", file=sys.stderr)
            return rc
    print(f"{label}: done.")
    return 0


def _fzf_select(choices: list[str], prompt: str) -> str | None:
    if shutil.which("fzf") is None:
        print("bt: fzf not found in PATH", file=sys.stderr)
        return None
    proc = subprocess.run(
        ["fzf", f"--prompt={prompt}> "],
        input="\n".join(choices),
        capture_output=True,
        text=True,
    )
    choice = proc.stdout.strip()
    return choice if proc.returncode == 0 and choice else None


def _print_csv(path: Path) -> None:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv_mod.reader(f))
    if not rows:
        return
    ncols = len(rows[0])
    widths = [max(len(row[i]) for row in rows if i < len(row)) for i in range(ncols)]
    for row in rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))


def _result_entries() -> list[tuple[str, Path]]:
    """`bt flow`のView resultsで選べる結果ディレクトリ一覧。
    rank/all(最新) → rank/all/history/<timestamp>(古い順)→ monthly/<YYYY-MM> の順。"""
    from lib.env_paths import get_backtest_data_root

    root = get_backtest_data_root()
    entries: list[tuple[str, Path]] = []

    rank_all = root / "rank" / "all"
    if rank_all.exists() and any(f.suffix == ".csv" for f in rank_all.glob("*.csv")):
        entries.append(("rank/all (latest)", rank_all))

    history_root = rank_all / "history"
    if history_root.exists():
        for d in sorted(history_root.iterdir(), reverse=True):
            if d.is_dir():
                entries.append((f"rank/all/history/{d.name}", d))

    monthly_root = root / "monthly"
    if monthly_root.exists():
        for d in sorted(monthly_root.iterdir(), reverse=True):
            if d.is_dir():
                entries.append((f"monthly/{d.name}", d))

    return entries


def _view_results() -> None:
    entries = _result_entries()
    if not entries:
        print("bt: no results found yet.")
        return

    labels = [label for label, _ in entries]
    chosen_label = _fzf_select(labels, "result")
    if chosen_label is None:
        return
    chosen_dir = dict(entries)[chosen_label]

    csvs = sorted(f for f in chosen_dir.rglob("*.csv") if f.is_file())
    if not csvs:
        print(f"bt: no CSV files under {chosen_dir}")
        return
    if len(csvs) == 1:
        chosen_csv = csvs[0]
    else:
        names = [str(f.relative_to(chosen_dir)) for f in csvs]
        chosen_name = _fzf_select(names, "file")
        if chosen_name is None:
            return
        chosen_csv = chosen_dir / chosen_name

    print(f"\n{chosen_csv}")
    _print_csv(chosen_csv)


def _flow() -> int:
    while True:
        print("\nSelect a phase to run:")
        for i, (label, stages) in enumerate(PHASES, start=1):
            last = _last_run_text(_phase_output_dir(i - 1))
            print(f"  {i}) {label:<20} ({', '.join(stages)}) — {last}")
        print("  v) View results")
        print("  q) Quit")
        try:
            choice = input("> ").strip().lower()
        except EOFError:
            return 0
        if choice in ("q", "quit"):
            return 0
        if choice == "v":
            _view_results()
            continue
        if not choice.isdigit() or not (1 <= int(choice) <= len(PHASES)):
            print("Invalid choice.")
            continue
        rc = _run_phase(int(choice) - 1)
        if rc != 0:
            print(f"Phase failed (exit {rc}). Back to menu.", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        _print_help()
        return 0

    cmd, rest = argv[0], argv[1:]

    if cmd == "flow":
        if rest:
            print("bt: 'flow' does not take extra args", file=sys.stderr)
            return 2
        return _flow()

    if cmd == "all":
        if rest:
            print("bt: 'all' does not forward extra args (per-stage flags differ) — use env vars, or run stages individually", file=sys.stderr)
            return 2
        for name in PIPELINE_ORDER:
            print(f"\n=== bt {name} ===", flush=True)
            rc = _run_stage(name, [])
            if rc != 0:
                print(f"bt: {name} failed (exit {rc}), abort", file=sys.stderr)
                return rc
        return 0

    if cmd not in STAGES:
        print(f"bt: unknown stage {cmd!r}", file=sys.stderr)
        _print_help()
        return 2

    return _run_stage(cmd, rest)


if __name__ == "__main__":
    raise SystemExit(main())
