from __future__ import annotations

"""
Hashing Helpers
"""

import hashlib
from lzl import load
from pydantic import BaseModel
from typing import Optional, Union, Any, TypeVar, Dict, List, TYPE_CHECKING

if load.TYPE_CHECKING:
    import xxhash
else:
    xxhash = load.LazyLoad("xxhash", install_missing = True)


PyModelType = TypeVar("PyModelType", bound=BaseModel)
ObjT = Union['PyModelType', Dict, Any]


def create_object_hash(
    obj: ObjT,
    _sep: Optional[str] = ':',
    _hash_length: Optional[int] = None,
) -> str:
    """
    Creates a deterministic hash for a given object using xxhash.

    Supports dictionaries, lists, tuples, sets, and Pydantic models.

    Args:
        obj: The object to hash.
        _sep: Separator used when joining iterable elements (default: ':').
        _hash_length: Length/type of hash (8=32bit, 16=64bit, 32/None=128bit).

    Returns:
        The resulting hexadecimal hash string.
    """
    if _hash_length is None or _hash_length == 32: _hasher = xxhash.xxh3_128_hexdigest
    elif _hash_length == 16: _hasher = xxhash.xxh3_64_hexdigest
    elif _hash_length == 8: _hasher = xxhash.xxh32_hexdigest

    if isinstance(obj, dict):
        return _hasher(str(obj))
    if isinstance(obj, (list, tuple, set)):
        return f'{_sep}'.join(create_object_hash(item, _sep = _sep) for item in obj)
    if isinstance(obj, BaseModel) or hasattr(obj, "model_dump"):
        return _hasher(obj.model_dump_json(exclude_none=True))
    return _hasher(str(obj))

def create_hash_from_args_and_kwargs(
    *args,
    _typed: Optional[bool] = False,
    _key_base: Optional[tuple] = None,
    _exclude: Optional[List[str]] = None,
    _exclude_none: Optional[bool] = True,
    _sep: Optional[str] = ':',
    _hash_length: Optional[int] = None,
    **kwargs,
) -> str:
    """
    Creates a deterministic hash from function arguments and keyword arguments.

    Useful for caching mechanisms where the cache key depends on input arguments.

    Args:
        *args: Positional arguments to include in the hash.
        _typed: If True, includes the type of positional arguments in the hash key.
        _key_base: An optional initial tuple to prepend to the hash key.
        _exclude: A list of keyword argument names to exclude from the hash.
        _exclude_none: If True, excludes keyword arguments with None values.
        _sep: Separator used for joining hash components.
        _hash_length: Length/type of hash (8=32bit, 16=64bit, 32/None=128bit).
        **kwargs: Keyword arguments to include in the hash.

    Returns:
        The resulting hexadecimal hash string.
    """
    hash_key = _key_base or ()
    if args: 
        hash_key += tuple(type(arg) for arg in args) if _typed else args
    if kwargs:
        if _exclude: kwargs = {k: v for k, v in kwargs.items() if k not in _exclude}
        if _exclude_none: kwargs = {k: v for k, v in kwargs.items() if v is not None}
        sorted_items = sorted(kwargs.items())
        for item in sorted_items:
            hash_key += item
    
    key = f'{_sep}'.join(str(k) for k in hash_key)
    return create_object_hash(key, _sep = _sep, _hash_length = _hash_length)


