# -*- coding: utf-8 -*-
def _parse_hhmm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)

def _parse_range(v):
    a, b = v.split("-", 1)
    return _parse_hhmm(a), _parse_hhmm(b)

def _in_range(mins, start, end):
    if start <= end:
        return start <= mins < end
    return mins >= start or mins < end

def normalize_session_label(s):
    return "LON" if s == "LDN" else s

def decide_session(time_utc, params):
    sess_tyo = params.get("SESS_TYO", "00:00-07:00")
    sess_lon = params.get("SESS_LON", "07:00-13:00")
    sess_nyc = params.get("SESS_NYC", "13:00-17:00")
    r_tyo = _parse_range(sess_tyo)
    r_lon = _parse_range(sess_lon)
    r_nyc = _parse_range(sess_nyc)
    m = time_utc.hour * 60 + time_utc.minute
    if _in_range(m, r_tyo[0], r_tyo[1]):
        return "TYO"
    if _in_range(m, r_lon[0], r_lon[1]):
        return "LON"
    if _in_range(m, r_nyc[0], r_nyc[1]):
        return "NYC"
    return ""

def is_own(session, own_session):
    return 1 if normalize_session_label(session) == normalize_session_label(own_session) else 0
