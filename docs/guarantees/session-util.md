# session-util

| 保証 | 対応テスト |
|---|---|
| `decide_session(t, params)` は、`SESS_TYO`・`SESS_LON`・`SESS_NYC` の範囲から、時刻が属するセッション名（`TYO`/`LON`/`NYC`）を返す | `test_decide_session_tyo`, `test_decide_session_nyc` |
| `decide_session(t, params)` は、セッション範囲の開始時刻を範囲に含める | `test_decide_session_lon_boundary_inclusive_start` |
| `decide_session(t, params)` は、どの範囲にも属さない時刻に空文字列を返す | `test_decide_session_outside_all_ranges_returns_empty` |
| `normalize_session_label(label)` は `LDN` を `LON` に直す | `test_normalize_session_label_maps_ldn_to_lon` |
| `normalize_session_label(label)` は `LDN` 以外のラベルをそのまま返す | `test_normalize_session_label_maps_ldn_to_lon` |
| `is_own(label, own)` は、正規化したラベルが一致すれば `1`、しなければ `0` を返す | `test_is_own_matches_after_normalization` |
