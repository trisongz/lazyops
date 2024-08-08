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

def create_object_hash(obj: ObjT) -> str:
    """
    Creates a hash for the object
    """
    if isinstance(obj, dict):
        return xxhash.xxh3_128_hexdigest(str(obj))
    if isinstance(obj, (list, tuple, set)):
        return ':'.join(create_object_hash(item) for item in obj)
    if isinstance(obj, BaseModel) or hasattr(obj, "model_dump"):
        return xxhash.xxh3_128_hexdigest(obj.model_dump_json(exclude_none=True))
    return xxhash.xxh3_128_hexdigest(str(obj))

def create_hash_from_args_and_kwargs(
    *args,
    **kwargs,
) -> str:
    """
    Creates a hash from the args and kwargs
    """
    key = args or ()
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    sorted_items = sorted(kwargs.items())
    for item in sorted_items:
        key += item
    key = ':'.join(str(k) for k in key)
    return create_object_hash(key)


