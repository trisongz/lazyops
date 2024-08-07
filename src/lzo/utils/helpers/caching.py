from __future__ import annotations

"""
Caching Helpers
"""

import asyncio
import functools
import datetime
import typing
import contextlib
from lzl import load
from .dates import create_timestamp
from .base import is_coro_func
from typing import Callable, Dict, Any, Tuple, TypeVar, Generic, Iterable, List, Generator

if load.TYPE_CHECKING:
    import frozendict
    import async_lru
else:
    frozendict = load.LazyLoad("frozendict", install_missing=True)
    async_lru = load.LazyLoad("async_lru", install_missing=True)

def recursive_freeze(value):
    """
    Recursively freezes the object
    """
    if not isinstance(value, dict):
        return value
    for k,v in value.items():
        value[k] = recursive_freeze(v)
    return frozendict.frozendict(value)

# To unfreeze
def recursive_unfreeze(value):
    """
    Recursively unfreezes the object
    """
    if isinstance(value, frozendict.frozendict):
        value = dict(value)
        for k,v in value.items():
            value[k] = recursive_unfreeze(v)
    
    return value

def freeze_args_and_kwargs(*args, **kwargs):
    """
    Freezes the args and kwargs
    """
    args = tuple(
        recursive_freeze(arg) if isinstance(arg, dict) else arg
        for arg in args
    )
    kwargs = {k: recursive_freeze(v) if isinstance(v, dict) else v for k, v in kwargs.items()}
    return args, kwargs


def timed_cache(
    secs: typing.Optional[int] = 60 * 60, 
    maxsize: int = 1024,
    invalidate_cache_key: typing.Optional[str] = '_invalidate_cache',
    cache_if_result: typing.Optional[typing.Any] = None,
    cache_if_type: typing.Optional[typing.Type] = None,
    exclude_none: typing.Optional[bool] = False,
    **_kwargs,
):
    """
    Wrapper for creating a expiring cached function
    args:
        secs: number of seconds to cache the function
        maxsize: maxsize of the cache
        invalidate_cache_key: key to invalidate the cache
    """
    if 'ttl' in _kwargs: secs = _kwargs.pop('ttl')
    if secs is None: secs = 60
    def wrapper_cache(func):
        if is_coro_func(func):

            @async_lru.alru_cache(maxsize = maxsize, ttl = secs)
            async def _wrapped(*args, **kwargs):
                return await func(*args, **kwargs)
            
            @functools.wraps(func)
            async def wrapped_func(*args, **kwargs):
                _invalidate = kwargs.pop(invalidate_cache_key, None) if invalidate_cache_key else None
                args, kwargs = freeze_args_and_kwargs(*args, **kwargs)
                if _invalidate is True: _wrapped.cache_invalidate(*args, **kwargs)
                result = await _wrapped(*args, **kwargs)
                if exclude_none is True and result is None:
                    _wrapped.cache_invalidate(*args, **kwargs)
                elif cache_if_result is not None and result != cache_if_result:
                    _wrapped.cache_invalidate(*args, **kwargs)
                elif cache_if_type is not None and not isinstance(result, cache_if_type):
                    _wrapped.cache_invalidate(*args, **kwargs)
                    # print(f'Invalidating cache for {func.__name__}')
                return result
            
            return wrapped_func
        
        else:
            func = functools.lru_cache(maxsize=maxsize)(func)
            func.lifetime = datetime.timedelta(seconds=secs)
            func.expiration = create_timestamp() + func.lifetime
            def _check_cache(func, invalidate: typing.Optional[bool] = None):
                if invalidate is True or create_timestamp() >= func.expiration:
                    func.cache_clear()
                    func.expiration = create_timestamp() + func.lifetime
            
            @functools.wraps(func)
            def wrapped_func(*args, **kwargs):
                _check_cache(func, invalidate = kwargs.pop(invalidate_cache_key, None) if invalidate_cache_key else None)
                args, kwargs = freeze_args_and_kwargs(*args, **kwargs)
                result = func(*args, **kwargs)
                if exclude_none is True and result is None:
                    func.cache_clear()
                elif cache_if_result is not None and result != cache_if_result:
                    func.cache_clear()
                elif cache_if_type is not None and not isinstance(result, cache_if_type):
                    func.cache_clear()
                return result
            
            return wrapped_func

    return wrapper_cache


    

@timed_cache(secs = 60, cache_if_result = True)
def is_in_async_loop(*args, **kwargs) -> bool:
    """
    Returns whether the app is in an async loop
    """
    with contextlib.suppress(RuntimeError):
        asyncio.get_running_loop()
        return True
    return False