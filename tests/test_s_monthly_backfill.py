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


def _recording_runner(calls, fail_on=None):
    def fake_run(cmd, env=None):
        calls.append((cmd, (env or {}).get("S8_AS_OF"), (env or {}).get("SIM_MONTH")))
        return type("R", (), {"returncode": 1 if cmd[1] == fail_on else 0})()

    return fake_run


def test_run_invokes_s4_s8_then_sim_for_each_month(monkeypatch):
    calls = []
    monkeypatch.setattr(backfill.subprocess, "run", _recording_runner(calls))
    monkeypatch.setattr(backfill, "_months_to_backfill", lambda n: ["2026-01", "2026-02"])

    backfill.run(backfill.argparse.Namespace(months=2))

    assert len(calls) == 6  # S4 + S8 + sim per month
    assert calls[0][0] == [backfill.PYTHON, backfill.S4, "--as-of", "2026-01"]
    assert calls[1][0] == [backfill.PYTHON, backfill.S8]
    assert calls[1][1] == "2026-01"
    assert calls[2][0] == [backfill.PYTHON, backfill.SIM]
    assert calls[2][2] == "2026-02"
    assert calls[3][0] == [backfill.PYTHON, backfill.S4, "--as-of", "2026-02"]
    assert calls[4][1] == "2026-02"
    assert calls[5][2] == "2026-03"


def test_run_aborts_on_s4_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(backfill.subprocess, "run", _recording_runner(calls, fail_on=backfill.S4))
    monkeypatch.setattr(backfill, "_months_to_backfill", lambda n: ["2026-01", "2026-02"])

    with pytest.raises(SystemExit) as exc:
        backfill.run(backfill.argparse.Namespace(months=2))
    assert exc.value.code == 1
    assert len(calls) == 1  # S8 and sim never start


def test_run_aborts_on_s8_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(backfill.subprocess, "run", _recording_runner(calls, fail_on=backfill.S8))
    monkeypatch.setattr(backfill, "_months_to_backfill", lambda n: ["2026-01", "2026-02"])

    with pytest.raises(SystemExit) as exc:
        backfill.run(backfill.argparse.Namespace(months=2))
    assert exc.value.code == 1
    assert len(calls) == 2  # S4 succeeded, S8 failed -> abort


def test_run_aborts_on_sim_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(backfill.subprocess, "run", _recording_runner(calls, fail_on=backfill.SIM))
    monkeypatch.setattr(backfill, "_months_to_backfill", lambda n: ["2026-01", "2026-02"])

    with pytest.raises(SystemExit) as exc:
        backfill.run(backfill.argparse.Namespace(months=2))
    assert exc.value.code == 1
    assert len(calls) == 3  # S4 and S8 succeeded, sim for first month failed -> abort


def test_months_to_backfill_returns_last_n_months():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date()
    y, m = today.year, today.month
    expected = []
    for _ in range(4):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        expected.append(f"{y}-{m:02d}")
    assert backfill._months_to_backfill(4) == sorted(expected)
