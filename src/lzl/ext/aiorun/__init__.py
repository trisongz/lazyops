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
_finalize_hooks: t.Set[HookT] = set()
_added_tasks: t.Set[asyncio.Task] = set()

def add_init_hook(func: HookT | t.Sequence[HookT]):
    """
    Adds an init hook(s)
    """
    if isinstance(func, list): _init_hooks.update(func)
    else: _init_hooks.add(func)
        
def add_finalize_hook(func: HookT | t.Sequence[HookT]):
    """
    Adds a finalize hook(s)
    """
    if isinstance(func, list): _finalize_hooks.update(func)
    else: _finalize_hooks.add(func)

def create_task(coro: t.Callable[..., t.Awaitable[t.Any]] | t.Awaitable[t.Any], *args, _task_list: t.Optional[t.Set[asyncio.Task]] = None, _task_name: t.Optional[str] = None, **kwargs) -> asyncio.Task:
    """
    Adds a task to the finalize hooks
    """
    if not inspect.isawaitable(coro): coro = coro(*args, **kwargs)
    task = asyncio.create_task(coro, name = _task_name)
    _added_tasks.add(task)
    if _task_list is not None: 
        _task_list.add(task)
        task.add_done_callback(_task_list.discard)
    # Remove the task  from _added_tasks
    task.add_done_callback(_added_tasks.discard)
    return task

async def complete_added_tasks(task_list: t.Optional[t.Set[asyncio.Task]] = None):
    """
    Completes all current tasks
    """
    if task_list is not None: await asyncio.gather(*task_list)
    elif _added_tasks: await asyncio.gather(*_added_tasks)

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
    try:
        return await func if inspect.isawaitable(func) else await func(*args, **kwargs)
    finally:
        if _added_tasks: await asyncio.gather(*_added_tasks)
        for hook in _finalize_hooks:
            await hook(*args, **kwargs)
        

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


