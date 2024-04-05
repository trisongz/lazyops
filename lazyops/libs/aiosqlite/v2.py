
from __future__ import annotations


"""
V2 Implementation of AioSQLite
"""


__all__ = ["connect", "Connection", "Cursor"]

import abc
import asyncio
import sqlite3
import contextlib
import functools
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Sequence
from functools import partial, wraps
from typing import Any, Literal, Optional, overload, Awaitable, TypeVar
from anyio import CapacityLimiter, to_thread


T = TypeVar('T')


class PoolObject(abc.ABC):
    """
    Base Pool Object
    """

    def __init__(
        self, 
        *args,
        max_workers: Optional[int] = None,
        pool: Optional[ThreadPoolExecutor] = None,
        concurrent: Optional[bool] = False,
        **kwargs,
    ) -> None:
        if pool is None: pool = ThreadPoolExecutor(max_workers = max_workers)
        self.pool = pool
        self.concurrent = concurrent
    
    def run_async(
        self, 
        func: Callable[..., T],
        *args, 
        **kwargs
    ) -> Awaitable[T]:
        """
        Wraps the function in a thread pool
        """
        blocking = functools.partial(func, *args, **kwargs)
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(self.pool, blocking)
        # future = self.pool.submit(func, *args, **kwargs)
        # return asyncio.wrap_future(future)

    
    async def run_async(
        self, 
        func: Callable[..., T],
        *args, 
        **kwargs
    ) -> Awaitable[T]:
        """
        Wraps the function in a thread pool
        """
        future = self.pool.submit(func, *args, **kwargs)
        f = asyncio.wrap_future(future)
        await f
        return f.result()
        
    

class Connection(PoolObject):
    def __init__(
        self, 
        _real_connection: sqlite3.Connection, 
        max_workers: Optional[int] = None,
        concurrent: Optional[bool] = False,
        **kwargs,
    ) -> None:
        
        super().__init__(max_workers = max_workers, concurrent = concurrent, **kwargs)
        self._real_connection = _real_connection
    

    @wraps(sqlite3.Connection.close)
    async def close(self):
        """
        Closes the connection
        """
        return await self.run_async(self._real_connection.close)

    @wraps(sqlite3.Connection.commit)
    async def commit(self):
        """
        Commits the connection
        """
        return await self.run_async(self._real_connection.commit)

    @wraps(sqlite3.Connection.rollback)
    async def rollback(self):
        """
        Rolls back the connection
        """
        return await self.run_async(self._real_connection.rollback)

    async def cursor(self, factory: Callable[[sqlite3.Connection], sqlite3.Cursor] = sqlite3.Cursor) -> Cursor:
        """
        Creates a cursor
        """
        real_cursor = await self.run_async(self._real_connection.cursor, factory)
        return Cursor(real_cursor, pool = self.pool)

    async def __aenter__(self) -> "Connection":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


class Cursor(PoolObject):
    def __init__(
        self, 
        real_cursor: sqlite3.Cursor, 
        pool: Optional[ThreadPoolExecutor] = None,
        **kwargs,
    ) -> None:
        self._real_cursor = real_cursor
        super().__init__(pool = pool, **kwargs)


    @property
    def description(self) -> Any:
        """
        Returns the description
        """
        return self._real_cursor.description

    @property
    def rowcount(self) -> int:
        """
        Returns the row count
        """
        return self._real_cursor.rowcount

    @property
    def arraysize(self) -> int:
        """
        Returns the array size
        """
        return self._real_cursor.arraysize
    
    @property
    def lastrowid(self) -> int:
        """
        Returns the last row id
        """
        return self._real_cursor.lastrowid

    @wraps(sqlite3.Cursor.close)
    async def close(self) -> None:
        """
        Closes the cursor
        """
        await self.run_async(self._real_cursor.close)

    @wraps(sqlite3.Cursor.execute)
    async def execute(self, sql: str, parameters: Sequence[Any] = (), /) -> Cursor:
        """
        Executes the sql
        """
        real_cursor = await self.run_async(self._real_cursor.execute, sql, parameters)
        return Cursor(real_cursor, pool = self.pool)

    @wraps(sqlite3.Cursor.executemany)
    async def executemany(self, sql: str, parameters: Sequence[Any], /) -> Cursor:
        """
        Executes the sql
        """
        real_cursor = await self.run_async(self._real_cursor.executemany, sql, parameters)
        return Cursor(real_cursor, pool = self.pool)


    @wraps(sqlite3.Cursor.executescript)
    async def executescript(self, sql_script: str, /) -> Cursor:
        """
        Executes the sql script
        """
        real_cursor = await self.run_async(self._real_cursor.executescript, sql_script)
        return Cursor(real_cursor, pool = self.pool)

    @wraps(sqlite3.Cursor.fetchone)
    async def fetchone(self) -> tuple[Any, ...] | None:
        """
        Fetches the first row
        """
        return await self.run_async(self._real_cursor.fetchone)

    @wraps(sqlite3.Cursor.fetchmany)
    async def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        """
        Fetches the rows
        """
        return await self.run_async(self._real_cursor.fetchmany, size)

    @wraps(sqlite3.Cursor.fetchall)
    async def fetchall(self) -> list[tuple[Any, ...]]:
        """
        Fetches the rows
        """
        return await self.run_async(self._real_cursor.fetchall)
    
    async def __aenter__(self) -> "Cursor":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

@overload
async def connect(
    database: str,
    timeout: Optional[float] = None,
    detect_types: Optional[int] = None,
    isolation_level: Literal['DEFERRED', 'IMMEDIATE', 'EXCLUSIVE'] = None,
    cached_statements: Optional[int] = 128,
    uri: Optional[bool] = False,
    limit: Optional[int] = None,
) -> Connection:
    """
    Connects to the database
    """
    ...


async def connect(
    database: str,
    max_workers: Optional[int] = None,
    concurrent: Optional[bool] = False,
    **kwargs,
) -> Connection:
    """
    Connects to the database
    """
    _ = kwargs.pop('check_same_thread', None)
    real_connection = await to_thread.run_sync(
        partial(sqlite3.connect, database, check_same_thread=False, **kwargs)
    )
    return Connection(real_connection, max_workers = max_workers, concurrent = concurrent)