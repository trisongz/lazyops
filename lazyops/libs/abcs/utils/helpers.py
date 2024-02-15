from __future__ import annotations

import collections.abc
from typing import Dict, Optional


def update_dict(d: Dict, u: Dict, exclude_none: Optional[bool] = False) -> Dict:
    """
    Recursively update a dictionary
    """
    for k, v in u.items():
        if exclude_none and v is None:
            continue
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_dict(d.get(k, {}), v)
        elif isinstance(v, list):
            d[k] = d.get(k, []) + v
        else:
            d[k] = v
    return d


def merge_recursive_dict(
    d: Dict,
    current_key: str,
) -> Dict:
    """
    Merge a recursive dictionary
    """
    if not isinstance(d, collections.abc.Mapping):
        return d
    mapping = {}
    for k, v in d.items():
        current_key = f'{current_key}.{k}'
        if isinstance(v, (collections.abc.Mapping, dict)):
            mapping[current_key] = merge_recursive_dict(v, current_key)
        else:
            mapping[current_key] = v
    return mapping


def flatten_dict_value(
    d: Dict,
    parent_key: str = '',
) -> str:
    """
    Flatten a dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f'{parent_key}.{k}' if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict_value(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)