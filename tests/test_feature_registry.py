import lib.feature_registry as feature_registry


def test_load_feature_registry_fills_missing_sections(tmp_path):
    p = tmp_path / "registry.yaml"
    p.write_text("precompute:\n  - name: rsi14\n", encoding="utf-8")
    data = feature_registry.load_feature_registry(p)
    assert data["precompute"] == [{"name": "rsi14"}]
    assert data["runtime_only"] == []


def test_available_feature_names_union_of_both_sections(tmp_path):
    p = tmp_path / "registry.yaml"
    p.write_text(
        "precompute:\n"
        "  - name: rsi14\n"
        "  - name: ema9\n"
        "runtime_only:\n"
        "  - name: session\n",
        encoding="utf-8",
    )
    names = feature_registry.available_feature_names(p)
    assert names == {"rsi14", "ema9", "session"}


def test_available_feature_names_ignores_blank_names(tmp_path):
    p = tmp_path / "registry.yaml"
    p.write_text("precompute:\n  - name: ''\n  - name: rsi14\n", encoding="utf-8")
    assert feature_registry.available_feature_names(p) == {"rsi14"}


def test_available_feature_names_accepts_plain_string_list(tmp_path):
    """import/feature_registry.yamlの実フォーマット(素の文字列リスト)を受け付けること。"""
    p = tmp_path / "registry.yaml"
    p.write_text("precompute:\n  - rsi14\n  - ema9\n", encoding="utf-8")
    assert feature_registry.available_feature_names(p) == {"rsi14", "ema9"}


def test_precompute_specs_returns_raw_rows(tmp_path):
    p = tmp_path / "registry.yaml"
    p.write_text("precompute:\n  - name: rsi14\n    period: 14\n", encoding="utf-8")
    specs = feature_registry.precompute_specs(p)
    assert specs == [{"name": "rsi14", "period": 14}]
