import math

import pandas as pd
import pytest

import core.s_selection_eval as ev


def _ns(top=10, from_month=None, until_month=None):
    return ev.argparse.Namespace(top=top, from_month=from_month, until_month=until_month)


def _write_monthly(root, rows):
    for year in sorted({r["year"] for r in rows}):
        d = root / "summary" / "all" / str(year)
        d.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([r for r in rows if r["year"] == year]).to_csv(d / "monthly_all.csv", index=False)


def _m(year, month, slug, pips):
    return {"year": year, "month": month, "id": "k", "slug": slug, "pips_sum_total": pips}


def _write_rank(root, snap, name, slugs):
    d = root / "rank" / "all" / "snapshots" / snap
    d.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"rank": range(1, len(slugs) + 1), "id": "k", "slug": slugs})
    df.to_csv(d / f"{name}.csv", index=False)


def _out(root):
    return pd.read_csv(root / "rank" / "all" / "eval" / "selection_eval.csv")


@pytest.fixture
def data(monkeypatch, tmp_path):
    monkeypatch.setenv("DRIP_SIM_DATA", str(tmp_path))
    return tmp_path


def _basic_monthly(root):
    rows = [_m(2026, 1, s, 1.0) for s in "abcdef"]
    # e は 2 月に行が無い（0 pips 扱い）。g は 3 月が初出で 1 月末の母集団に入らない
    rows += [_m(2026, 2, "a", 10.0), _m(2026, 2, "b", -5.0), _m(2026, 2, "c", 0.0),
             _m(2026, 2, "d", 20.0), _m(2026, 2, "f", -15.0), _m(2026, 2, "g", 1000.0)]
    _write_monthly(root, rows)


def test_hand_calculated_row(data):
    _basic_monthly(data)
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "a", "b"])

    ev.run(_ns(top=2))

    out = _out(data)
    assert list(out.columns) == ev.OUT_COLS
    assert len(out) == 1
    row = out.iloc[0]
    assert row["snapshot"] == "2026-01"
    assert row["rank_file"] == "rank_by_pips_avg"
    assert row["n_universe"] == 6
    assert row["n_selected"] == 3
    assert row["univ_mean_pips"] == pytest.approx(10 / 6)
    assert row["sel_mean_pips"] == pytest.approx(25 / 3)
    assert row["sel_minus_univ"] == pytest.approx(25 / 3 - 10 / 6)
    assert row["topk_mean_pips"] == pytest.approx(15.0)
    assert row["topk_hit_rate"] == pytest.approx(1.0)
    assert row["rank_corr"] == pytest.approx(1.0)


def test_universe_counts_missing_next_month_as_zero_pips(data):
    _basic_monthly(data)
    # e は 2 月に行が無い → 0。選ばれても 0 として平均に入る
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["e", "d", "f"])

    ev.run(_ns())

    row = _out(data).iloc[0]
    assert row["sel_mean_pips"] == pytest.approx((0 + 20 - 15) / 3)


def test_topk_hit_rate_counts_only_strictly_positive(data):
    _basic_monthly(data)
    # d=20(>0), c=0(not >0), b=-5, a=10
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "c", "b", "a"])

    ev.run(_ns(top=3))

    row = _out(data).iloc[0]
    assert row["topk_hit_rate"] == pytest.approx(1 / 3)
    assert row["topk_mean_pips"] == pytest.approx((20 + 0 - 5) / 3)


def test_rank_corr_is_negative_when_ranking_inverted(data):
    _basic_monthly(data)
    # 順位が低い（悪い）ほど翌月が良い: f(-15), b(-5), a(10), d(20)
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["f", "b", "a", "d"])

    ev.run(_ns())

    assert _out(data).iloc[0]["rank_corr"] == pytest.approx(-1.0)


def test_rank_corr_nan_under_three_selected(data):
    _basic_monthly(data)
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "a"])

    ev.run(_ns())

    assert math.isnan(_out(data).iloc[0]["rank_corr"])


def test_spearman_handles_ties_and_constants():
    # 同順位は平均順位。pips が全て同じなら相関は定義できない
    assert math.isnan(ev._spearman(pd.Series([1, 2, 3]), pd.Series([5.0, 5.0, 5.0])))
    r = ev._spearman(pd.Series([1, 2, 3, 4]), pd.Series([9.0, 9.0, 3.0, 1.0]))
    # rank(x)=[1,2,3,4], rank(y)=[3.5,3.5,2,1]
    assert r == pytest.approx(0.9486832980505138)


def test_snapshot_without_next_month_data_is_skipped(data):
    _basic_monthly(data)  # 3 月のデータは無い
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "a", "b"])
    _write_rank(data, "2026-02", "rank_by_pips_avg", ["d", "a", "b"])

    ev.run(_ns())

    assert list(_out(data)["snapshot"]) == ["2026-01"]


def test_all_rank_files_in_snapshot_are_evaluated(data):
    _basic_monthly(data)
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "a", "b"])
    _write_rank(data, "2026-01", "rank_by_tstat", ["a", "d", "b"])

    ev.run(_ns())

    out = _out(data)
    assert sorted(out["rank_file"]) == ["rank_by_pips_avg", "rank_by_tstat"]


def test_summary_printed_per_rank_file(data, capsys):
    rows = [_m(2026, 1, s, 1.0) for s in "abcdef"]
    rows += [_m(2026, 2, "a", 10.0), _m(2026, 2, "b", -5.0), _m(2026, 2, "c", 0.0),
             _m(2026, 2, "d", 20.0), _m(2026, 2, "f", -15.0), _m(2026, 2, "g", 1000.0)]
    rows += [_m(2026, 3, s, v) for s, v in zip("abcdef", [1, 2, 3, 4, 5, 6])]
    _write_monthly(data, rows)
    # 1 月: 差 +40/6、相関 +1。2 月: 母集団 a..g の平均 3、選抜 2 → 差 -1、相関 -1
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "a", "b"])
    _write_rank(data, "2026-02", "rank_by_pips_avg", ["a", "b", "c"])

    ev.run(_ns())

    out = capsys.readouterr().out
    assert (
        "[rank_by_pips_avg]: months=2 mean_sel_minus_univ=2.83 "
        "share_positive=0.50 mean_rank_corr=0.000"
    ) in out


def test_from_until_limit_snapshot_range_and_do_not_read_outside(data):
    rows = [_m(2025, 12, s, 1.0) for s in "abcdef"]
    rows += [_m(2026, 1, s, 1.0) for s in "abcdef"]
    rows += [_m(2026, 2, "a", 10.0), _m(2026, 2, "b", -5.0), _m(2026, 3, "a", 1.0)]
    _write_monthly(data, rows)
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["a", "b", "c"])
    # 範囲外のスナップショットにも翌月のデータがある。範囲で絞らなければ読まれて
    # EmptyDataError で落ちる（from 側は 2025-12、until 側は 2026-02）
    for snap in ("2025-12", "2026-02"):
        d = data / "rank" / "all" / "snapshots" / snap
        d.mkdir(parents=True)
        (d / "rank_by_pips_avg.csv").write_text("")

    ev.run(_ns(from_month="2026-01", until_month="2026-01"))

    assert list(_out(data)["snapshot"]) == ["2026-01"]


def test_top_defaults_to_10(monkeypatch):
    monkeypatch.setattr(ev.sys, "argv", ["s_selection_eval.py"])
    args = ev.parse_args()
    assert args.top == 10
    assert args.from_month is None and args.until_month is None


def test_top_changes_k(data):
    _basic_monthly(data)
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "a", "b"])

    ev.run(_ns(top=1))

    row = _out(data).iloc[0]
    assert row["topk_mean_pips"] == pytest.approx(20.0)
    assert row["sel_mean_pips"] == pytest.approx(25 / 3)


def test_no_snapshots_prints_message_and_writes_nothing(data, capsys):
    _basic_monthly(data)

    ev.run(_ns())

    assert "no snapshots" in capsys.readouterr().out
    assert not (data / "rank" / "all" / "eval" / "selection_eval.csv").exists()


def test_no_monthly_data_prints_message_and_writes_nothing(data, capsys):
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "a", "b"])

    ev.run(_ns())

    assert "monthly_all.csv" in capsys.readouterr().out
    assert not (data / "rank" / "all" / "eval" / "selection_eval.csv").exists()


def test_no_next_month_for_any_snapshot_prints_message(data, capsys):
    _basic_monthly(data)
    _write_rank(data, "2026-02", "rank_by_pips_avg", ["d", "a", "b"])

    ev.run(_ns())

    assert "Nothing to evaluate" in capsys.readouterr().out
    assert not (data / "rank" / "all" / "eval" / "selection_eval.csv").exists()


def test_write_failure_leaves_existing_output_untouched(data, monkeypatch):
    _basic_monthly(data)
    _write_rank(data, "2026-01", "rank_by_pips_avg", ["d", "a", "b"])
    out_path = data / "rank" / "all" / "eval" / "selection_eval.csv"
    out_path.parent.mkdir(parents=True)
    out_path.write_text("old\n")

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(ev.os, "replace", boom)
    with pytest.raises(OSError):
        ev.run(_ns())

    assert out_path.read_text() == "old\n"


def test_next_month_rolls_over_year():
    assert ev._next_month("2025-12") == "2026-01"
    assert ev._next_month("2026-01") == "2026-02"


def test_month_arg_rejects_malformed():
    with pytest.raises(ev.argparse.ArgumentTypeError):
        ev._month_arg("2026-13")
    with pytest.raises(ev.argparse.ArgumentTypeError):
        ev._month_arg("202601")
    assert ev._month_arg("2026-01") == "2026-01"


def test_eval_stage_is_registered_but_outside_pipeline_order():
    import bt

    assert bt.STAGES["eval"] == "s_selection_eval.py"
    assert "eval" not in bt.PIPELINE_ORDER
    assert all("eval" not in stages for _, stages in bt.PHASES)
