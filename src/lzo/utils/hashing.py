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
    Creates a hash for the object

    obj:
        the object to hash
    _sep (str, optional):
        the separator to use for the hash
        Defaults to ':'.
    _hash_length (int, optional):
        the length of the hash
        Defaults to None.
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
    Creates a hash from the args and kwargs

    args:
        the args to hash
    _typed (bool, optional):
        if True, it will hash the args and kwargs as a typed hash
        if False, it will hash the args and kwargs as a non-typed hash
        Defaults to False.
    _key_base (tuple, optional):
        the base key to use for the hash
        Defaults to None.
    _exclude (List[str], optional):
        the keys to exclude from the hash
        Defaults to None.
    _exclude_none (bool, optional):
        if True, it will exclude any None values from the hash
        Defaults to True.
    _sep (str, optional):
        the separator to use for the hash
        Defaults to ':'.
    _hash_length (int, optional):
        the length of the hash
        Defaults to None.
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


