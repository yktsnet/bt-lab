import core.s2_gen_strategies as s2


def test_expand_grid_cartesian_product():
    out = s2._expand_grid({"a": [1, 2], "b": [10]})
    assert out == [{"a": 1, "b": 10}, {"a": 2, "b": 10}]


def test_make_slug_sorts_keys_and_formats_floats():
    slug = s2._make_slug({"b": 1.5, "a": 20})
    assert slug == "a20_b1p5"


def test_vstr_formats_float_without_trailing_zeros():
    assert s2._vstr(2.0) == "2p0"
    assert s2._vstr(1.25) == "1p25"
    assert s2._vstr(14) == "14"


def test_main_generates_one_file_per_grid_combo(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    s2.main()

    strategies_root = tmp_path / "strategies"
    generated = sorted((strategies_root / "rsi_zone").glob("*.py"))
    # rsi_period in {14,21} x distance_from_mid in {20,25,30} = 6 combos
    assert len(generated) == 6

    out = capsys.readouterr().out
    assert "created=6" in out
    assert "kept=0" in out

    sample = generated[0].read_text()
    assert "SLUG = " in sample
    assert "PARAMS = " in sample


def test_main_second_run_keeps_everything(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    s2.main()
    capsys.readouterr()
    s2.main()
    out = capsys.readouterr().out
    assert "kept=6" in out
    assert "created=0" in out
    assert "updated=0" in out
    assert "deleted=0" in out


def test_main_deletes_stray_files_not_in_desired_set(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))
    s2.main()
    capsys.readouterr()

    strategies_root = tmp_path / "strategies"
    stray = strategies_root / "rsi_zone" / "stray_leftover.py"
    stray.write_text("# leftover\n")

    s2.main()
    out = capsys.readouterr().out
    assert "deleted=1" in out
    assert not stray.exists()


def test_main_skips_combos_with_missing_required_features(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BACKTEST_DATA_ROOT", str(tmp_path))

    # Point the feature registry lookup at a temp dir with no features declared,
    # so every rsi_zone combo's required_features (rsiN) is unavailable.
    empty_import_root = tmp_path / "import_empty"
    empty_import_root.mkdir()
    (empty_import_root / "feature_registry.yaml").write_text("precompute: []\n")
    monkeypatch.setattr(s2, "get_import_root", lambda: empty_import_root)

    s2.main()
    out = capsys.readouterr().out
    assert "desired=0" in out
    assert "skipped=6" in out
