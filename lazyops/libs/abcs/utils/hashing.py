from __future__ import annotations

"""
Commonly used hashing functions

- Requires `xxhash` and `cloudpickle`
"""

from lazyops.libs import lazyload
from pydantic import BaseModel
from typing import Any, Optional, Union, List, Dict, Set

if lazyload.TYPE_CHECKING:
    import xxhash
    import cloudpickle
else:
    xxhash = lazyload.LazyLoad("xxhash")
    cloudpickle = lazyload.LazyLoad("cloudpickle")

def create_string_for_kwargs(
    *args: Any,
    **kwargs: Any,
) -> str:
    """
    Creates a string for the kwargs
    """
    key = args or ()
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    sorted_items = sorted(kwargs.items())
    for item in sorted_items:
        key += item
    return ':'.join(str(k) for k in key)


def dump_object_to_dict(
    obj: Union['BaseModel', Dict[str, Any], List[Any], Any],
    mode: Optional[str] = 'json',
    exclude: Optional[Set] = None,
    exclude_none: Optional[bool] = True,
    exclude_unset: Optional[bool] = True,
    exclude_defaults: Optional[bool] = True,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Dumps the object to a dict
    """
    if isinstance(obj, list):
        return [dump_object_to_dict(item, mode = mode, exclude = exclude, exclude_none = exclude_none, exclude_unset = exclude_unset, exclude_defaults = exclude_defaults) for item in obj]

    if isinstance(obj, dict):
        if exclude_none: obj = {k: v for k, v in obj.items() if v is not None}
        return obj
    
    if isinstance(obj, BaseModel):
        exclude = exclude or set()
        for k in {
            'hashkeys',
            'hashkey',
            'hash',
        }:
            if hasattr(obj, k): exclude.add(k)
        exclude = exclude or None
        return obj.model_dump(mode = mode, exclude_none = exclude_none, exclude_unset = exclude_unset, exclude_defaults = exclude_defaults, exclude = exclude)
    raise ValueError(f'Unsupported object type: {type(obj)}')



def create_hash_from_key(key: str) -> str:
    """
    Generates a hash from a key
    """
    return xxhash.xxh3_128_hexdigest(key)


def create_hash_from_kwargs(
    *args: Any,
    **kwargs: Any,
) -> str:
    """
    Generates a hash from the kwargs
    """
    return create_hash_from_key(create_string_for_kwargs(*args, **kwargs))


def create_hash_from_object(
    obj: Union['BaseModel', Dict[str, Any], List[Any], Any],
    mode: Optional[str] = 'json',
    exclude: Optional[Set] = None,
    exclude_none: Optional[bool] = True,
    exclude_unset: Optional[bool] = True,
    exclude_defaults: Optional[bool] = True,
) -> str:
    """
    Generates a hash from an object
    """
    objs = dump_object_to_dict(obj, mode = mode, exclude = exclude, exclude_none = exclude_none, exclude_unset = exclude_unset, exclude_defaults = exclude_defaults)
    key = ()
    if not isinstance(objs, list): objs = [objs]
    for obj in objs:
        kwargs = {k: v for k, v in obj.items() if v is not None}
        sorted_items = sorted(kwargs.items())
        for item in sorted_items:
            key += item
    key = ':'.join(str(k) for k in key)
    return create_hash_from_key(key)

