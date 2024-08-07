from __future__ import annotations

"""
Credits:

https://gist.github.com/agronholm/458637aa569720fb1305cc74347e3e1d
"""

__all__ = ["connect", "Connection", "Cursor"]

import sqlite3
import contextlib
from collections.abc import Callable, Sequence
from functools import partial, wraps
from typing import Any, Literal, Optional, overload

from anyio import CapacityLimiter, to_thread


class Connection:
    def __init__(self, _real_connection: sqlite3.Connection, limit: Optional[int] = None) -> None:
        self._real_connection = _real_connection
        limit = limit or 1
        self._limiter = CapacityLimiter(limit)

    @wraps(sqlite3.Connection.close)
    async def close(self):
        return await to_thread.run_sync(self._real_connection.close, limiter=self._limiter)

    @wraps(sqlite3.Connection.commit)
    async def commit(self):
        return await to_thread.run_sync(self._real_connection.commit, limiter=self._limiter)

    @wraps(sqlite3.Connection.rollback)
    async def rollback(self):
        return await to_thread.run_sync(self._real_connection.rollback, limiter=self._limiter)

    async def cursor(self, factory: Callable[[sqlite3.Connection], sqlite3.Cursor] = sqlite3.Cursor) -> Cursor:
        real_cursor = await to_thread.run_sync(self._real_connection.cursor, factory, limiter=self._limiter)
        return Cursor(real_cursor, self._limiter)

    async def __aenter__(self) -> "Connection":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


class Cursor:
    def __init__(self, real_cursor: sqlite3.Cursor, limiter: CapacityLimiter) -> None:
        self._real_cursor = real_cursor
        self._limiter = limiter

    @property
    def description(self) -> Any:
        return self._real_cursor.description

    @property
    def rowcount(self) -> int:
        return self._real_cursor.rowcount

    @property
    def arraysize(self) -> int:
        return self._real_cursor.arraysize
    
    @property
    def lastrowid(self) -> int:
        return self._real_cursor.lastrowid

    @wraps(sqlite3.Cursor.close)
    async def close(self) -> None:
        await to_thread.run_sync(self._real_cursor.close, limiter=self._limiter)

    @wraps(sqlite3.Cursor.execute)
    async def execute(self, sql: str, parameters: Sequence[Any] = (), /) -> Cursor:
        real_cursor = await to_thread.run_sync(self._real_cursor.execute, sql, parameters, limiter=self._limiter)
        return Cursor(real_cursor, self._limiter)

    @wraps(sqlite3.Cursor.executemany)
    async def executemany(self, sql: str, parameters: Sequence[Any], /) -> Cursor:
        real_cursor = await to_thread.run_sync(self._real_cursor.executemany, sql, parameters, limiter=self._limiter)
        return Cursor(real_cursor, self._limiter)

    @wraps(sqlite3.Cursor.executescript)
    async def executescript(self, sql_script: str, /) -> Cursor:
        real_cursor = await to_thread.run_sync(self._real_cursor.executescript, sql_script, limiter=self._limiter)
        return Cursor(real_cursor, self._limiter)

    @wraps(sqlite3.Cursor.fetchone)
    async def fetchone(self) -> tuple[Any, ...] | None:
        return await to_thread.run_sync(self._real_cursor.fetchone, limiter=self._limiter)

    @wraps(sqlite3.Cursor.fetchmany)
    async def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        return await to_thread.run_sync(self._real_cursor.fetchmany, size, limiter=self._limiter)

    @wraps(sqlite3.Cursor.fetchall)
    async def fetchall(self) -> list[tuple[Any, ...]]:
        return await to_thread.run_sync(self._real_cursor.fetchall, limiter=self._limiter)


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
    limit: Optional[int] = None,
    **kwargs,
) -> Connection:
    """
    Connects to the database
    """
    _ = kwargs.pop('check_same_thread', None)
    real_connection = await to_thread.run_sync(
        partial(sqlite3.connect, database, check_same_thread=False, **kwargs)
    )
    return Connection(real_connection, limit = limit)