from __future__ import annotations

"""
Base Helpers
"""

import time
import random
import contextlib
import asyncio
import inspect
import functools
import importlib.util
import collections.abc
from typing import Callable, Dict, Any, Tuple, Optional, Union, Tuple, TYPE_CHECKING

def extract_function_kwargs(func: Callable[..., Any], **kwargs) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Returns the unused kwargs
    """
    func_kwargs = {
        k: v for k, v in kwargs.items() if k in func.__code__.co_varnames
    }
    extra_kwargs = {
        k: v for k, v in kwargs.items() if k not in func_kwargs
    }
    return func_kwargs, extra_kwargs

    # return {k: v for k, v in kwargs.items() if k not in func.__code__.co_varnames}


def is_coro_func(obj, func_name: str = None):
    """
    This is probably in the library elsewhere but returns bool
    based on if the function is a coro
    """
    try:
        if inspect.iscoroutinefunction(obj): return True
        if inspect.isawaitable(obj): return True
        if func_name and hasattr(obj, func_name) and inspect.iscoroutinefunction(getattr(obj, func_name)):
            return True
        return bool(hasattr(obj, '__call__') and inspect.iscoroutinefunction(obj.__call__))

    except Exception:
        return False


def exponential_backoff(
    attempts: int,
    base_delay: int = 1,
    max_delay: int = None,
    jitter: bool = True,
):
    """
    Get the next delay for retries in exponential backoff.

    attempts: Number of attempts so far
    base_delay: Base delay, in seconds
    max_delay: Max delay, in seconds. If None (default), there is no max.
    jitter: If True, add a random jitter to the delay
    """
    if max_delay is None:
        max_delay = float("inf")
    backoff = min(max_delay, base_delay * 2 ** max(attempts - 1, 0))
    if jitter:
        backoff = backoff * random.random()
    return backoff

def retryable(limit: int = 3, delay: int = 3):
    """
    Creates a retryable decorator
    """
    def decorator(func: Callable):
        if not inspect.iscoroutinefunction(func):
            def sync_wrapper(*args, **kwargs):
                for n in range(limit - 1):
                    with contextlib.suppress(Exception):
                        return func(*args, **kwargs)
                    time.sleep(exponential_backoff(n, base_delay=delay))
                return func(*args, **kwargs)
            return sync_wrapper
        else:
            async def async_wrapper(*args, **kwargs):
                for n in range(limit-1):
                    with contextlib.suppress(Exception):
                        return await func(*args, **kwargs)
                    await asyncio.sleep(exponential_backoff(n, base_delay=delay))
                return await func(*args, **kwargs)
            return async_wrapper
    return decorator


def suppress(
    *exceptions: Optional[Union[Tuple[Exception], Exception]],
):
    """
    Wrapper for suppressing exceptions
    args:
        exceptions: exceptions to suppress
    """
    if not exceptions: exceptions = (Exception,)
    def wrapper(func):
        if is_coro_func(func):
            @functools.wraps(func)
            async def wrapped_func(*args, **kwargs):
                with contextlib.suppress(*exceptions):
                    return await func(*args, **kwargs)
            return wrapped_func
        else:
            @functools.wraps(func)
            def wrapped_func(*args, **kwargs):
                with contextlib.suppress(*exceptions):
                    return func(*args, **kwargs)
        return wrapped_func
    return wrapper

def create_secret(
    nbytes: Optional[int] = 16,    
):
    """
    Generates a secret key
    """
    import secrets
    return secrets.token_hex(nbytes)


def create_unique_id(
    method: Optional[str] = 'uuid4',
    alph_only: Optional[bool] = False,
    length: Optional[int] = None,
):
    """
    Creates a unique id
    args:
        method: uuid4, uuid1, uuid5, timestamp, secret
        alph_only: if True, returns a string of only alphabets
        length: if specified, returns a string of the specified length
    """
    import uuid
    meth = getattr(uuid, method, None)
    if not meth:  raise ValueError(f'Invalid UUID method: {method}')
    val = str(meth())
    if alph_only: val = ''.join([c for c in val if c.isalpha()])
    if length:
        while len(val) < length:
            val += str(meth())
            if alph_only: val = ''.join([c for c in val if c.isalpha()])
            # remove trailing hyphen
            if val.endswith('-'): val = val[:-1]
        val = val[:length]
    return val

def fail_after(
    delay: Union[int, float] = 5.0,
):
    """
    Creates a fail after context
    """
    import concurrent.futures
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            p = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                f = p.submit(func, *args, **kwargs)
                return f.result(timeout = delay)
            except Exception as e:
                raise e
            finally:
                p.shutdown(wait = False, cancel_futures = True)
        return wrapper
    return decorator

    


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



def parse_deltas(deltas: dict) -> dict: # type: ignore
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
