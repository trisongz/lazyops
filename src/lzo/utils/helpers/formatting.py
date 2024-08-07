from __future__ import annotations

"""
Formatting Helpers
"""

import datetime
import contextlib
from typing import List, Dict, Any, Union

def build_dict_from_str(
    data: str,
    **kwargs
) -> Union[List[Any], Dict[str, Any]]:
    """
    Helper to build a dictionary from a string
    """
    import json
    if (data.startswith('[') and data.endswith(']')) or (data.startswith('{') and data.endswith('}')):
        return json.loads(data)
    return build_dict_from_list(data.split(','), **kwargs)


def build_dict_from_list(
    data: List[str],
    seperator: str = '=',
) -> Dict[str, Any]:
    """
    Builds a dictionary from a list of strings
    """
    import json
    return json.loads(str(dict([item.split(seperator) for item in data])))


def build_dict_from_query(
    query: str,
    **kwargs,
) -> Dict[str, Union[int, float, str, datetime.datetime, Any]]:
    """
    Builds a dictionary from a query
    """
    # Try to base decode it
    if not query.startswith('{') and not query.startswith('['):
        import base64
        query = base64.b64decode(query).decode('utf-8')
    data = build_dict_from_str(query, **kwargs)
    for k,v in data.items():
        if 'date' in k:
            with contextlib.suppress(Exception):
                from lazyops.utils.dates import parse_datetime
                v = parse_datetime(v)
        data[k] = v
    return data