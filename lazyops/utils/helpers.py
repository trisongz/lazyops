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
import signal


from frozendict import frozendict
from typing import Dict, Callable, List, Any, Union, Coroutine, TypeVar, TYPE_CHECKING
from lazyops.utils.logs import default_logger

from lazyops.utils.serialization import (
    object_serializer, object_deserializer,
    ObjectEncoder, ObjectDecoder,
    Json,
)

# For backwards compatibility
from lazyops.utils.lazy import (
    import_string,
    import_function, 
    get_obj_class_name,
    fetch_property,
    is_coro_func,
    lazy_function,
    lazy_import,
)

if TYPE_CHECKING:
    from lazyops.types import BaseModel


def timer(t: typing.Optional[float] = None, msg: typing.Optional[str] = None, logger = default_logger):
    if not t: return time.perf_counter()
    done_time = time.perf_counter() - t
    if msg: logger.info(f'{msg} in {done_time:.2f} secs')
    return done_time

# def timed(func: typing.Callable):
#     """
#     Decorator to time a function
#     """
#     _func_name = func.__name__
#     @functools.wraps(func)
#     async def fx(*args, **kwargs):
#         start = time.perf_counter()
#         if inspect.iscoroutinefunction(func): result = await func(*args, **kwargs)
#         else: result = func(*args, **kwargs)
#         end = time.perf_counter()
#         default_logger.info(f'{_func_name}: {end - start:.4f} secs')
#         return result
#     return fx


def timed(verbose: typing.Optional[bool] = False):
    """
    Decorator to time a function
    """
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                start = time.perf_counter()
                result = await func(*args, **kwargs)
                end = time.perf_counter()
                if verbose: default_logger.info(f"took {end - start:.2f} secs with args: {args} and kwargs: {kwargs}", prefix = f"{func.__module__}.|g|{func.__name__}|e|", colored = True)
                else: default_logger.info(f"took {end - start:.2f} secs", prefix = f"{func.__module__}.|g|{func.__name__}|e|", colored = True)
                return result
            return wrapper
        
        else:        
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                result = func(*args, **kwargs)
                end = time.perf_counter()
                if verbose: default_logger.info(f"took {end - start:.2f} secs with args: {args} and kwargs: {kwargs}", prefix = f"{func.__module__}.|g|{func.__name__}|e|", colored = True)
                else: default_logger.info(f"took {end - start:.2f} secs", prefix = f"{func.__module__}.|g|{func.__name__}|e|", colored = True)
                return result
            return wrapper
    
    return decorator


def merge_dicts(x: Dict, y: Dict):
    z = x.copy()
    z.update(y)
    return z

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


T = TypeVar('T')

def get_batches_from_generator(iterable: typing.Iterable[T], n: int) -> typing.Generator[typing.List[T], None, None]:
    """
    Batch elements of an iterable into fixed-length chunks or blocks.
    """
    it = iter(iterable)
    while x := tuple(itertools.islice(it, n)):
        yield x

def split_into_batches(items: List[T], n: int) -> typing.Iterable[typing.List[T]]:
    """
    Splits the items into n amount of equal items

    >>> list(split_into_batches(range(11), 3))
    [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10]]
    """
    n = min(n, len(items))
    k, m = divmod(len(items), n)
    return (items[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))

def split_into_batches_of_n(iterable: typing.Iterable[T], n: int) -> typing.Iterable[typing.List[T]]:
    """
    Splits the items into fixed-length chunks or blocks.

    >>> list(split_into_batches_of_n(range(11), 3))
    [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10]]
    """
    return list(get_batches_from_generator(iterable, n))


def split_into_n_batches(iterable: typing.Iterable[T], size: int) -> typing.Iterable[typing.List[T]]:
    """
    Splits the items into n amount of equal items

    >>> list(split_into_batches_of_size(range(11), 3))
    [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10]]
    """
    return split_into_batches(iterable, size)

def build_batches(iterable: typing.Iterable[T], size: int, fixed_batch_size: bool = True) -> typing.Iterable[typing.List[T]]:
    """
    Builds batches of a given size from an iterable.
    """
    if fixed_batch_size:
        return split_into_batches_of_n(iterable, size)
    return split_into_n_batches(iterable, size)



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
        


def with_fail_after(delay: float):
    """
    Creates a timeout for a function
    """

    def wrapper(func):
        @functools.wraps(func)
        def time_limited(*args, **kwargs):
            # Register an handler for the timeout
            def handler(signum, frame):
                raise TimeoutError(f"Timeout for function '{func.__name__}'")

            # Register the signal function handler
            signal.signal(signal.SIGALRM, handler)

            # Define a timeout for your function
            signal.alarm(delay)

            result = None
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                raise exc
            finally:
                # disable the signal alarm
                signal.alarm(0)

            return result

        return time_limited
    return wrapper


@contextlib.contextmanager
def fail_after(delay: Union[int, float]):
    """
    Creates a timeout for a function
    """
    def signal_handler(signum, frame):
        raise TimeoutError(f"Timed out after {delay}s")
    signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(int(delay))
    try:
        yield
    finally:
        signal.alarm(0)


async def run_as_coro(
    func: Callable,
    *args,
    **kwargs
) -> Any:
    """
    Runs a function as a coroutine
    """
    from .pooler import ThreadPooler
    try:
        return await ThreadPooler.asyncish(func, *args, **kwargs)
    except Exception as e:
        default_logger.trace(f'Error running as coro', error = e)
        raise e


_background_tasks = set()


def create_background_task(func: Union[Callable, Coroutine], *args, **kwargs):
    """
    Creates a background task and adds it to the global set of background tasks
    """
    if inspect.isawaitable(func):
        task = asyncio.create_task(func)
    else:
        task = asyncio.create_task(
            run_as_coro(
                func,
                *args,
                **kwargs
            )
        )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task

