import os
import sys
import time
from pathlib import Path

import bt


def test_stage_scripts_exist():
    """STAGESの各エントリが指すスクリプトがcore/に実在すること（取り残しを検知する）。"""
    core = Path(__file__).resolve().parents[1] / "core"
    for name, script in bt.STAGES.items():
        assert (core / script).exists(), f"stage {name!r} -> core/{script} not found"


def test_pipeline_order_is_s1b_through_s8():
    assert bt.PIPELINE_ORDER == ["s1b", "s1c", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]
    assert set(bt.PIPELINE_ORDER) <= set(bt.STAGES)


def test_phases_cover_pipeline_order_exactly():
    """PHASES(bt flowのフェーズ分割)がPIPELINE_ORDERの段を過不足なく分割していること。"""
    flattened = [name for _, stages in bt.PHASES for name in stages]
    assert flattened == bt.PIPELINE_ORDER


def test_no_args_prints_help_and_exits_0(capsys):
    rc = bt.main([])
    assert rc == 0
    assert "stages:" in capsys.readouterr().out


def test_unknown_stage_exits_2(capsys):
    rc = bt.main(["s99"])
    assert rc == 2
    assert "unknown stage" in capsys.readouterr().err


def test_all_rejects_extra_args(capsys):
    rc = bt.main(["all", "--foo"])
    assert rc == 2
    assert "does not forward extra args" in capsys.readouterr().err


def test_all_aborts_on_first_stage_failure(monkeypatch):
    calls = []

    def fake_run_stage(name, extra_args):
        calls.append(name)
        return 1 if name == "s3" else 0

    monkeypatch.setattr(bt, "_run_stage", fake_run_stage)
    rc = bt.main(["all"])

    assert rc == 1
    assert calls == ["s1b", "s1c", "s2", "s3"]


def test_flow_rejects_extra_args(capsys):
    rc = bt.main(["flow", "--foo"])
    assert rc == 2
    assert "does not take extra args" in capsys.readouterr().err


def test_flow_quit_immediately_runs_nothing(monkeypatch):
    monkeypatch.setattr(bt, "_run_stage", lambda name, extra: (_ for _ in ()).throw(AssertionError("should not run")))
    monkeypatch.setattr("builtins.input", lambda prompt="": "q")
    rc = bt.main(["flow"])
    assert rc == 0


def test_flow_invalid_choice_then_quit(monkeypatch, capsys):
    responses = iter(["9", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    rc = bt.main(["flow"])
    assert rc == 0
    assert "Invalid choice" in capsys.readouterr().out


def test_flow_declining_confirmation_skips_phase(monkeypatch, capsys):
    responses = iter(["1", "n", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    monkeypatch.setattr(bt, "_run_stage", lambda name, extra: (_ for _ in ()).throw(AssertionError("should not run")))
    rc = bt.main(["flow"])
    assert rc == 0
    assert "Skipped." in capsys.readouterr().out


def test_flow_runs_selected_phase_stages_in_order(monkeypatch):
    calls = []
    monkeypatch.setattr(bt, "_run_stage", lambda name, extra: calls.append((name, extra)) or 0)
    responses = iter(["2", "y", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    rc = bt.main(["flow"])
    assert rc == 0
    assert calls == [("s2", []), ("s3", []), ("s4", [])]


def test_flow_position_engine_phase_prompts_for_tp_sl(monkeypatch):
    calls = []
    monkeypatch.setattr(bt, "_run_stage", lambda name, extra: calls.append((name, extra)) or 0)
    responses = iter(["3", "y", "40", "15", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    rc = bt.main(["flow"])
    assert rc == 0
    assert calls == [("s5", ["--tp-pips", "40", "--sl-pips", "15"])]


def test_flow_view_results_menu_entry(monkeypatch):
    calls = []
    monkeypatch.setattr(bt, "_view_results", lambda: calls.append("viewed"))
    responses = iter(["v", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    rc = bt.main(["flow"])
    assert rc == 0
    assert calls == ["viewed"]


def test_run_stage_archives_rank_output_after_s8_success(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    rank_all = tmp_path / "rank" / "all"
    rank_all.mkdir(parents=True)
    (rank_all / "rank_by_pips_avg.csv").write_text("a,b\n1,2\n")

    monkeypatch.setattr(bt.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
    bt._run_stage("s8", [])

    history_dirs = list((rank_all / "history").iterdir())
    assert len(history_dirs) == 1
    assert (history_dirs[0] / "rank_by_pips_avg.csv").read_text() == "a,b\n1,2\n"


def test_run_stage_does_not_archive_on_s8_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    rank_all = tmp_path / "rank" / "all"
    rank_all.mkdir(parents=True)
    (rank_all / "rank_by_pips_avg.csv").write_text("a,b\n1,2\n")

    monkeypatch.setattr(bt.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 1})())
    bt._run_stage("s8", [])

    assert not (rank_all / "history").exists()


def test_run_stage_does_not_archive_for_non_s8_stages(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    rank_all = tmp_path / "rank" / "all"
    rank_all.mkdir(parents=True)
    (rank_all / "rank_by_pips_avg.csv").write_text("a,b\n1,2\n")

    monkeypatch.setattr(bt.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0})())
    bt._run_stage("s7", [])

    assert not (rank_all / "history").exists()


def test_result_entries_lists_latest_history_then_monthly(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    rank_all = tmp_path / "rank" / "all"
    rank_all.mkdir(parents=True)
    (rank_all / "rank_by_pips_avg.csv").write_text("a\n1\n")
    (rank_all / "history" / "20260101_000000").mkdir(parents=True)
    (rank_all / "history" / "20260201_000000").mkdir(parents=True)
    (tmp_path / "monthly" / "2026-06").mkdir(parents=True)

    entries = bt._result_entries()
    labels = [label for label, _ in entries]
    assert labels == [
        "rank/all (latest)",
        "rank/all/history/20260201_000000",
        "rank/all/history/20260101_000000",
        "monthly/2026-06",
    ]


def test_view_results_no_results_prints_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    bt._view_results()
    assert "no results found" in capsys.readouterr().out


def test_view_results_selects_and_prints_csv(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    rank_all = tmp_path / "rank" / "all"
    rank_all.mkdir(parents=True)
    (rank_all / "rank_by_pips_avg.csv").write_text("a,b\n1,2\n")

    monkeypatch.setattr(bt, "_fzf_select", lambda choices, prompt: choices[0])
    bt._view_results()

    out = capsys.readouterr().out
    assert "a" in out and "b" in out and "1" in out and "2" in out


def test_flow_aborts_phase_on_stage_failure_and_returns_to_menu(monkeypatch, capsys):
    calls = []

    def fake_run_stage(name, extra):
        calls.append(name)
        return 1 if name == "s3" else 0

    monkeypatch.setattr(bt, "_run_stage", fake_run_stage)
    responses = iter(["2", "y", "q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    rc = bt.main(["flow"])
    assert rc == 0
    assert calls == ["s2", "s3"]
    assert "Phase failed" in capsys.readouterr().err


def test_stage_dispatch_forwards_extra_args_to_subprocess(monkeypatch):
    """`bt <stage> <options>`が個別ステージ実行時、追加引数を実際にsubprocessへ転送すること
    （_run_stage自体はモックせず、本物のsubprocess起動経路を通す）。"""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(bt.subprocess, "run", fake_run)
    rc = bt.main(["s5", "--tp-pips", "40", "--sl-pips", "15"])
    assert rc == 0
    assert calls == [
        [sys.executable, str(bt.CORE / "s5_position_engine.py"), "--tp-pips", "40", "--sl-pips", "15"]
    ]


def test_stage_dispatch_with_no_extra_args(monkeypatch):
    calls = []
    monkeypatch.setattr(bt.subprocess, "run", lambda cmd, **k: calls.append(cmd) or type("R", (), {"returncode": 0})())
    rc = bt.main(["s2"])
    assert rc == 0
    assert calls == [[sys.executable, str(bt.CORE / "s2_gen_strategies.py")]]


def test_last_run_text_never_run_for_missing_dir(tmp_path):
    assert bt._last_run_text(tmp_path / "nonexistent") == "never run"


def test_last_run_text_never_run_for_empty_dir(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    assert bt._last_run_text(d) == "never run"


def test_last_run_text_updated_today(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    (d / "f.csv").write_text("x")
    assert bt._last_run_text(d) == "updated today"


def test_last_run_text_updated_one_day_ago(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    f = d / "f.csv"
    f.write_text("x")
    old = time.time() - 1.5 * 86400
    os.utime(f, (old, old))
    assert bt._last_run_text(d) == "updated 1 day ago"


def test_last_run_text_updated_n_days_ago(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    f = d / "f.csv"
    f.write_text("x")
    old = time.time() - 3 * 86400
    os.utime(f, (old, old))
    assert bt._last_run_text(d) == "updated 3 days ago"


def test_last_run_text_uses_latest_file_among_many(tmp_path):
    d = tmp_path / "out"
    d.mkdir()
    old_f = d / "old.csv"
    old_f.write_text("x")
    old = time.time() - 5 * 86400
    os.utime(old_f, (old, old))
    (d / "new.csv").write_text("y")
    assert bt._last_run_text(d) == "updated today"


def test_fzf_select_not_found_in_path(monkeypatch, capsys):
    monkeypatch.setattr(bt.shutil, "which", lambda name: None)
    result = bt._fzf_select(["a", "b"], "prompt")
    assert result is None
    assert "fzf not found" in capsys.readouterr().err


def test_fzf_select_invokes_real_subprocess_with_expected_args(monkeypatch):
    """_fzf_select自体はモックせず、実際にsubprocess.runへ渡す引数（--prompt・input・
    capture_output・text）を検証する。"""
    monkeypatch.setattr(bt.shutil, "which", lambda name: "/usr/bin/fzf")
    captured = {}

    def fake_run(cmd, input=None, capture_output=None, text=None):
        captured.update(cmd=cmd, input=input, capture_output=capture_output, text=text)
        return type("R", (), {"stdout": "chosen\n", "returncode": 0})()

    monkeypatch.setattr(bt.subprocess, "run", fake_run)
    result = bt._fzf_select(["chosen", "other"], "result")

    assert result == "chosen"
    assert captured == {
        "cmd": ["fzf", "--prompt=result> "],
        "input": "chosen\nother",
        "capture_output": True,
        "text": True,
    }


def test_fzf_select_returns_none_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(bt.shutil, "which", lambda name: "/usr/bin/fzf")
    monkeypatch.setattr(bt.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "x\n", "returncode": 1})())
    assert bt._fzf_select(["x"], "p") is None


def test_fzf_select_returns_none_on_empty_choice(monkeypatch):
    monkeypatch.setattr(bt.shutil, "which", lambda name: "/usr/bin/fzf")
    monkeypatch.setattr(bt.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "\n", "returncode": 0})())
    assert bt._fzf_select(["x"], "p") is None
