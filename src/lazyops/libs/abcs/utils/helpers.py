from __future__ import annotations

import collections.abc
from typing import Dict, Optional, Any


def update_dict(d: Dict, u: Dict, exclude_none: Optional[bool] = False, unset_value: Optional[str] = 'UNSET') -> Dict:
    """
    Recursively update a dictionary
    """
    unset_keys = []
    for k, v in u.items():
        if exclude_none and v is None:
            continue
        if isinstance(v, str) and v == unset_value:
            unset_keys.append(k)
            continue
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_dict(d.get(k, {}), v)
        elif isinstance(v, list):
            d[k] = d.get(k, []) + v
        else:
            d[k] = v
    for k in unset_keys:
        d.pop(k, None)
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


# https://stackoverflow.com/questions/27265939/comparing-python-dictionaries-and-nested-dictionaries



def diff_dict(d1: Dict[str, Any], d2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns the difference between two dictionaries

    d1 should be the original dict
    d2 should be the new/updated dict

    Returns a dict with the differences between d1 and d2
    """
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    shared_keys = d1_keys.intersection(d2_keys)
    shared_deltas = {o: (d1[o], d2[o]) for o in shared_keys if d1[o] != d2[o]}
    added_keys = d2_keys - d1_keys
    added_deltas = {o: (None, d2[o]) for o in added_keys}
    deltas = {**shared_deltas, **added_deltas}
    return parse_deltas(deltas)


def parse_deltas(deltas: dict) -> dict:
    """
    Parses the deltas
    """
    res = {}
    for k, v in deltas.items():
        if isinstance(v[0], dict):
            tmp = diff_dict(v[0], v[1])
            if tmp:
                res[k] = tmp
        else:
            res[k] = v[1]
    return res