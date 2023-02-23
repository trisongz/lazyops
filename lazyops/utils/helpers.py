import time
import uuid
import typing
import random
import inspect
import functools
import datetime
import itertools
import asyncio
import contextlib
import async_lru

from frozendict import frozendict
from typing import Dict, Callable, List, Any, TYPE_CHECKING
from lazyops.utils.logs import default_logger

from lazyops.utils.serialization import (
    object_serializer, object_deserializer,
    ObjectEncoder, ObjectDecoder,
    Json,
)

if TYPE_CHECKING:
    from lazyops.types import BaseModel


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



def import_string(dotted_path: str) -> Any:
    """
    Taken from pydantic.utils.
    """
    from importlib import import_module

    try:
        module_path, class_name = dotted_path.strip(' ').rsplit('.', 1)
    except ValueError as e:
        raise ImportError(f'"{dotted_path}" doesn\'t look like a module path') from e

    module = import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as e:
        raise ImportError(f'Module "{module_path}" does not define a "{class_name}" attribute') from e


def fetch_property(
    obj: typing.Union[typing.Type['BaseModel'], Dict],
    key: str,
    default: typing.Optional[Any] = None
):  
    """
    Fetches a property from a dict or object
    """
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def create_unique_id(
    method: typing.Optional[str] = 'uuid4',
    alph_only: typing.Optional[bool] = False,
    length: typing.Optional[int] = None,
):
    """
    Creates a unique id
    args:
        method: uuid4, uuid1, uuid5, timestamp, secret
        alph_only: if True, returns a string of only alphabets
        length: if specified, returns a string of the specified length
    """
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

def create_timestamp(
    tz: typing.Optional[datetime.tzinfo] = datetime.timezone.utc,
    as_str: typing.Optional[bool] = False,
):
    """
    Creates a timestamp
    args:
        tz: timezone
        as_str: if True, returns a string
    """
    dt = datetime.datetime.now(tz =tz)
    return dt.isoformat() if as_str else dt

def create_secret(
    nbytes: typing.Optional[int] = 16,    
):
    import secrets
    return secrets.token_hex(nbytes)

@functools.lru_cache()
def import_function(func: typing.Union[str, Callable]) -> Callable:
    """
    Imports a function from a string
    """
    return func if callable(func) else import_string(func)

def suppress(
    *exceptions: typing.Optional[typing.Union[typing.Tuple[Exception], Exception]],
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

"""
Timed Caches
"""

def recursive_freeze(value):
    if not isinstance(value, dict):
        return value
    for k,v in value.items():
        value[k] = recursive_freeze(v)
    return frozendict(value)

# To unfreeze
def recursive_unfreeze(value):
    if isinstance(value, frozendict):
        value = dict(value)
        for k,v in value.items():
            value[k] = recursive_unfreeze(v)
    
    return value

def freeze_args_and_kwargs(*args, **kwargs):
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
):
    """
    Wrapper for creating a expiring cached function
    args:
        secs: number of seconds to cache the function
        maxsize: maxsize of the cache
        invalidate_cache_key: key to invalidate the cache
    """
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
                if _invalidate is True:
                    _wrapped.cache_invalidate(*args, **kwargs)
                # print(f'wrapped: {_wrapped.cache_info()}')
                return await _wrapped(*args, **kwargs)
            
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
                return func(*args, **kwargs)
            
            return wrapped_func

    return wrapper_cache
        
        

def lazy_function(
    validator: Callable,
    function: Callable,
    *args,
    **kwargs,
):
    """
    Creates an empty function wrapper
    args:
        validator: function to validate the arguments
        func: function to call
        
    """
    def wrapper_func(func):
        if not validator():
            return func
        
        if is_coro_func(func):
            @functools.wraps(func)
            async def wrapped_func(*args, **kwargs):
                return await function(*args, **kwargs)
        
        else:
            @functools.wraps(func)
            def wrapped_func(*args, **kwargs):
                return function(*args, **kwargs)
        return wrapped_func
    return wrapper_func









