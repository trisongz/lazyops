from __future__ import annotations

from pydantic.alias_generators import to_camel
from typing import Any, Dict, Type, Union


def dict_diff(dict_a: Dict[str, Any], dict_b: Dict[str, Any], show_value_diff: bool = True):
    
    """
    Compare two dictionaries and return the difference between them
    """
    result = {
        'added': {k: dict_b[k] for k in set(dict_b) - set(dict_a)},
        'removed': {k: dict_a[k] for k in set(dict_a) - set(dict_b)},
    }
    if show_value_diff:
        common_keys =  set(dict_a) & set(dict_b)
        result['value_diffs'] = {
            k:(dict_a[k], dict_b[k])
            for k in common_keys
            if dict_a[k] != dict_b[k]
        }
    return result


def format_table_name(table_name: str) -> str:
    """
    Formats the table name

    >>> format_table_name('my.test.table_name') 
    'my_test_tableName'
    """
    parts = table_name.split('.')
    parts = [to_camel(part) for part in parts]
    return '_'.join(parts)
