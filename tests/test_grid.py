import lib.grid as grid


def test_empty_params_returns_single_empty_dict():
    assert grid.expand_param_grid({}) == [{}]


def test_scalar_values_are_wrapped_as_single_option():
    out = grid.expand_param_grid({"a": 1, "b": "x"})
    assert out == [{"a": 1, "b": "x"}]


def test_cartesian_product_of_list_values():
    out = grid.expand_param_grid({"a": [1, 2], "b": [10, 20]})
    assert out == [
        {"a": 1, "b": 10},
        {"a": 1, "b": 20},
        {"a": 2, "b": 10},
        {"a": 2, "b": 20},
    ]


def test_mixed_scalar_and_list_values():
    out = grid.expand_param_grid({"a": [1, 2], "b": "fixed"})
    assert out == [{"a": 1, "b": "fixed"}, {"a": 2, "b": "fixed"}]
