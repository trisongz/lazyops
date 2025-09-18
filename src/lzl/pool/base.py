from __future__ import annotations

"""Thread and coroutine interop helpers backing LazyOps utilities."""

import os
import abc
import sys
# import anyio
import inspect
import asyncio
import shlex
import functools
import subprocess
import contextvars
import contextlib
# import anyio.from_thread
import typing as t
from concurrent import futures
# from anyio._core._eventloop import threadlocals
from lzl.proxied import proxied
from lzl import load
from typing import Callable, Coroutine, Any, Union, List, Set, Tuple, TypeVar, Optional, Generator, Awaitable, Iterable, AsyncGenerator, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    import anyio
    import anyio.from_thread
    import anyio._core._eventloop

else:
    anyio = load.lazy_load("anyio")


if sys.version_info < (3, 10):
    # Add aiter and anext to asyncio
    def aiter(it: AsyncIterable) -> Any:
        return it.__aiter__()
    
    def anext(it: AsyncIterator) -> Any:
        return it.__anext__()
    


RT = TypeVar("RT")
_concurrency_limit: Optional[int] = None

def set_concurrency_limit(
    limit: Optional[int] = None
):
    """Override the maximum number of concurrently scheduled background tasks.

    When ``limit`` is ``None`` the value falls back to ``os.cpu_count() * 4``
    for parity with the original implementation.
    """
    global _concurrency_limit
    if limit is None: limit = os.cpu_count() * 4
    _concurrency_limit = limit

def get_concurrency_limit() -> Optional[int]:
    """Return the currently configured concurrency limit."""
    global _concurrency_limit
    if _concurrency_limit is None: set_concurrency_limit()
    return _concurrency_limit


def is_coro_func(obj, func_name: str = None) -> bool:
    """Return ``True`` when ``obj`` (or ``obj.func_name``) is awaitable."""
    try:
        if inspect.iscoroutinefunction(obj): return True
        if inspect.isawaitable(obj): return True
        if func_name and hasattr(obj, func_name) and inspect.iscoroutinefunction(getattr(obj, func_name)):
            return True
        return bool(hasattr(obj, '__call__') and inspect.iscoroutinefunction(obj.__call__))

    except Exception:
        return False


async def amap_iterable(
    mapped_iterable: Union[Callable[[], Awaitable[Any]], Awaitable[Any], Coroutine[Any, Any, Any], Callable[[], Any]],
    concurrency_limit: Optional[int] = None,
    return_when: Optional[str] = 'FIRST_COMPLETED',
):
    """Yield tasks from ``mapped_iterable`` while respecting ``concurrency_limit``."""
    try:
        iterable = aiter(mapped_iterable)
        is_async = True
    except (TypeError, AttributeError):
        iterable = iter(mapped_iterable)
        is_async = False
    
    iterable_ended: bool = False
    pending = set()
    concurrency_limit = get_concurrency_limit() if concurrency_limit is None else concurrency_limit
    return_when = getattr(asyncio, return_when) if isinstance(return_when, str) else return_when

    while pending or not iterable_ended:
        while len(pending) < concurrency_limit and not iterable_ended:
            try: iter_item = await anext(iterable) if is_async else next(iterable)
            except StopAsyncIteration if is_async else StopIteration:
                iterable_ended = True
            else: pending.add(asyncio.ensure_future(iter_item))

        if not pending: return
        done, pending = await asyncio.wait(pending,  return_when = return_when)
        while done: yield done.pop()



async def async_map(
    func: Callable[..., Awaitable[Any]],
    iterable: Iterable[Any], 
    *args,
    limit: Optional[int] = None,
    return_when: Optional[str] = 'FIRST_COMPLETED',
    **kwargs,
) -> AsyncGenerator[RT, None]:
    """Yield results from applying ``func`` to ``iterable`` as tasks complete."""
    func = ensure_coro(func)
    partial = functools.partial(func, *args, **kwargs)
    try:
        mapped_iterable = map(partial, iterable)
    except TypeError:
        mapped_iterable = (partial(x) async for x in iterable)
    async for task in amap_iterable(mapped_iterable, limit = limit, return_when = return_when):
        yield await task


async def _read_stream(stream: asyncio.streams.StreamReader, cb: t.Optional[t.Union[t.Callable, t.Awaitable]]):  
    """
    Read from the stream
    """
    if cb is None: return
    _is_coro = is_coro_func(cb)
    while True:
        line = await stream.readline()
        if line:
            await cb(line) if _is_coro else cb(line)
        else:
            break


async def _stream_subprocess(
    cmd: Union[str, List[str]], 
    stdout_cb: t.Union[t.Callable, t.Awaitable], 
    stderr_cb: t.Optional[t.Union[t.Callable, t.Awaitable]] = None,
    **kwargs 
):  
    """
    Streams the Subprocess Output into the Callbacks
    """
    # https://stackoverflow.com/questions/65649412/getting-live-output-from-asyncio-subprocess
    if isinstance(cmd, str): cmd = shlex.split(cmd)
    process = await asyncio.create_subprocess_exec(*cmd,
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE,
        **kwargs
    )
    await asyncio.gather(
        _read_stream(process.stdout, stdout_cb),
        _read_stream(process.stderr, stderr_cb)
    )
    return await process.wait()



@proxied
class ThreadPool(abc.ABC):
    """Singleton-style proxy wrapping LazyOps thread/process pools."""

    allow_task_completion: Optional[bool] = True
    register_exit: Optional[bool] = True

    def __init__(
        self,
        max_workers: Optional[int] = None,
        allow_task_completion: Optional[bool] = None,
        register_exit: Optional[bool] = None,
        **kwargs
    ):
        """Initialise backing executors and configure automatic shutdown hooks."""
        if allow_task_completion is not None: self.allow_task_completion = allow_task_completion
        if register_exit is not None: self.register_exit = register_exit
        if max_workers is None:
            max_workers = int(os.getenv("MAX_WORKERS", os.cpu_count()))
        
        self.max_workers = max_workers
        self.tasks: Optional[Set[asyncio.Task]] = set()
        self._pool: Optional[futures.ThreadPoolExecutor] = None
        self._ppool: Optional[futures.ProcessPoolExecutor] = None
        
        self._kwargs = kwargs
        if self.register_exit:
            import atexit
            atexit.register(self.on_exit)

    @staticmethod
    def is_coro(obj: Any) -> bool:
        """Return ``True`` when ``obj`` is a coroutine function or awaitable."""
        return is_coro_func(obj)
    
    def ensure_coro(self, func: Callable[..., RT]) -> Callable[..., Awaitable[RT]]:
        """Return an awaitable wrapper around ``func`` when it is sync."""
        if asyncio.iscoroutinefunction(func): return func
        @functools.wraps(func)
        async def inner(*args, **kwargs):
            return await self.arun(func, *args, **kwargs)
        return inner
    
    def ensure_coro_function(self, func: Callable[..., RT]) -> Callable[..., Awaitable[RT]]:
        """Return an awaitable wrapper preserving context variables."""
        if asyncio.iscoroutinefunction(func): return func
        @functools.wraps(func)
        async def inner(*args, **kwargs):
            loop = asyncio.get_running_loop()
            ctx = contextvars.copy_context()
            return await loop.run_in_executor(
                executor = self.pool, 
                func = lambda: ctx.run(func, *args, **kwargs)
            )
        return inner
    
    @property
    def pool(self) -> futures.ThreadPoolExecutor:
        """Return (and lazily create) the shared thread pool executor."""
        if self._pool is None:
            self._pool = futures.ThreadPoolExecutor(max_workers = self.max_workers)
        return self._pool
    
    @property
    def ppool(self) -> futures.ProcessPoolExecutor:
        """Return (and lazily create) the shared process pool executor."""
        if self._ppool is None:
            self._ppool = futures.ProcessPoolExecutor(max_workers = self.max_workers)
        return self._ppool
    
    @property
    def in_async_loop(self) -> bool:
        """Return ``True`` when executed inside a running event loop."""
        try:
            return asyncio.get_running_loop() is not None
        except RuntimeError:
            return False
    
    def get_pool(
        self, 
        num_workers: Optional[int] = None, 
        process_pool: bool = False
    ) -> futures.Executor:
        """Create a dedicated executor honouring ``num_workers`` preferences."""
        pool_cls = futures.ProcessPoolExecutor if process_pool else futures.ThreadPoolExecutor
        if num_workers is None: num_workers = self.max_workers
        return pool_cls(max_workers = num_workers)

    def add_task(
        self, 
        task: asyncio.Task, 
        callback: Optional[Callable] = None,
        callback_args: Optional[Tuple] = None,
        callback_kwargs: Optional[Dict] = None
    ):
        """Track ``task`` and optionally invoke ``callback`` when it completes."""
        self.tasks.add(task)
        if callback is not None:
            if callback_args or callback_kwargs:
                callback_args = callback_args or ()
                callback_kwargs = callback_kwargs or {}
                callback = functools.partial(callback, *callback_args, **callback_kwargs)
            task.add_done_callback(callback)
        task.add_done_callback(self.tasks.discard)


    def on_exit(self):
        """Cancel tracked tasks and shut down executors at interpreter exit."""
        for task in self.tasks:
            with contextlib.suppress(Exception):
                task.cancel()
        with contextlib.suppress(Exception):
            if self._pool is not None: self._pool.shutdown(wait = self.allow_task_completion, cancel_futures = not self.allow_task_completion)
        with contextlib.suppress(Exception):
            if self._ppool is not None: self._ppool.shutdown(wait = self.allow_task_completion, cancel_futures = not self.allow_task_completion)

    """
    Core
    """

    def run(self, func: Coroutine[RT], *args, **kwargs) -> RT:
        """Execute ``func`` synchronously, bridging any active AnyIO loop."""
        current_async_module = getattr(anyio._core._eventloop.threadlocals, "current_async_module", None)
        partial_f = functools.partial(func, *args, **kwargs)
        if current_async_module is None:
            return anyio.run(partial_f)
        return anyio.from_thread.run(partial_f)
    

    async def arun(self, func: Callable[..., RT], *args, **kwargs) -> RT:
        """Execute ``func`` in the shared thread pool and await the result."""
        blocking = functools.partial(func, *args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.pool, blocking)
    
    async def asyncish(self, func: Callable[..., RT], *args, **kwargs) -> RT:
        """Await ``func`` when async, otherwise delegate to :meth:`arun`."""
        if is_coro_func(func): return await func(*args, **kwargs)
        return await self.arun(func, *args, **kwargs)
    
    run_async = arun
    run_sync = run

    """
    Background Tasks
    """    

    def threadpool_task(
        self, 
        func: Callable, 
        *args, 
        task_callback: Optional[Callable[..., RT]] = None, 
        task_callback_args: Optional[Tuple] = None,
        task_callback_kwargs: Optional[Dict] = None,
        **kwargs
    ) -> futures.Future[RT]:
        """Submit ``func`` to the thread pool and return the future."""
        task = self.pool.submit(func, *args, **kwargs)
        self.add_task(task, task_callback, callback_args=task_callback_args, callback_kwargs=task_callback_kwargs)
        return task

    def background_task(
        self, 
        func: Callable[..., RT],
        *args, 
        task_callback: Optional[Callable] = None, 
        task_callback_args: Optional[Tuple] = None,
        task_callback_kwargs: Optional[Dict] = None,
        **kwargs
    ) -> Awaitable[RT]:
        """Schedule ``func`` in the appropriate executor based on loop state."""
        if inspect.isawaitable(func): task = asyncio.create_task(func)
        else: task = asyncio.create_task(self.asyncish(func, *args, **kwargs))
        self.add_task(task, task_callback, callback_args = task_callback_args, callback_kwargs=task_callback_kwargs)
        return task
    
    def background(
        self, 
        func: Callable[..., RT], 
        *args, 
        task_callback: Optional[Callable] = None, 
        task_callback_args: Optional[Tuple] = None,
        task_callback_kwargs: Optional[Dict] = None,
        **kwargs
    ) -> Awaitable[RT]:
        """
        Runs a function in the background.
        If the current thread is in an async loop, it runs the function as an async function.
        Otherwise, it runs the function as a sync function in the threadpool.

        Returns a `asyncio.Task` if the current thread is in an async loop.
        Otherwise, it returns a `futures.Future`.
        """
        method = self.background_task if self.in_async_loop else self.threadpool_task
        return method(func, *args, task_callback = task_callback, task_callback_args = task_callback_args, task_callback_kwargs = task_callback_kwargs, **kwargs)

    create_threadpool_task = threadpool_task
    create_background_task = background_task
    create_background = background

    """
    Iterators
    """

    def map(
        self,
        func: Callable[..., RT],
        iterable: Iterable[Any],
        *args,
        return_ordered: Optional[bool] = True,
        use_process_pool: Optional[bool] = False, 
        **kwargs
    ) -> List[RT]:  # sourcery skip: assign-if-exp
        """Return the results of applying ``func`` across ``iterable``."""
        num_workers = kwargs.pop('num_workers', None)
        partial_func = functools.partial(func, *args, **kwargs)
        with self.get_pool(num_workers = num_workers, process_pool = use_process_pool) as executor:
            _futures = [
                executor.submit(partial_func, item) for item in iterable
            ]
            if not return_ordered: return [f.result() for f in futures.as_completed(_futures)]
            futures.wait(_futures)
            return [f.result() for f in _futures]
    

    def iterate(
        self,
        func: Callable[..., RT],
        iterable: Iterable[Any],
        *args,
        use_process_pool: Optional[bool] = False, 
        return_ordered: Optional[bool] = True,
        **kwargs
    ) -> Generator[RT, None, None]:  # sourcery skip: assign-if-exp
        """Yield items produced by applying ``func`` across ``iterable``."""
        num_workers = kwargs.pop('num_workers', None)
        partial_func = functools.partial(func, *args, **kwargs)
        with self.get_pool(num_workers = num_workers, process_pool = use_process_pool) as executor:
            _futures = [
                executor.submit(partial_func, item) for item in iterable
            ]
            if not return_ordered:
                for f in futures.as_completed(_futures):
                    yield f.result()
            else:
                futures.wait(_futures)
                for f in _futures:
                    yield f.result()
    
    async def amap(
        self,
        func: Callable[..., Awaitable[RT]],
        iterable: Iterable[Any], 
        *args,
        return_ordered: Optional[bool] = True,
        concurrency_limit: Optional[int] = None,
        **kwargs,
    ) -> List[RT]:
        """Await results serially while respecting the concurrency limit."""
        return_when = kwargs.pop('return_when', 'ALL_COMPLETED' if return_ordered else 'FIRST_COMPLETED')
        concurrency_limit = kwargs.pop('limit', concurrency_limit)
        func = self.ensure_coro(func)
        partial = functools.partial(func, *args, **kwargs)
        try: mapped_iterable = map(partial, iterable)
        except TypeError: mapped_iterable = (partial(x) async for x in iterable)
        results = []
        async for result in amap_iterable(
            mapped_iterable, 
            return_when = return_when, 
            concurrency_limit = concurrency_limit
        ):
            results.append(await result)
        return results
    
    async def aiterate(
        self,
        func: Callable[..., Awaitable[RT]],
        iterable: Iterable[Any], 
        *args,
        return_ordered: Optional[bool] = True,
        concurrency_limit: Optional[int] = None,
        **kwargs,
    ) -> AsyncGenerator[RT, None]:
        """Async generator yielding results as soon as underlying tasks finish."""
        return_when = kwargs.pop('return_when', 'ALL_COMPLETED' if return_ordered else 'FIRST_COMPLETED')
        concurrency_limit = kwargs.pop('limit', concurrency_limit)
        func = self.ensure_coro(func)
        partial = functools.partial(func, *args, **kwargs)
        try: mapped_iterable = map(partial, iterable)
        except TypeError: mapped_iterable = (partial(x) async for x in iterable)
        async for result in amap_iterable(
            mapped_iterable, 
            return_when = return_when, 
            concurrency_limit = concurrency_limit
        ):
            yield await result
    
    sync_map = map
    sync_iterate = iterate
    async_map = amap
    async_iterate = aiterate

    """
    CMD
    """

    @staticmethod
    def cmd(
        command: Union[List[str], str], 
        shell: bool = True, 
        raise_error: bool = True, 
        **kwargs
    ):
        if isinstance(command, list): command = " ".join(command)
        try:
            out = subprocess.check_output(command, shell=shell, **kwargs)
            if isinstance(out, bytes): out = out.decode('utf8')
            return out.strip()
        except Exception as e:
            if not raise_error: return ""
            raise e
    
    @staticmethod
    async def acmd(
        command: Union[str, List[str]], 
        output_only: bool = True, 
        stdout = asyncio.subprocess.PIPE, 
        stderr = asyncio.subprocess.PIPE, 
        output_encoding: str = 'UTF-8', 
        output_errors: str = 'ignore', 
        *args,
        **kwargs
    ) -> Union[str, asyncio.subprocess.Process]:
        """Execute a shell command asynchronously, optionally returning stdout."""
        if isinstance(command, list): command = ' '.join(command)
        p = await asyncio.subprocess.create_subprocess_shell(command, *args, stdout = stdout, stderr = stderr, **kwargs)
        if not output_only: return p
        stdout, _ = await p.communicate()
        return stdout.decode(encoding = output_encoding, errors = output_errors).strip()
    
    run_command = cmd
    async_run_command = acmd


    @staticmethod
    async def acmd_exec(
        command: Union[str, List[str]], 
        output_only: bool = True, 
        stdout = asyncio.subprocess.PIPE, 
        stderr = asyncio.subprocess.PIPE, 
        output_encoding: str = 'UTF-8', 
        output_errors: str = 'ignore', 
        **kwargs
    ) -> Union[str, asyncio.subprocess.Process]:
        """Execute a command using ``create_subprocess_exec`` and return stdout when requested."""
        if isinstance(command, str): command = shlex.split(command)
        p = await asyncio.subprocess.create_subprocess_exec(*command, stdout = stdout, stderr = stderr, **kwargs)
        if not output_only: return p
        stdout, _ = await p.communicate()
        return stdout.decode(encoding = output_encoding, errors = output_errors).strip()
    
    @staticmethod
    async def acmd_stream(
        command: Union[str, List[str]], 
        stdout_cb: t.Union[t.Callable, t.Awaitable], 
        stderr_cb: t.Optional[t.Union[t.Callable, t.Awaitable]] = None,
        **kwargs 
    ) -> asyncio.subprocess.Process:
        """Stream subprocess output into the supplied callbacks."""
        return await _stream_subprocess(command, stdout_cb, stderr_cb, **kwargs)
    


def ensure_coro(
    func: Callable[..., Any]
) -> Callable[..., Awaitable[Any]]:
    """Return an awaitable wrapper around ``func`` using :class:`ThreadPool`."""
    if asyncio.iscoroutinefunction(func): return func
    @functools.wraps(func)
    async def inner(*args, **kwargs):
        return await ThreadPool.arun(func, *args, **kwargs)
    return inner
