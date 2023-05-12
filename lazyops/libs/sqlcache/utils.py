from lazyops.libs.sqlcache.constants import ENOVAL
from typing import Dict, Tuple


def full_name(func):
    "Return full name of `func` by adding the module and function name."
    return f'{func.__module__}.{func.__qualname__}'


def args_to_key(base: Tuple, args: Tuple, kwargs: Dict, typed: bool) -> Tuple:
    """Create cache key out of function arguments.
    :param tuple base: base of key
    :param tuple args: function arguments
    :param dict kwargs: function keyword arguments
    :param bool typed: include types in cache key
    :return: cache key tuple
    """
    key = base + args

    if kwargs:
        key += (ENOVAL,)
        sorted_items = sorted(kwargs.items())
        for item in sorted_items:
            key += item

    if typed:
        key += tuple(type(arg) for arg in args)
        if kwargs:
            key += tuple(type(value) for _, value in sorted_items)

    return key
