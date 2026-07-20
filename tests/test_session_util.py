from datetime import datetime, timezone

import lib.session_util as session_util

PARAMS = {
    "SESS_TYO": "00:00-07:00",
    "SESS_LON": "07:00-13:00",
    "SESS_NYC": "13:00-17:00",
}


def _t(h, m):
    return datetime(2026, 1, 5, h, m, tzinfo=timezone.utc)


def test_decide_session_tyo():
    assert session_util.decide_session(_t(3, 30), PARAMS) == "TYO"


def test_decide_session_lon_boundary_inclusive_start():
    assert session_util.decide_session(_t(7, 0), PARAMS) == "LON"


def test_decide_session_nyc():
    assert session_util.decide_session(_t(15, 0), PARAMS) == "NYC"


def test_decide_session_outside_all_ranges_returns_empty():
    assert session_util.decide_session(_t(20, 0), PARAMS) == ""


def test_wraparound_range_crossing_midnight():
    # start > end means the range wraps past midnight
    assert session_util._in_range(23 * 60, 22 * 60, 2 * 60) is True
    assert session_util._in_range(1 * 60, 22 * 60, 2 * 60) is True
    assert session_util._in_range(12 * 60, 22 * 60, 2 * 60) is False


def test_normalize_session_label_maps_ldn_to_lon():
    assert session_util.normalize_session_label("LDN") == "LON"
    assert session_util.normalize_session_label("NYC") == "NYC"


def test_is_own_matches_after_normalization():
    assert session_util.is_own("LDN", "LON") == 1
    assert session_util.is_own("TYO", "LON") == 0
