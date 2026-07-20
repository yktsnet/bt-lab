import pytest

import core.s_monthly_backfill as backfill


def test_months_to_backfill_length_and_ordering():
    months = backfill._months_to_backfill(6)
    assert len(months) == 6
    assert months == sorted(months)
    for m in months:
        year, mo = m.split("-")
        assert 1 <= int(mo) <= 12


def test_months_to_backfill_consecutive():
    months = backfill._months_to_backfill(3)
    years_months = [(int(y), int(m)) for y, m in (s.split("-") for s in months)]
    for (y1, m1), (y2, m2) in zip(years_months, years_months[1:]):
        next_m = m1 + 1
        next_y = y1
        if next_m == 13:
            next_m = 1
            next_y += 1
        assert (next_y, next_m) == (y2, m2)


def test_run_invokes_s8_then_sim_for_each_month(monkeypatch):
    calls = []

    def fake_run(cmd, env=None):
        calls.append((cmd, env.get("S8_AS_OF"), env.get("SIM_MONTH")))
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(backfill.subprocess, "run", fake_run)
    monkeypatch.setattr(backfill, "_months_to_backfill", lambda n: ["2026-01", "2026-02"])

    args = backfill.argparse.Namespace(months=2)
    backfill.run(args)

    assert len(calls) == 4  # S8 + sim per month
    assert calls[0][0] == [backfill.PYTHON, backfill.S8]
    assert calls[0][1] == "2026-01"
    assert calls[1][0] == [backfill.PYTHON, backfill.SIM]
    assert calls[1][2] == "2026-02"
    assert calls[2][1] == "2026-02"
    assert calls[3][2] == "2026-03"


def test_run_aborts_on_s8_failure(monkeypatch):
    calls = []

    def fake_run(cmd, env=None):
        calls.append(cmd)
        is_s8 = cmd[1] == backfill.S8
        return type("R", (), {"returncode": 1 if is_s8 else 0})()

    monkeypatch.setattr(backfill.subprocess, "run", fake_run)
    monkeypatch.setattr(backfill, "_months_to_backfill", lambda n: ["2026-01", "2026-02"])

    args = backfill.argparse.Namespace(months=2)
    with pytest.raises(SystemExit) as exc:
        backfill.run(args)
    assert exc.value.code == 1
    assert len(calls) == 1  # aborted right after first S8 failure


def test_run_aborts_on_sim_failure(monkeypatch):
    calls = []

    def fake_run(cmd, env=None):
        calls.append(cmd)
        is_sim = cmd[1] == backfill.SIM
        return type("R", (), {"returncode": 1 if is_sim else 0})()

    monkeypatch.setattr(backfill.subprocess, "run", fake_run)
    monkeypatch.setattr(backfill, "_months_to_backfill", lambda n: ["2026-01", "2026-02"])

    args = backfill.argparse.Namespace(months=2)
    with pytest.raises(SystemExit) as exc:
        backfill.run(args)
    assert exc.value.code == 1
    assert len(calls) == 2  # S8 succeeded, sim for first month failed -> abort
