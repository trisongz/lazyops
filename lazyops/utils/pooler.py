import anyio
import asyncio
import functools
import subprocess
from concurrent import futures

from typing import Callable, Coroutine, Any, Union, List, Optional
from anyio._core._eventloop import threadlocals
from lazyops.utils.lazy import is_coro_func

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
    
