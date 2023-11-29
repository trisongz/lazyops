import os
import anyio
import inspect
import asyncio
import functools
import subprocess
from concurrent import futures

from typing import Callable, Coroutine, Any, Union, List, Set, Tuple, TypeVar, Optional, Generator, Awaitable, Iterable, AsyncGenerator
from anyio._core._eventloop import threadlocals


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


def ensure_coro(
    func: Callable[..., Any]
) -> Callable[..., Awaitable[Any]]:
    """
    Ensure that the function is a coroutine
    """
    if asyncio.iscoroutinefunction(func): return func
    @functools.wraps(func)
    async def inner(*args, **kwargs):
        return await ThreadPooler.asyncish(func, *args, **kwargs)
    return inner



class ThreadPooler:
    pool: futures.ThreadPoolExecutor = None
    max_workers: Optional[int] = None

    @classmethod
    def is_coro(cls, obj: Any) -> bool:
        return is_coro_func(obj)

    @classmethod
    def get_pool(cls) -> futures.ThreadPoolExecutor:
        if cls.pool is None:
            cls.pool = futures.ThreadPoolExecutor(max_workers = cls.max_workers)
        return cls.pool


    @classmethod
    async def run_async(cls, func: Callable, *args, **kwargs):
        """
        Runs a Sync Function as an Async Function
        """
        blocking = functools.partial(func, *args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(cls.get_pool(), blocking)
    
    
    @classmethod
    def run_sync(cls, func: Coroutine, *args, **kwargs):
        """
        Runs an Async Function as a Sync Function
        """
        current_async_module = getattr(threadlocals, "current_async_module", None)
        partial_f = functools.partial(func, *args, **kwargs)
        if current_async_module is None:
            return anyio.run(partial_f)
        return anyio.from_thread.run(partial_f)


    @classmethod
    async def asyncish(cls, func: Callable, *args, **kwargs):
        """
        Runs a Function as an Async Function if it is an Async Function
        otherwise wraps it around `run_async`
        """
        if cls.is_coro(func): return await func(*args, **kwargs)
        return await cls.run_async(func, *args, **kwargs)


    @classmethod
    def run_command(
        cls, 
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

    @classmethod
    async def async_run_command(
        cls, 
        command: Union[str, List[str]], 
        output_only: bool = True, 
        stdout = asyncio.subprocess.PIPE, 
        stderr = asyncio.subprocess.PIPE, 
        output_encoding: str = 'UTF-8', 
        output_errors: str = 'ignore', 
        *args,
        **kwargs
    ) -> Union[str, asyncio.subprocess.Process]:
        """
        Executes a Shell command using `asyncio.subprocess.create_subprocess_shell`

        Returns str if output_only else `asyncio.subprocess.Process`
        """
        if isinstance(command, list): command = ' '.join(command)
        p = await asyncio.subprocess.create_subprocess_shell(command, *args, stdout = stdout, stderr = stderr, **kwargs)
        if not output_only: return p
        stdout, _ = await p.communicate()
        return stdout.decode(encoding = output_encoding, errors = output_errors).strip()


RT = TypeVar("RT")

class ThreadPoolerMetaClass(type):
    """
    ThreadPooler v2
    """

    _pool: Optional[futures.ThreadPoolExecutor] = None
    _ppool: Optional[futures.ProcessPoolExecutor] = None
    _max_workers: Optional[int] = None
    _in_async_loop: Optional[bool] = None
    _tasks: Optional[Set[asyncio.Task]] = None

    allow_task_completion: bool = True
    register_exit: bool = True

    @property
    def max_workers(cls) -> int:
        """
        Returns the number of max workers
        """
        if cls._max_workers is None:
            cls._max_workers = int(os.getenv("MAX_WORKERS", os.cpu_count()))
        return cls._max_workers
    
    @property
    def in_async_loop(cls) -> bool:
        """
        Returns True if the current thread is in an async loop
        """
        if cls._in_async_loop is None:
            try:
                cls._in_async_loop = asyncio.get_running_loop() is not None
            except RuntimeError:
                cls._in_async_loop = False
        return cls._in_async_loop

    @property
    def pool(cls) -> futures.ThreadPoolExecutor:
        """
        Returns the ThreadPoolExecutor
        """
        if cls._pool is None:
            cls._pool = futures.ThreadPoolExecutor(max_workers = cls.max_workers)
        return cls._pool
    
    @property
    def ppool(cls) -> futures.ProcessPoolExecutor:
        """
        Returns the ProcessPoolExecutor
        """
        if cls._ppool is None:
            cls._ppool = futures.ProcessPoolExecutor(max_workers = cls.max_workers)
        return cls._ppool
    
    def get_pool(cls, n_workers: Optional[int] = None, process_pool: bool = False) -> futures.Executor:
        """
        Returns the ThreadPoolExecutor or ProcessPoolExecutor
        """
        pool_cls = futures.ProcessPoolExecutor if process_pool else futures.ThreadPoolExecutor
        if n_workers is None: n_workers = cls.max_workers
        return pool_cls(max_workers = n_workers)

    @property
    def tasks(cls) -> Set[asyncio.Task]:
        """
        Returns the current tasks
        """
        if cls._tasks is None:
            cls._tasks = set()
            if cls.register_exit:
                import atexit
                atexit.register(cls.on_exit)
        return cls._tasks
    
    def add_task(cls, task: asyncio.Task, callback: Optional[Callable] = None):
        """
        Adds a task to the current tasks
        """
        cls.tasks.add(task)
        if callback is not None:
            task.add_done_callback(callback)
        task.add_done_callback(cls.tasks.discard)
        

    def on_exit(cls):
        """
        Cleans up the ThreadPoolExecutor and Tasks
        """
        for task in cls.tasks:
            task.cancel()
        if cls._pool is not None: cls._pool.shutdown(wait = cls.allow_task_completion, cancel_futures = not cls.allow_task_completion)
        if cls._ppool is not None: cls._ppool.shutdown(wait = cls.allow_task_completion, cancel_futures = not cls.allow_task_completion)


    def is_coro(cls, obj: Any) -> bool:
        """
        Checks if an object is a coroutine function
        """
        return is_coro_func(obj)

    async def run_async(cls, func: Callable, *args, **kwargs):
        """
        Runs a Sync Function as an Async Function
        """
        blocking = functools.partial(func, *args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(cls.pool, blocking)
    
    def run_sync(cls, func: Coroutine, *args, **kwargs):
        """
        Runs an Async Function as a Sync Function
        """
        current_async_module = getattr(threadlocals, "current_async_module", None)
        partial_f = functools.partial(func, *args, **kwargs)
        if current_async_module is None:
            return anyio.run(partial_f)
        return anyio.from_thread.run(partial_f)

    async def asyncish(cls, func: Callable, *args, **kwargs):
        """
        Runs a Function as an Async Function if it is an Async Function
        otherwise wraps it around `run_async`
        """
        if cls.is_coro(func): return await func(*args, **kwargs)
        return await cls.run_async(func, *args, **kwargs)

    def run_command(
        cls, 
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

    async def async_run_command(
        cls, 
        command: Union[str, List[str]], 
        output_only: bool = True, 
        stdout = asyncio.subprocess.PIPE, 
        stderr = asyncio.subprocess.PIPE, 
        output_encoding: str = 'UTF-8', 
        output_errors: str = 'ignore', 
        *args,
        **kwargs
    ) -> Union[str, asyncio.subprocess.Process]:
        """
        Executes a Shell command using `asyncio.subprocess.create_subprocess_shell`

        Returns str if output_only else `asyncio.subprocess.Process`
        """
        if isinstance(command, list): command = ' '.join(command)
        p = await asyncio.subprocess.create_subprocess_shell(command, *args, stdout = stdout, stderr = stderr, **kwargs)
        if not output_only: return p
        stdout, _ = await p.communicate()
        return stdout.decode(encoding = output_encoding, errors = output_errors).strip()
    
    """
    v2 Functions
    """

    def create_threadpool_task(cls, func: Callable, *args, task_callback: Optional[Callable] = None, **kwargs) -> futures.Future:
        """
        Creates a threadpool task
        """
        task = cls.pool.submit(func, *args, **kwargs)
        # task.add_done_callback
        cls.add_task(task, task_callback)
        return task

    def create_background_task(cls, func: Callable, *args, task_callback: Optional[Callable] = None, **kwargs) -> asyncio.Task:
        """
        Creates a background task
        """
        if inspect.isawaitable(func):
            task = asyncio.create_task(func)
        else:
            task = asyncio.create_task(cls.asyncish(func, *args, **kwargs))
        cls.add_task(task, task_callback)
        return task
    
    def create_background(cls, func: Callable, *args, **kwargs) -> Union[asyncio.Task, futures.Future]:
        """
        Runs a function in the background.
        If the current thread is in an async loop, it runs the function as an async function.
        Otherwise, it runs the function as a sync function in the threadpool.

        Returns a `asyncio.Task` if the current thread is in an async loop.
        Otherwise, it returns a `futures.Future`.
        """
        if cls.in_async_loop:
            return cls.create_background_task(func, *args, **kwargs)
        return cls.create_threadpool_task(func, *args, **kwargs)
    
    def sync_map(
        cls,
        func: Callable,
        iterable: Iterable[Any],
        *args,
        return_ordered: Optional[bool] = True,
        use_process_pool: Optional[bool] = False, 
        **kwargs
    ) -> List[RT]:  # sourcery skip: assign-if-exp
        """
        Iterates over an iterable and runs a function on each item in the iterable.
        """
        n_workers = kwargs.pop('n_workers', None)
        partial_func = functools.partial(func, *args, **kwargs)
        with cls.get_pool(n_workers = n_workers, process_pool = use_process_pool) as executor:
            _futures = [
                executor.submit(partial_func, item) for item in iterable
            ]
            if not return_ordered: return [f.result() for f in futures.as_completed(_futures)]
            futures.wait(_futures)
            return [f.result() for f in _futures]
            # return [f.result() for f in return_func(_futures)]
        

    def sync_iterate(
        cls,
        func: Callable,
        iterable: Iterable[Any],
        *args,
        use_process_pool: Optional[bool] = False, 
        return_ordered: Optional[bool] = True,
        **kwargs
    ) -> Generator[RT, None, None]:  # sourcery skip: assign-if-exp
        """
        Iterates over an iterable and runs a function on each item in the iterable.
        """
        n_workers = kwargs.pop('n_workers', None)
        partial_func = functools.partial(func, *args, **kwargs)
        with cls.get_pool(n_workers = n_workers, process_pool = use_process_pool) as executor:
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
    
    async def async_map(
        cls,
        func: Callable[..., Awaitable[Any]],
        iterable: Iterable[Any], 
        *args,
        return_ordered: Optional[bool] = True,
        concurrency_limit: Optional[int] = None,
        **kwargs,
    ) -> List[RT]:
        """
        Creates an Async Generator that iterates over an iterable and runs a function on each item in the iterable.
        """
        from .ahelpers import async_map as _amap
        rt = kwargs.pop('return_when', 'ALL_COMPLETED' if return_ordered else 'FIRST_COMPLETED')
        concurrency_limit = kwargs.pop('limit', concurrency_limit)

        results = []
        async for result in _amap(func, iterable, *args, return_when = rt, **kwargs):
            results.append(result)
        return results
    
    async def async_iterate(
        cls,
        func: Callable[..., Awaitable[Any]],
        iterable: Iterable[Any], 
        *args,
        return_ordered: Optional[bool] = True,
        concurrency_limit: Optional[int] = None,
        **kwargs,
    ) -> AsyncGenerator[RT, None]:
        """
        Creates an Async Generator that iterates over an iterable and runs a function on each item in the iterable.
        """
        from .ahelpers import async_map as _amap
        rt = kwargs.pop('return_when', 'ALL_COMPLETED' if return_ordered else 'FIRST_COMPLETED')
        concurrency_limit = kwargs.pop('limit', concurrency_limit)
        async for result in _amap(func, iterable, *args, return_when = rt, **kwargs):
            yield result



class ThreadPoolV2(metaclass = ThreadPoolerMetaClass):
    """
    (v2) The ThreadPooler Class
    """
    pass