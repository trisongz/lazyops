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