from itertools import product
from typing import Any


def _as_list(v: Any):
    return v if isinstance(v, list) else [v]


def expand_param_grid(params: dict):
    if not params:
        return [{}]
    keys = list(params.keys())
    values = [_as_list(params[k]) for k in keys]
    out = []
    for combo in product(*values):
        out.append({k: v for k, v in zip(keys, combo)})
    return out
