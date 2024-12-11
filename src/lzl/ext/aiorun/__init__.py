from __future__ import annotations

"""
A super simple wrapper for `asyncio.run` or `anyio.run`
that also handles adding in hooks
"""
import inspect
import asyncio
import functools
import typing as t

try:
    import anyio
    _has_anyio = True
except ImportError:
    _has_anyio = False

HookT = t.Callable[[], t.Awaitable[None]]
_init_hooks: t.Set[HookT] = set()

def add_init_hook(func: HookT | t.Sequence[HookT]):
    """
    Adds an init hook(s)
    """
    if isinstance(func, list): _init_hooks.update(func)
    else: _init_hooks.add(func)

async def runtime(
    func: t.Callable[..., t.Awaitable[t.Any]] | t.Awaitable[t.Any],
    *args,
    **kwargs,
):
    """
    Runs the function with the runtime
    """
    for hook in _init_hooks:
        await hook(*args, **kwargs)
    return await func if inspect.isawaitable(func) else await func(*args, **kwargs)

def run(
    func: t.Callable[..., t.Awaitable[t.Any]] | t.Awaitable[t.Any],
    *args,
    _runtime: t.Optional[t.Literal['asyncio', 'anyio']] = None,
    **kwargs,
):
    """
    Runs the function with the runtime
    """
    if _runtime is None:
        _runtime = 'anyio' if _has_anyio else 'asyncio'
    if _runtime == 'asyncio':
        return asyncio.run(runtime(func, *args, **kwargs))
    if _runtime == 'anyio':
        func_partial = functools.partial(runtime, func, *args, **kwargs)
        return anyio.run(func_partial)
    raise ValueError(f'Invalid Runtime: {_runtime}')


