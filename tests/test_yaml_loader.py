from lib.yaml_loader import load_yaml


def test_load_yaml_reads_mapping(tmp_path):
    p = tmp_path / "sample.yaml"
    p.write_text("a: 1\nb:\n  - x\n  - y\n", encoding="utf-8")
    data = load_yaml(p)
    assert data == {"a": 1, "b": ["x", "y"]}


def test_load_yaml_empty_file_returns_none(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    assert load_yaml(p) is None
