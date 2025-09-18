from __future__ import annotations

"""
Base Helpers
"""

import asyncio
import collections.abc
import contextlib
import functools
import importlib.util
import inspect
import pathlib
import random
import string
import time
import typing as t

def extract_function_kwargs(
    func: t.Callable[..., t.Any],
    **kwargs: t.Any,
) -> t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]:
    """Split ``kwargs`` into arguments accepted by ``func`` and leftovers."""

    func_kwargs = {k: v for k, v in kwargs.items() if k in func.__code__.co_varnames}
    extra_kwargs = {k: v for k, v in kwargs.items() if k not in func_kwargs}
    return func_kwargs, extra_kwargs

    # return {k: v for k, v in kwargs.items() if k not in func.__code__.co_varnames}


def is_coro_func(obj: t.Any, func_name: t.Optional[str] = None) -> bool:
    """Return ``True`` when ``obj`` or ``obj.func_name`` is awaitable."""
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
    max_delay: t.Optional[int] = None,
    jitter: bool = True,
) -> float:
    """Compute an exponentially increasing delay for retry loops."""
    if max_delay is None:
        max_delay = float("inf")
    backoff = min(max_delay, base_delay * 2 ** max(attempts - 1, 0))
    if jitter:
        backoff = backoff * random.random()
    return backoff

def retryable(limit: int = 3, delay: int = 3) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """Wrap a callable to retry transient failures with exponential backoff."""

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if not inspect.iscoroutinefunction(func):

            def sync_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
                for n in range(limit - 1):
                    with contextlib.suppress(Exception):
                        return func(*args, **kwargs)
                    time.sleep(exponential_backoff(n, base_delay=delay))
                return func(*args, **kwargs)

            return sync_wrapper

        async def async_wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            for n in range(limit - 1):
                with contextlib.suppress(Exception):
                    return await func(*args, **kwargs)
                await asyncio.sleep(exponential_backoff(n, base_delay=delay))
            return await func(*args, **kwargs)

        return async_wrapper

    return decorator


def suppress(*exceptions: t.Optional[t.Union[t.Tuple[Exception, ...], Exception]]) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """Decorator factory mirroring :func:`contextlib.suppress` for callables."""

    if not exceptions:
        exceptions = (Exception,)

    def wrapper(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if is_coro_func(func):

            @functools.wraps(func)
            async def wrapped_func(*args: t.Any, **kwargs: t.Any) -> t.Any:
                with contextlib.suppress(*exceptions):
                    return await func(*args, **kwargs)

            return wrapped_func

        @functools.wraps(func)
        def wrapped_func(*args: t.Any, **kwargs: t.Any) -> t.Any:
            with contextlib.suppress(*exceptions):
                return func(*args, **kwargs)

        return wrapped_func

    return wrapper

def create_secret(nbytes: t.Optional[int] = 16) -> str:
    """Generate a hexadecimal token using ``secrets.token_hex``."""

    import secrets

    return secrets.token_hex(nbytes)


def create_unique_id(
    method: t.Optional[str] = 'uuid4',
    alph_only: bool = False,
    length: t.Optional[int] = None,
) -> str:
    """Generate a UUID-based identifier with optional filtering/truncation."""

    import uuid

    meth = getattr(uuid, method, None)
    if not meth:
        raise ValueError(f'Invalid UUID method: {method}')
    val = str(meth())
    if alph_only:
        val = ''.join(c for c in val if c.isalpha())
    if length:
        while len(val) < length:
            val += str(meth())
            if alph_only:
                val = ''.join(c for c in val if c.isalpha())
            if val.endswith('-'):
                val = val[:-1]
        val = val[:length]
    return val

ALPHA = string.ascii_letters

def create_unique_secret_key(length: int = 44) -> str:
    """Return an uppercase alphanumeric key suitable for shared secrets."""

    return ''.join(random.choice(ALPHA) for _ in range(length)).upper()


def fail_after(delay: t.Union[int, float] = 5.0) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """Raise a timeout if ``func`` does not finish within ``delay`` seconds."""

    import concurrent.futures

    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        @functools.wraps(func)
        def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = executor.submit(func, *args, **kwargs)
                return future.result(timeout=delay)
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        return wrapper

    return decorator

    


def update_dict(
    d: t.Dict[t.Hashable, t.Any],
    u: t.Mapping[t.Hashable, t.Any],
    exclude_none: bool = False,
    unset_value: t.Optional[str] = 'UNSET',
) -> t.Dict[t.Hashable, t.Any]:
    """Recursively update a dictionary, respecting unset sentinels."""
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
    d: t.Mapping[str, t.Any],
    current_key: str,
) -> t.Dict[str, t.Any]:
    """Flatten nested dictionaries into dotted-key mappings."""
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
    d: t.Mapping[str, t.Any],
    parent_key: str = '',
) -> t.Dict[str, t.Any]:
    """Return a flattened dictionary where keys are joined by ``.``."""

    items: t.List[t.Tuple[str, t.Any]] = []
    for k, v in d.items():
        new_key = f'{parent_key}.{k}' if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict_value(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)



# https://stackoverflow.com/questions/27265939/comparing-python-dictionaries-and-nested-dictionaries



def parse_deltas(deltas: t.Mapping[str, t.Tuple[t.Any, t.Any]]) -> t.Dict[str, t.Any]:
    """Normalise nested diff output into a flat mapping."""

    res: t.Dict[str, t.Any] = {}
    for k, v in deltas.items():
        if isinstance(v[0], dict):
            tmp = diff_dict(v[0], v[1])
            if tmp:
                res[k] = tmp
        else:
            res[k] = v[1]
    return res

def diff_dict(d1: t.Mapping[str, t.Any], d2: t.Mapping[str, t.Any]) -> t.Dict[str, t.Any]:
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



@functools.lru_cache()
def get_module_path(
    module_name: str, 
    **kwargs
) -> pathlib.Path:
    """Locate the filesystem path for ``module_name`` using import metadata."""

    module_spec = importlib.util.find_spec(module_name)
    if not module_spec:
        raise ValueError(f"Module {module_name} not found")

    for path in module_spec.submodule_search_locations:
        module_path = pathlib.Path(path)
        if module_path.exists(): return module_path
    
    raise ValueError(f"Module {module_name} cant be found in the path")
