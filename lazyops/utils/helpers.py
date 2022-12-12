import time 
import typing
import random
import json
import inspect
import functools
import itertools
import asyncio
import datetime
import dataclasses
import contextlib
from typing import Dict, Callable, List, Any
from lazyops.utils.logs import default_logger


try:
    import numpy as np
except ImportError:
    np = None


def timer(t: typing.Optional[float] = None, msg: typing.Optional[str] = None, logger = default_logger):
    if not t: return time.perf_counter()
    done_time = time.perf_counter() - t
    if msg: logger.info(f'{msg} in {done_time:.2f} secs')
    return done_time

def timed(func: typing.Callable):
    """
    Decorator to time a function
    """
    _func_name = func.__name__
    @functools.wraps(func)
    async def fx(*args, **kwargs):
        start = time.perf_counter()
        if inspect.iscoroutinefunction(func): result = await func(*args, **kwargs)
        else: result = func(*args, **kwargs)
        end = time.perf_counter()
        default_logger.info(f'{_func_name}: {end - start:.4f} secs')
        return result
    return fx


def merge_dicts(x: Dict, y: Dict):
    z = x.copy()
    z.update(y)
    return z

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



def get_batches_from_generator(iterable, n):
    """
    Batch elements of an iterable into fixed-length chunks or blocks.
    """
    it = iter(iterable)
    x = tuple(itertools.islice(it, n))
    while x:
        yield x
        x = tuple(itertools.islice(it, n))


def split_into_batches(items: List[Any], n: int):
    """
    Splits the items into n amount of equal items

    >>> list(split_into_batches(range(11), 3))
    [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10]]
    """
    n = min(n, len(items))
    k, m = divmod(len(items), n)
    return (items[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))


def object_serializer(obj: typing.Any) -> typing.Any:
    if isinstance(obj, dict):
        return {k: object_serializer(v) for k, v in obj.items()}

    if isinstance(obj, bytes):
        return obj.decode('utf-8')

    if isinstance(obj, (str, list, dict, int, float, bool, type(None))):
        return obj

    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)

    if hasattr(obj, 'dict'): # test for pydantic models
        return obj.dict()
    
    if hasattr(obj, 'get_secret_value'):
        return obj.get_secret_value()
    
    if hasattr(obj, 'as_posix'):
        return obj.as_posix()
    
    if hasattr(obj, "numpy"):  # Checks for TF tensors without needing the import
        return obj.numpy().tolist()
    
    if hasattr(obj, 'tolist'): # Checks for torch tensors without importing
        return obj.tolist()
    
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    
    if np is not None:
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(obj)
        
        if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        
    else:
        # Try to convert to a primitive type
        with contextlib.suppress(Exception):
            return int(obj)
        with contextlib.suppress(Exception):
            return float(obj)

    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class ObjectEncoder(json.JSONEncoder):
    
    def default(self, obj: typing.Any):   # pylint: disable=arguments-differ,method-hidden
        with contextlib.suppress(Exception):
            return object_serializer(obj)
        return json.JSONEncoder.default(self, obj)