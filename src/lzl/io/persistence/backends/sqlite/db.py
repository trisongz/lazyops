from __future__ import annotations

"""
SQLite Backend

Borrowed parts from `python-diskache <https://github.com/grantjenks/python-diskcache>`_
"""

import abc
import copy
import time
import asyncio
import contextlib
import threading
import contextlib
import typing as t
from lzl import load
from lzl.pool import ThreadPool
from lzo.types import eproperty
from pydantic.networks import UrlConstraints, Annotated
try:
    from pydantic_core import MultiHostUrl
except ImportError:
    from pydantic.networks import MultiHostUrl
from ..base import logger
from .utils import dict_diff
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Tuple, Iterable, List, Type, Callable, Generator, AsyncGenerator, TYPE_CHECKING

if load.TYPE_CHECKING:
    import sqlite3
    import aiosqlite

    from sqlite3 import Connection, Cursor
    from aiosqlite import Connection as AsyncConnection, Cursor as AsyncCursor
else:
    sqlite3 = load.LazyLoad("sqlite3")
    aiosqlite = load.LazyLoad("aiosqlite")


from .base import (
    BaseSqliteDB,
    get_eviction_policies,
    get_optimized_settings,
    METADATA,
    OPTIMIZED,
    SqliteDsn,
    Optimization,

    Timeout,
    ENOVAL,
    UNKNOWN,
)

class SqliteDB(BaseSqliteDB):
    """
    The Sqlite Database
    """

    def get_child(self, table: str, timeout: t.Optional[float] = None, **kwargs) -> 'SqliteDB':
        """
        Creates a New Child Instance
        """
        child_kwargs = copy.deepcopy(self._child_kwargs)
        child_kwargs['table'] = table
        if timeout is not None: child_kwargs['timeout'] = timeout
        if self._debug_enabled: child_kwargs['debug_enabled'] = self._debug_enabled
        if kwargs: child_kwargs['kwargs'].update(kwargs)
        child_kwargs['is_child_db'] = True
        kws = child_kwargs.pop('kwargs', {})
        # logger.info({**child_kwargs, **kws}, prefix = f'{table} - Init Kws', colored = True)
        new_child = type(self)(**child_kwargs, **kws)
        # Provide the underlying props
        _extra_kws = copy.deepcopy(self._extra)
        _extra_kws.pop('is_configured', None)
        _extra_kws.pop('configured', None)
        _extra_kws.pop('has_configured_table', None)
        _extra_kws.pop('has_configured_settings', None)
        _extra_kws.pop('eviction_policies', None)
        _extra_kws.pop('eviction_policy', None)
        new_child._extra.update(_extra_kws)
        # logger.info(f'Child Cache: {new_child.conn_uri}: {new_child.table}: {new_child._extra}')
        # logger.info(new_child._extra, prefix = f'{new_child.table} - Extra', colored = True)
        return new_child



    """
    Public Primary Methods
    """
    
    def _set(self, key: str, value: t.Any, expire: Optional[float] = None, read: bool = False, tag: t.Optional[str] = None, retry: bool = False):
        """Set `key` and `value` item in cache.

        When `read` is `True`, `value` should be a file-like object opened
        for reading in binary mode.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param value: value for item
        :param float expire: seconds until item expires
            (default None, no expiry)
        :param bool read: read value as bytes from file (default False)
        :param str tag: text to associate with key (default None)
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was set
        :raises Timeout: if database timeout occurs
        """
        now = time.time()
        size = self.get_object_size(value)
        expire_time = None if expire is None else now + expire
        columns = (expire_time, tag, size, value)

        # The order of SELECT, UPDATE, and INSERT is important below.
        #
        # Typical cache usage pattern is:
        #
        # value = cache.get(key)
        # if value is None:
        #     value = expensive_calculation()
        #     cache.set(key, value)
        #
        # Cache.get does not evict expired keys to avoid writes during lookups.
        # Commonly used/expired keys will therefore remain in the cache making
        # an UPDATE the preferred path.
        #
        # The alternative is to assume the key is not present by first trying
        # to INSERT and then handling the IntegrityError that occurs from
        # violating the UNIQUE constraint. This optimistic approach was
        # rejected based on the common cache usage pattern.
        #
        # INSERT OR REPLACE aka UPSERT is not used because the old filename may
        # need cleanup.

        with self._transact(retry) as sql:
            rows = sql(
                f'SELECT rowid FROM "{self.table}"'
                ' WHERE key = ?',
                (key,),
            ).fetchall()

            if rows:
                ((rowid,),) = rows
                # logger.info(f'{rowid}') 
                self._row_update(rowid, now, columns)
            else:
                self._row_insert(key, now, columns)

            self._cull(now, sql)
            # self._cull(now, sql, cleanup)
            return True

    def set(self, key: str, value: t.Any, expire: Optional[float] = None, read: bool = False, tag: t.Optional[str] = None, retry: bool = False):
        """Set `key` and `value` item in cache.

        When `read` is `True`, `value` should be a file-like object opened
        for reading in binary mode.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param value: value for item
        :param float expire: seconds until item expires
            (default None, no expiry)
        :param bool read: read value as bytes from file (default False)
        :param str tag: text to associate with key (default None)
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was set
        :raises Timeout: if database timeout occurs
        """
        now = time.time()
        size = self.get_object_size(value)
        expire_time = None if expire is None else now + expire
        columns = (expire_time, tag, size, value)
        
        with self._transact(retry) as sql:
            # We'll use the upsert method here
            self._row_upsert(key, now, columns, sql = sql)
            self._cull(now, sql)
            return True
        
    async def _aset(self, key: str, value: t.Any, expire: Optional[float] = None, read: bool = False, tag: t.Optional[str] = None, retry: bool = False):
        """Set `key` and `value` item in cache.

        When `read` is `True`, `value` should be a file-like object opened
        for reading in binary mode.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param value: value for item
        :param float expire: seconds until item expires
            (default None, no expiry)
        :param bool read: read value as bytes from file (default False)
        :param str tag: text to associate with key (default None)
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was set
        :raises Timeout: if database timeout occurs
        """
        now = time.time()
        size = self.get_object_size(value)
        expire_time = None if expire is None else now + expire
        columns = (expire_time, tag, size, value)        
        async with self._atransact(retry) as sql:
            # result = await sql(
            #     f'SELECT rowid FROM {self.table}'
            #     ' WHERE key = ?',
            #     (key,),
            # )
            # rows = await result.fetchall()
            rows = await (await sql(
                f'SELECT rowid FROM "{self.table}"'
                ' WHERE key = ?',
                (key,),
            )).fetchall()

            if rows:
                ((rowid,),) = rows
                await self._row_update(rowid, now, columns, is_async = True)
            else:
                await self._row_insert(key, now, columns, is_async = True)

            self.abg_cull(now, retry = retry)
            # await self._acull(now, sql)
            return True
    

    async def aset(self, key: str, value: t.Any, expire: Optional[float] = None, read: bool = False, tag: t.Optional[str] = None, retry: bool = False):
        """Set `key` and `value` item in cache.

        When `read` is `True`, `value` should be a file-like object opened
        for reading in binary mode.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param value: value for item
        :param float expire: seconds until item expires
            (default None, no expiry)
        :param bool read: read value as bytes from file (default False)
        :param str tag: text to associate with key (default None)
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was set
        :raises Timeout: if database timeout occurs
        """
        now = time.time()
        size = self.get_object_size(value)
        expire_time = None if expire is None else now + expire
        columns = (expire_time, tag, size, value)        
        async with self._atransact(retry) as sql:
            await self._row_upsert(key, now, columns, is_async = True, sql = sql)
            self.abg_cull(now, retry = retry)
            return True

    def batch_set(self, data: t.Dict[str, t.Any], expire: t.Optional[float] = None, tag: t.Optional[str] = None, retry: t.Optional[bool] = None):
        """
        Batch sets many items

        :param data: dict of key/value pairs
        :param expire: seconds until the key expires
            (default None, no expiry)
        :param retry: retry if database timeout occurs (default None, no retry)
        :return: True if item was set
        """
        now = time.time()
        expire_time = None if expire is None else now + expire
        columns = (expire_time, tag)
        with self._transact(retry) as sql:
            self._bulk_upsert(data, now, columns)
            self._cull(now, sql)
            return True

    async def abatch_set(self, data: t.Dict[str, t.Any], expire: t.Optional[float] = None, tag: t.Optional[str] = None, retry: t.Optional[bool] = None):
        """
        Batch sets many items

        :param data: dict of key/value pairs
        :param expire: seconds until the key expires
            (default None, no expiry)
        :param retry: retry if database timeout occurs (default None, no retry)
        :return: True if item was set
        """
        now = time.time()
        expire_time = None if expire is None else now + expire
        columns = (expire_time, tag)
        # async with self._atransact(retry) as sql:
        await self._bulk_upsert(data, now, columns, is_async = True)
        self.abg_cull(now, retry = retry)
        return True


    def _cull(self, now: float, sql: t.Callable[..., 'Cursor'], limit: t.Optional[int] = None):
        """
        Culls the cache
        """
        cull_limit = self.cull_limit if limit is None else limit
        if cull_limit == 0: return

        # Evict expired keys.
        select_expired_template = (
            f'SELECT %s FROM "{self.table}"'
            ' WHERE expire_time IS NOT NULL AND expire_time < ?'
            ' ORDER BY expire_time LIMIT ?'
        )

        select_expired = select_expired_template % 'key'
        rows = sql(select_expired, (now, cull_limit)).fetchall()
        if rows:
            delete_expired = f'DELETE FROM "{self.table}" WHERE rowid IN (%s)' % (
                select_expired_template % 'rowid'
            )
            sql(delete_expired, (now, cull_limit))
            cull_limit -= len(rows)
            if cull_limit == 0: return

        # Evict keys by policy.
        select_policy = self.eviction_policies['cull']
        if select_policy is None or self.volume() < self.size_limit:
            return
        
        select_key = select_policy.format(fields='key', now=now)
        rows = sql(select_key, (cull_limit,)).fetchall()
        if rows:
            delete = f'DELETE FROM "{self.table}" WHERE key IN (%s)' % (
                select_policy.format(fields='rowid', now=now)
            )
            sql(delete, (cull_limit,))
    

    async def _acull(self, now: float, sql: t.Callable[..., t.Awaitable['AsyncCursor']], limit: t.Optional[int] = None):
        """
        Culls the cache
        """
        cull_limit = self.cull_limit if limit is None else limit
        if cull_limit == 0: return

        # Evict expired keys.
        select_expired_template = (
            f'SELECT %s FROM "{self.table}"'
            ' WHERE expire_time IS NOT NULL AND expire_time < ?'
            ' ORDER BY expire_time LIMIT ?'
        )

        select_expired = select_expired_template % 'key'
        rows = await (await sql(select_expired, (now, cull_limit))).fetchall()
        if rows:
            delete_expired = f'DELETE FROM "{self.table}" WHERE rowid IN (%s)' % (
                select_expired_template % 'rowid'
            )
            await sql(delete_expired, (now, cull_limit))
            cull_limit -= len(rows)
            if cull_limit == 0: return

        # Evict keys by policy.
        select_policy = self.eviction_policies['cull']
        if select_policy is None or (await self.avolume()) < self.size_limit:
            return
        
        select_key = select_policy.format(fields='key', now=now)
        rows = (await sql(select_key, (cull_limit,))).fetchall()
        if rows:
            delete = f'DELETE FROM "{self.table}" WHERE key IN (%s)' % (
                select_policy.format(fields='rowid', now=now)
            )
            await sql(delete, (cull_limit,))

    async def _abg_cull(self, now: float, limit: t.Optional[int] = None, retry: bool = False):
        """
        [Async - Background] Culls the cache
        """
        # We don't pass the sql connection for thread safety.
        # async with self._atransact(retry) as sql:
        sql = self._asql_retry if retry else self._asql
        await self._acull(now, sql, limit = limit)
    
    def abg_cull(self, now: float, limit: t.Optional[int] = None, retry: bool = False):
        """
        [Async Background] Culls the cache
        """
        return self.pool.create_background(self._abg_cull, now = now, limit = limit, retry = retry)

    def touch(self, key: str, expire: Optional[float] = None, retry: bool = False):
        """Touch `key` in cache and update `expire` time.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param float expire: seconds until item expires
            (default None, no expiry)
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if key was touched
        :raises Timeout: if database timeout occurs
        """
        now = time.time()
        expire_time = None if expire is None else now + expire
        with self._transact(retry) as sql:
            rows = sql(
                f'SELECT rowid, expire_time FROM "{self.table}"'
                ' WHERE key = ?',
                (key,),
            ).fetchall()
            if rows:
                ((rowid, old_expire_time),) = rows

                if old_expire_time is None or old_expire_time > now:
                    sql(
                        f'UPDATE "{self.table}" SET expire_time = ? WHERE rowid = ?',
                        (expire_time, rowid),
                    )
                    return True
        return False
                    
    
    async def atouch(self, key: str, expire: Optional[float] = None, retry: bool = False):
        """Touch `key` in cache and update `expire` time.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param float expire: seconds until item expires
            (default None, no expiry)
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if key was touched
        :raises Timeout: if database timeout occurs
        """
        now = time.time()
        expire_time = None if expire is None else now + expire
        async with self._atransact(retry) as sql:
            rows = await (await sql(
                f'SELECT rowid, expire_time FROM "{self.table}"'
                ' WHERE key = ?',
                (key,),
            )).fetchall()
            if rows:
                ((rowid, old_expire_time),) = rows
                if old_expire_time is None or old_expire_time > now:
                    await sql(
                        f'UPDATE "{self.table}" SET expire_time = ? WHERE rowid = ?',
                        (expire_time, rowid),
                    )
                    return True
        return False
                    
    

    def add(self, key: str, value: t.Any, expire: t.Optional[float] = None, read: bool = False, tag: t.Optional[str] = None, retry: bool = False):
        """Add `key` and `value` item to cache.

        Similar to `set`, but only add to cache if key not present.

        Operation is atomic. Only one concurrent add operation for a given key
        will succeed.

        When `read` is `True`, `value` should be a file-like object opened
        for reading in binary mode.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param value: value for item
        :param float expire: seconds until the key expires
            (default None, no expiry)
        :param bool read: read value as bytes from file (default False)
        :param str tag: text to associate with key (default None)
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was added
        :raises Timeout: if database timeout occurs

        """
        now = time.time()
        expire_time = None if expire is None else now + expire
        size = self.get_object_size(value)
        # size, mode, filename, db_value = self._disk.store(value, read, key=key)
        # columns = (expire_time, tag, size, mode, filename, db_value)
        columns = (expire_time, tag, size, value)

        # with self._transact(retry, filename) as (sql, cleanup):
        with self._transact(retry) as sql:
            rows = sql(
                f'SELECT rowid, expire_time FROM "{self.table}"'
                ' WHERE key = ?',
                (key,),
            ).fetchall()

            if rows:
                ((rowid, old_expire_time),) = rows
                if old_expire_time is None or old_expire_time > now:
                    return False
                self._row_update(rowid, now, columns)
            else: self._row_insert(key, now, columns)
            self._cull(now, sql)
            return True
    
    async def aadd(self, key: str, value: t.Any, expire: t.Optional[float] = None, read: bool = False, tag: t.Optional[str] = None, retry: bool = False):
        """Add `key` and `value` item to cache.

        Similar to `set`, but only add to cache if key not present.

        Operation is atomic. Only one concurrent add operation for a given key
        will succeed.

        When `read` is `True`, `value` should be a file-like object opened
        for reading in binary mode.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param value: value for item
        :param float expire: seconds until the key expires
            (default None, no expiry)
        :param bool read: read value as bytes from file (default False)
        :param str tag: text to associate with key (default None)
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was added
        :raises Timeout: if database timeout occurs

        """
        now = time.time()
        expire_time = None if expire is None else now + expire
        size = self.get_object_size(value)
        columns = (expire_time, tag, size, value)
        async with self._atransact(retry) as sql:
            rows = await (await sql(
                f'SELECT rowid, expire_time FROM "{self.table}"'
                ' WHERE key = ?',
                (key,),
            )).fetchall()

            if rows:
                ((rowid, old_expire_time),) = rows
                if old_expire_time is None or old_expire_time > now:
                    return False
                await self._row_update(rowid, now, columns, is_async = True)
            else: await self._row_insert(key, now, columns, is_async = True)
            self.abg_cull(now, retry = retry)
            # self._cull(now, sql)
            return True
    

    def incr(self, key: str, delta: int = 1, default: int = 0, retry: bool = False):
        """Increment value by delta for item with key.

        If key is missing and default is None then raise KeyError. Else if key
        is missing and default is not None then use default for value.

        Operation is atomic. All concurrent increment operations will be
        counted individually.

        Assumes value may be stored in a SQLite column. Most builds that target
        machines with 64-bit pointer widths will support 64-bit signed
        integers.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param int delta: amount to increment (default 1)
        :param int default: value if key is missing (default 0)
        :param bool retry: retry if database timeout occurs (default False)
        :return: new value for item
        :raises KeyError: if key is not found and default is None
        :raises Timeout: if database timeout occurs

        """
        now = time.time()

        # db_key, raw = self._disk.put(key)
        select = (
            f'SELECT rowid, expire_time, value FROM "{self.table}"'
            ' WHERE key = ?'
        )

        with self._transact(retry) as sql:
            rows = sql(select, (key,)).fetchall()
            if not rows:
                if default is None: raise KeyError(key)
                value = default + delta
                # expire_time, tag, size, value
                columns = (None, None, self.get_object_size(value), value)
                self._row_insert(key, now, columns)
                # columns = (None, None) + self._disk.store(
                #     value, False, key=key
                # )
                self._row_insert(key, now, columns)
                self._cull(now, sql)
                return value
            
            ((rowid, expire_time, value),) = rows
            # ((rowid, expire_time, filename, value),) = rows
            if expire_time is not None and expire_time < now:
                if default is None: raise KeyError(key)

                value = default + delta
                columns = (None, None, self.get_object_size(value), value)
                # columns = (None, None) + self._disk.store(
                #     value, False, key=key
                # )
                self._row_update(rowid, now, columns)
                self._cull(now, sql)
                # cleanup(filename)
                return value

            value += delta
            columns = 'store_time = ?, value = ?'
            update_column = self.eviction_policies['get']
            if update_column is not None:
                columns += f', {update_column.format(now=now)}'
            update = f'UPDATE "{self.table}" SET %s WHERE rowid = ?' % columns
            sql(update, (now, value, rowid))
            return value
    
    async def aincr(self, key: str, delta: int = 1, default: int = 0, retry: bool = False):
        """Increment value by delta for item with key.

        If key is missing and default is None then raise KeyError. Else if key
        is missing and default is not None then use default for value.

        Operation is atomic. All concurrent increment operations will be
        counted individually.

        Assumes value may be stored in a SQLite column. Most builds that target
        machines with 64-bit pointer widths will support 64-bit signed
        integers.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param int delta: amount to increment (default 1)
        :param int default: value if key is missing (default 0)
        :param bool retry: retry if database timeout occurs (default False)
        :return: new value for item
        :raises KeyError: if key is not found and default is None
        :raises Timeout: if database timeout occurs

        """
        now = time.time()
        select = (
            f'SELECT rowid, expire_time, value FROM {self.table}'
            ' WHERE key = ?'
        )

        async with self._atransact(retry) as sql:
            rows = await (await sql(select, (key,))).fetchall()
            if not rows:
                if default is None: raise KeyError(key)
                value = default + delta
                columns = (None, None, self.get_object_size(value), value)
                await self._row_insert(key, now, columns, is_async = True)
                await self._row_insert(key, now, columns, is_async = True)
                self.abg_cull(now, retry = retry)
                return value
            
            ((rowid, expire_time, value),) = rows
            if expire_time is not None and expire_time < now:
                if default is None: raise KeyError(key)
                value = default + delta
                columns = (None, None, self.get_object_size(value), value)
                await self._row_update(rowid, now, columns, is_async = True)
                self.abg_cull(now, retry = retry)
                return value

            value += delta
            columns = 'store_time = ?, value = ?'
            update_column = self.eviction_policies['get']
            if update_column is not None:
                columns += f', {update_column.format(now=now)}'
            update = f'UPDATE "{self.table}" SET %s WHERE rowid = ?' % columns
            await sql(update, (now, value, rowid))
            return value

    def decr(self, key: str, delta: int = 1, default: int = 0, retry: bool = False):
        """Decrement value by delta for item with key.

        If key is missing and default is None then raise KeyError. Else if key
        is missing and default is not None then use default for value.

        Operation is atomic. All concurrent decrement operations will be
        counted individually.

        Unlike Memcached, negative values are supported. Value may be
        decremented below zero.

        Assumes value may be stored in a SQLite column. Most builds that target
        machines with 64-bit pointer widths will support 64-bit signed
        integers.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param int delta: amount to decrement (default 1)
        :param int default: value if key is missing (default 0)
        :param bool retry: retry if database timeout occurs (default False)
        :return: new value for item
        :raises KeyError: if key is not found and default is None
        :raises Timeout: if database timeout occurs

        """
        return self.incr(key, -delta, default, retry)

    
    async def adecr(self, key: str, delta: int = 1, default: int = 0, retry: bool = False):
        """Decrement value by delta for item with key.

        If key is missing and default is None then raise KeyError. Else if key
        is missing and default is not None then use default for value.

        Operation is atomic. All concurrent decrement operations will be
        counted individually.

        Unlike Memcached, negative values are supported. Value may be
        decremented below zero.

        Assumes value may be stored in a SQLite column. Most builds that target
        machines with 64-bit pointer widths will support 64-bit signed
        integers.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param int delta: amount to decrement (default 1)
        :param int default: value if key is missing (default 0)
        :param bool retry: retry if database timeout occurs (default False)
        :return: new value for item
        :raises KeyError: if key is not found and default is None
        :raises Timeout: if database timeout occurs

        """
        return await self.aincr(key, -delta, default, retry)

    def get(
        self,
        key: str,
        default: t.Optional[t.Any] = None,
        include_meta: t.Optional[bool] = False,
        retry: bool = False,
    ) -> t.Union[t.Any, t.Tuple[t.Any, t.Dict[str, t.Any]]]:
        """Retrieve value from cache. If `key` is missing, return `default`.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param default: value to return if key is missing (default None)
        :param include_meta: if True, return a dict of metadata as the second item (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: value for item or default if key not found or a tuple of (value, metadata)
        :raises Timeout: if database timeout occurs
        """

        # db_key, raw = self._disk.put(key)
        update_column = self.eviction_policies['get']
        select = (
            'SELECT rowid, expire_time, tag, access_count, hit_count, value'
            f' FROM "{self.table}" WHERE key = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )
        if not self.statistics and update_column is None:
            # Fast path, no transaction necessary.
            rows = self._sql(select, (key, time.time())).fetchall()
            if not rows: return default

            # ((rowid, db_expire_time, db_tag, mode, filename, db_value),) = rows
            ((rowid, expire_time, tag, access_count, hit_count, value),) = rows

        else:  # Slow path, transaction required.
            _result = self._update_statistics(key, select, update_column, retry = retry)
            if _result is ENOVAL: return default
            ((rowid, expire_time, tag, access_count, hit_count, value),) = _result

        if not include_meta: return value
        return value, {
            'expire_time': expire_time,
            'rowid': rowid,
            'access_count': access_count,
            'hits': hit_count,
            'tag': tag,
        }


    async def aget(
        self,
        key: str,
        default: t.Optional[t.Any] = None,
        include_meta: t.Optional[bool] = False,
        retry: bool = False,
    ) -> t.Union[t.Any, t.Tuple[t.Any, t.Dict[str, t.Any]]]:
        """Retrieve value from cache. If `key` is missing, return `default`.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param default: value to return if key is missing (default None)
        :param include_meta: if True, return a dict of metadata as the second item (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: value for item or default if key not found or a tuple of (value, metadata)
        :raises Timeout: if database timeout occurs
        """
        update_column = self.eviction_policies['get']
        select = (
            'SELECT rowid, expire_time, tag, access_count, hit_count, value'
            f' FROM "{self.table}" WHERE key = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )
        if not self.statistics and update_column is None:
            rows = await (await self._asql(select, (key, time.time()))).fetchall()
            if not rows: return default
            ((rowid, expire_time, tag, access_count, hit_count, value),) = rows

        else:  # Slow path, transaction required.
            _result = await self._aupdate_statistics(key, select, update_column, retry = retry)
            if _result is ENOVAL: return default
            ((rowid, expire_time, tag, access_count, hit_count, value),) = _result
        
        if not include_meta: return value
        return value, {
            'expire_time': expire_time,
            'rowid': rowid,
            'access_count': access_count,
            'hits': hit_count,
            'tag': tag,
        }

    
    def _update_statistics(self, key: str, select: str, update_column: t.Optional[str] = None, retry: bool = False):
        """
        Update The Statics
        """
        cache_hit = (
            f'UPDATE "{self.table}_settings" SET value = value + 1 WHERE key = "hits"'
        )
        cache_miss = (
            f'UPDATE "{self.table}_settings" SET value = value + 1 WHERE key = "misses"'
        )
        with self._transact(retry) as sql:
            rows = sql(select, (key, time.time())).fetchall()
            if not rows:
                if self.statistics: sql(cache_miss)
                return ENOVAL
            (
                (rowid, _, _, _, _, _),
            ) = rows
            if self.statistics: sql(cache_hit)
            now = time.time()
            update = f'UPDATE "{self.table}" SET %s WHERE rowid = ?'
            if update_column is not None:
                sql(update % update_column.format(now=now), (rowid,))
            return rows

    async def _aupdate_statistics(self, key: str, select: str, update_column: t.Optional[str] = None, retry: bool = False):
        """
        [Async Background] Update The Statics
        """
        cache_hit = (
            f'UPDATE "{self.table}_settings" SET value = value + 1 WHERE key = "hits"'
        )
        cache_miss = (
            f'UPDATE "{self.table}_settings" SET value = value + 1 WHERE key = "misses"'
        )
        async with self._atransact(retry) as sql:
            rows = await (await sql(select, (key, time.time()))).fetchall()
            if not rows:
                if self.statistics: await sql(cache_miss)
                return ENOVAL
            (
                (rowid, _, _, _, _, _),
            ) = rows
            if self.statistics: await sql(cache_hit)

            now = time.time()
            update = f'UPDATE "{self.table}" SET %s WHERE rowid = ?'
            if update_column is not None:
                await sql(update % update_column.format(now=now), (rowid,))
            return rows

    def fetch_kv_data(self, limit: t.Optional[int] = None, **kwargs) -> t.Dict[str, t.Any]:
        """
        Loads all the Data
        """
        # Since this is a heavy operation, we'll just retrieve it from the DB
        # with a single query
        select = (
            'SELECT key, value'
            f' FROM "{self.table}"'
            ' WHERE (expire_time IS NULL OR expire_time > ?)'
        )
        if limit is not None: select += f' LIMIT {limit}'
        now = time.time()
        data_results = {}
        rows = self._sql(select, (now,)).fetchall()
        if not rows: return data_results
        for row in rows:
            key, value = row
            data_results[key] = value
        return data_results

    async def afetch_kv_data(self, limit: t.Optional[int] = None, **kwargs) -> t.Dict[str, t.Any]:
        """
        Loads all the Data
        """
        # Since this is a heavy operation, we'll just retrieve it from the DB
        # with a single query
        select = (
            'SELECT key, value'
            f' FROM "{self.table}"'
            ' WHERE (expire_time IS NULL OR expire_time > ?)'
        )
        if limit is not None: select += f' LIMIT {limit}'
        now = time.time()
        data_results = {}
        async with self._atransact() as sql:
            rows = await (await sql(select, (now,))).fetchall()
            if not rows: return data_results
            for row in rows:
                key, value = row
                data_results[key] = value
        return data_results


    def fetch_values(self, limit: t.Optional[int] = None, **kwargs) -> t.List[t.Any]:
        """
        Fetches the values
        """
        select = (
            'SELECT value'
            f' FROM "{self.table}"'
            ' WHERE (expire_time IS NULL OR expire_time > ?)'
        )
        if limit is not None: select += f' LIMIT {limit}'
        now = time.time()
        rows = self._sql(select, (now,)).fetchall()
        return [row[0] for row in rows]

    async def afetch_values(self, limit: t.Optional[int] = None, **kwargs) -> t.List[t.Any]:
        """
        Fetches the values
        """
        select = (
            'SELECT value'
            f' FROM "{self.table}"'
            ' WHERE (expire_time IS NULL OR expire_time > ?)'
        )
        if limit is not None: select += f' LIMIT {limit}'
        now = time.time()
        rows = await (await self._asql(select, (now,))).fetchall()
        return [row[0] for row in rows]
        
    def batch_get(self, *keys: str, default: t.Optional[t.Any] = None, include_meta: bool = False, retry: t.Optional[bool] = False):
        """
        Batch gets many items

        :param keys: keys to get
        :param default: value to return if key is missing
            (default None, no default value)
        :param include_meta: if True, return a dict of metadata
            (default False)
        :param retry: retry if database timeout occurs (default None, no retry)
        :return: dict of key/value pairs or tuple of (key, value) pairs if include_meta is True
        """
        update_column = self.eviction_policies['get']
        select = (
            'SELECT rowid, expire_time, tag, access_count, hit_count, value, key'
            f' FROM "{self.table}" WHERE key IN (%s)'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        ) % self._format_keys_(keys)
        now = time.time()
        meta_results = {}
        batch_results = {}
        def return_noval():
            _batch_results = {key: default for key in keys}
            if include_meta: 
                _meta_results = {key: None for key in keys}
                return _batch_results, _meta_results
            return _batch_results
            
        if not self.statistics and update_column is None:
            # Fast path, no transaction necessary.
            rows = self._sql(select, (now,)).fetchall()
            if not rows:  return return_noval()
            fetched_results = {
                key: (rowid, value, db_expire_time, db_tag, db_access_count, db_hit_count)
                for (rowid, db_expire_time, db_tag, db_access_count, db_hit_count, value, key) in rows
            }
            for key in keys:
                if key not in fetched_results:
                    batch_results[key] = default
                    if include_meta: meta_results[key] = None
                    continue
                (rowid, value, db_expire_time, db_tag, db_access_count, db_hit_count) = fetched_results[key]
                if include_meta: meta_results[key] = {
                    'expire_time': db_expire_time,
                    'tag': db_tag,
                    'rowid': rowid,
                    'access_count': db_access_count,
                    'hits': db_hit_count,
                }
                batch_results[key] = value

        else:  # Slow path, transaction required.
            _result = self._batch_update_statistics(keys, now, select, update_column = update_column, default = default, retry = retry)
            if _result is ENOVAL: return return_noval()
            batch_results, meta_results = _result

        return (batch_results, meta_results) if include_meta else batch_results


    async def abatch_get(self, *keys: str, default: t.Optional[t.Any] = None, include_meta: bool = False, retry: t.Optional[bool] = False):
        """
        Batch gets many items

        :param keys: keys to get
        :param default: value to return if key is missing
            (default None, no default value)
        :param include_meta: if True, return a dict of metadata
            (default False)
        :param retry: retry if database timeout occurs (default None, no retry)
        :return: dict of key/value pairs or tuple of (key, value) pairs if include_meta is True
        """
        update_column = self.eviction_policies['get']
        select = (
            'SELECT rowid, expire_time, tag, access_count, hit_count, value, key'
            f' FROM "{self.table}" WHERE key IN (%s)'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        ) % self._format_keys_(keys)
        now = time.time()
        meta_results = {}
        batch_results = {}
        def return_noval():
            _batch_results = {key: default for key in keys}
            if include_meta: 
                _meta_results = {key: None for key in keys}
                return _batch_results, _meta_results
            return _batch_results
            
        if not self.statistics and update_column is None:
            # Fast path, no transaction necessary.
            rows = await (await self._asql(select, (now,))).fetchall()
            if not rows:  return return_noval()
            fetched_results = {
                key: (rowid, value, db_expire_time, db_tag, db_access_count, db_hit_count)
                for (rowid, db_expire_time, db_tag, db_access_count, db_hit_count, value, key) in rows
            }
            for key in keys:
                if key not in fetched_results:
                    batch_results[key] = default
                    if include_meta: meta_results[key] = None
                    continue
                (rowid, value, db_expire_time, db_tag, db_access_count, db_hit_count) = fetched_results[key]
                if include_meta: meta_results[key] = {
                    'expire_time': db_expire_time,
                    'tag': db_tag,
                    'rowid': rowid,
                    'access_count': db_access_count,
                    'hits': db_hit_count,
                }
                batch_results[key] = value

        else:  # Slow path, transaction required.
            _result = await self._abatch_update_statistics(keys, now, select, update_column = update_column, default = default, retry = retry)
            if _result is ENOVAL: return return_noval()
            batch_results, meta_results = _result

        return (batch_results, meta_results) if include_meta else batch_results

    def _batch_update_statistics(self, keys: t.Iterable[str], now: float, select: str, update_column: t.Optional[str] = None, default: t.Optional[t.Any] = None, retry: bool = False):
        """
        Batch Update The Statics and get the values
        """
        cache_hit = (
            f'UPDATE "{self.table}_settings" SET value = value + <NUM_HITS> WHERE key = "hits"'
        )
        cache_miss = (
            f'UPDATE "{self.table}_settings" SET value = value + <NUM_MISSES> WHERE key = "misses"'
        )
        cache_bulk_miss = (
            f'UPDATE "{self.table}_settings" SET value = value + {len(keys)} WHERE key = "misses"'
        )
        with self._transact(retry) as sql:
            rows = sql(select, (now,)).fetchall()
            if not rows:
                if self.statistics: sql(cache_bulk_miss)
                return ENOVAL
            fetched_results = {
                key: (rowid, value, db_expire_time, db_tag, db_access_count, db_hit_count)
                for (rowid, db_expire_time, db_tag, db_access_count, db_hit_count, value, key) in rows
            }
            meta_results, batch_results = {}, {}
            n_hits, n_misses = 0, 0
            row_ids = []
            for key in keys:
                if key not in fetched_results:
                    batch_results[key] = default
                    meta_results[key] = None
                    n_misses += 1
                    continue
                (rowid, value, db_expire_time, db_tag, db_access_count, db_hit_count) = fetched_results[key]
                meta_results[key] = {
                    'expire_time': db_expire_time,
                    'tag': db_tag,
                    'rowid': rowid,
                    'access_count': db_access_count,
                    'hits': db_hit_count,
                }
                batch_results[key] = value
                n_hits += 1
                # row_ids.append((rowid,))
                row_ids.append(rowid)

            if self.statistics: 
                if n_hits: sql(cache_hit.replace('<NUM_HITS>', str(n_hits)))
                if n_misses: sql(cache_miss.replace('<NUM_MISSES>', str(n_misses)))
            _row_ids = self._format_rowids_(row_ids)
            update = f'UPDATE "{self.table}" SET %s WHERE rowid IN ({_row_ids})'
            if update_column is not None:
                sql(update % update_column.format(now=now))
                # sqlmany(update % update_column.format(now=now), row_ids)
            return batch_results, meta_results

    async def _abatch_update_statistics(self, keys: t.Iterable[str], now: float, select: str, update_column: t.Optional[str] = None, default: t.Optional[t.Any] = None, retry: bool = False):
        """
        [Async] Batch Update The Statics and get the values
        """
        cache_hit = (
            f'UPDATE "{self.table}_settings" SET value = value + <NUM_HITS> WHERE key = "hits"'
        )
        cache_miss = (
            f'UPDATE "{self.table}_settings" SET value = value + <NUM_MISSES> WHERE key = "misses"'
        )
        cache_bulk_miss = (
            f'UPDATE "{self.table}_settings" SET value = value + {len(keys)} WHERE key = "misses"'
        )
        async with self._atransact(retry) as sql:
            rows = await (await sql(select, (now,))).fetchall()
            if not rows:
                if self.statistics: await sql(cache_bulk_miss)
                return ENOVAL
            fetched_results = {
                key: (rowid, value, db_expire_time, db_tag, db_access_count, db_hit_count)
                for (rowid, db_expire_time, db_tag, db_access_count, db_hit_count, value, key) in rows
            }
            meta_results, batch_results = {}, {}
            n_hits, n_misses = 0, 0
            row_ids = []
            for key in keys:
                if key not in fetched_results:
                    batch_results[key] = default
                    meta_results[key] = None
                    n_misses += 1
                    continue
                (rowid, value, db_expire_time, db_tag, db_access_count, db_hit_count) = fetched_results[key]
                meta_results[key] = {
                    'expire_time': db_expire_time,
                    'tag': db_tag,
                    'rowid': rowid,
                    'access_count': db_access_count,
                    'hits': db_hit_count,
                }
                batch_results[key] = value
                n_hits += 1
                row_ids.append(rowid)

            if self.statistics: 
                if n_hits: await sql(cache_hit.replace('<NUM_HITS>', str(n_hits)))
                if n_misses: await sql(cache_miss.replace('<NUM_MISSES>', str(n_misses)))
            _row_ids = self._format_rowids_(row_ids)
            update = f'UPDATE "{self.table}" SET %s WHERE rowid IN ({_row_ids})'
            if update_column is not None:
                await sql(update % update_column.format(now=now))
            return batch_results, meta_results


    def select_tags(
        self, 
        *tags: str, 
        limit: t.Optional[int] = None, 
        order: t.Optional[t.Literal['ASC', 'DESC']] = 'ASC',
        order_by: t.Optional[str] = 'rowid',
        include_meta: bool = False, 
        retry: t.Optional[bool] = True
    ) -> t.Union[t.Dict[str, t.Any], t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]]:
        """
        Select all items with the given tags

        :param tags: tags to select
        :param limit: limit the number of items to return
            (default None, no limit)
        :param order: order to return the items
            (default 'ASC', ascending)
        :param include_meta: if True, return a dict of metadata
            (default False)
        :param retry: retry if database timeout occurs (default True)
        :return: dict of key/value pairs or tuple of (key, value) pairs if include_meta is True
        """
        update_column = self.eviction_policies['get']
        select = (
            f'SELECT rowid, expire_time, tag, access_count, hit_count, value, key'
            f' FROM "{self.table}"'
            ' WHERE tag IN (%s) AND (expire_time IS NULL OR expire_time > ?)'
        ) % self._format_keys_(tags)
        
        if order: select += f' ORDER BY {order_by} {order}'
        if limit: select += f' LIMIT {limit}'
        now = time.time()
        meta_results, batch_results = {}, {}
        rowids = []
        with self._transact(retry) as sql:
            rows = sql(select, (now,)).fetchall()
            if not rows: return {}, {} if include_meta else {}
            for row in rows:
                rowid, expire_time, tag, access_count, hit_count, value, key = row
                batch_results[key] = value
                if include_meta: meta_results[key] = {
                    'expire_time': expire_time,
                    'tag': tag,
                    'rowid': rowid,
                    'access_count': access_count,
                    'hits': hit_count,
                }
                rowids.append(rowid)
            if self.statistics:
                cache_hit = (
                    f'UPDATE "{self.table}_settings" SET value = value + {len(rowids)} WHERE key = "hits"'
                )
                sql(cache_hit)
            
            if update_column is not None:
                _row_ids = self._format_rowids_(rowids)
                update = f'UPDATE "{self.table}" SET %s WHERE rowid IN ({_row_ids})'
                sql(update % update_column.format(now=now))
        return (batch_results, meta_results) if include_meta else batch_results

    
    async def aselect_tags(
        self, 
        *tags: str, 
        limit: t.Optional[int] = None, 
        order: t.Optional[t.Literal['ASC', 'DESC']] = 'ASC',
        order_by: t.Optional[str] = 'rowid',
        include_meta: bool = False, 
        retry: t.Optional[bool] = True
    ) -> t.Union[t.Dict[str, t.Any], t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]]:
        """
        Select all items with the given tags

        :param tags: tags to select
        :param limit: limit the number of items to return
            (default None, no limit)
        :param order: order to return the items
            (default 'ASC', ascending)
        :param include_meta: if True, return a dict of metadata
            (default False)
        :param retry: retry if database timeout occurs (default True)
        :return: dict of key/value pairs or tuple of (key, value) pairs if include_meta is True
        """
        update_column = self.eviction_policies['get']
        select = (
            f'SELECT rowid, expire_time, tag, access_count, hit_count, value, key'
            f' FROM "{self.table}"'
            ' WHERE tag IN (%s) AND (expire_time IS NULL OR expire_time > ?)'
        ) % self._format_keys_(tags)
        
        if order: select += f' ORDER BY {order_by} {order}'
        if limit: select += f' LIMIT {limit}'
        now = time.time()
        meta_results, batch_results = {}, {}
        rowids = []
        async with self._atransact(retry) as sql:
            rows = await (await sql(select, (now,))).fetchall()
            if not rows: return {}, {} if include_meta else {}
            for row in rows:
                rowid, expire_time, tag, access_count, hit_count, value, key = row
                batch_results[key] = value
                if include_meta: meta_results[key] = {
                    'expire_time': expire_time,
                    'tag': tag,
                    'rowid': rowid,
                    'access_count': access_count,
                    'hits': hit_count,
                }
                rowids.append(rowid)
            if self.statistics:
                cache_hit = (
                    f'UPDATE "{self.table}_settings" SET value = value + {len(rowids)} WHERE key = "hits"'
                )
                await sql(cache_hit)
            
            if update_column is not None:
                _row_ids = self._format_rowids_(rowids)
                update = f'UPDATE "{self.table}" SET %s WHERE rowid IN ({_row_ids})'
                await sql(update % update_column.format(now=now))
        return (batch_results, meta_results) if include_meta else batch_results

        

    def read(self, key: str, retry: bool = False):
        """Return file handle value corresponding to `key` from cache.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key matching item
        :param bool retry: retry if database timeout occurs (default False)
        :return: file open for reading in binary mode
        :raises KeyError: if key is not found
        :raises Timeout: if database timeout occurs

        """
        handle = self.get(key, default=ENOVAL, read=True, retry=retry)
        if handle is ENOVAL:
            raise KeyError(key)
        return handle


    def pop(
        self, key: str, default: t.Optional[t.Any] = None, expire_time: bool = False, tag: bool = False, retry: bool = False
    ):  # noqa: E501
        """Remove corresponding item for `key` from cache and return value.

        If `key` is missing, return `default`.

        Operation is atomic. Concurrent operations will be serialized.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param default: value to return if key is missing (default None)
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: value for item or default if key not found
        :raises Timeout: if database timeout occurs

        """
        # db_key, raw = self._disk.put(key)
        select = (
            'SELECT rowid, expire_time, tag, value'
            f' FROM "{self.table}" WHERE key = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )

        if expire_time and tag: default = default, None, None
        elif expire_time or tag: default = default, None
        with self._transact(retry) as sql:
            rows = sql(select, (key, time.time())).fetchall()
            # rows = sql(select, (db_key, raw, time.time())).fetchall()
            if not rows: return default
            ((rowid, db_expire_time, db_tag, value),) = rows
            # ((rowid, db_expire_time, db_tag, mode, filename, db_value),) = rows
            sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))

        if expire_time and tag: return value, db_expire_time, db_tag
        elif expire_time: return value, db_expire_time
        elif tag: return value, db_tag
        else: return value
    
    
    async def apop(
        self, key: str, default: t.Optional[t.Any] = None, expire_time: bool = False, tag: bool = False, retry: bool = False
    ):  # noqa: E501
        """Remove corresponding item for `key` from cache and return value.

        If `key` is missing, return `default`.

        Operation is atomic. Concurrent operations will be serialized.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key for item
        :param default: value to return if key is missing (default None)
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: value for item or default if key not found
        :raises Timeout: if database timeout occurs

        """
        select = (
            'SELECT rowid, expire_time, tag, value'
            f' FROM "{self.table}" WHERE key = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )

        if expire_time and tag: default = default, None, None
        elif expire_time or tag: default = default, None
        async with self._atransact(retry) as sql:
            rows = await (await sql(select, (key, time.time()))).fetchall()
            if not rows: return default
            ((rowid, db_expire_time, db_tag, value),) = rows
            await sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))

        if expire_time and tag: return value, db_expire_time, db_tag
        elif expire_time: return value, db_expire_time
        elif tag: return value, db_tag
        else: return value


    def delete(self, key: str, retry: bool = False):
        """Delete corresponding item for `key` from cache.

        Missing keys are ignored.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key matching item
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was deleted
        :raises Timeout: if database timeout occurs

        """
        # pylint: disable=unnecessary-dunder-call
        try:
            return self._delete_key_(key, retry=retry)
        except KeyError:
            return False
    
    async def adelete(self, key: str, retry: bool = False):
        """Delete corresponding item for `key` from cache.

        Missing keys are ignored.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param key: key matching item
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was deleted
        :raises Timeout: if database timeout occurs

        """
        # pylint: disable=unnecessary-dunder-call
        try:
            return await self._adelete_key_(key, retry=retry)
        except KeyError:
            return False
    
    def push(
        self,
        value: t.Any,
        prefix: t.Optional[str] = None,
        side: t.Literal['back', 'front'] = 'back',
        expire: t.Optional[float] = None,
        read: bool = False,
        tag: t.Optional[str] = None,
        retry: bool = False,
    ):
        """Push `value` onto `side` of queue identified by `prefix` in cache.

        When prefix is None, integer keys are used. Otherwise, string keys are
        used in the format "prefix-integer". Integer starts at 500 trillion.

        Defaults to pushing value on back of queue. Set side to 'front' to push
        value on front of queue. Side must be one of 'back' or 'front'.

        Operation is atomic. Concurrent operations will be serialized.

        When `read` is `True`, `value` should be a file-like object opened
        for reading in binary mode.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        See also `Cache.pull`.

        >>> cache = Cache()
        >>> print(cache.push('first value'))
        500000000000000
        >>> cache.get(500000000000000)
        'first value'
        >>> print(cache.push('second value'))
        500000000000001
        >>> print(cache.push('third value', side='front'))
        499999999999999
        >>> cache.push(1234, prefix='userids')
        'userids-500000000000000'

        :param value: value for item
        :param str prefix: key prefix (default None, key is integer)
        :param str side: either 'back' or 'front' (default 'back')
        :param float expire: seconds until the key expires
            (default None, no expiry)
        :param bool read: read value as bytes from file (default False)
        :param str tag: text to associate with key (default None)
        :param bool retry: retry if database timeout occurs (default False)
        :return: key for item in cache
        :raises Timeout: if database timeout occurs

        """
        if prefix is None:
            min_key = 0
            max_key = 999999999999999
        else:
            min_key = f'{prefix}-000000000000000'
            max_key = f'{prefix}-999999999999999'

        now = time.time()
        # raw = True
        expire_time = None if expire is None else now + expire
        size = self.get_object_size(value)
        columns = (expire_time, tag, size, value)
        # size, mode, filename, db_value = self._disk.store(value, read)
        # columns = (expire_time, tag, size, mode, filename, db_value)
        order = {'back': 'DESC', 'front': 'ASC'}
        select = (
            f'SELECT key FROM "{self.table}"'
            ' WHERE ? < key AND key < ?'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]
        with self._transact(retry) as sql:
            rows = sql(select, (min_key, max_key)).fetchall()
            if rows:
                ((key,),) = rows
                key: str

                num = int(key[(key.rfind('-') + 1) :]) if prefix is not None else key
                if side == 'back': num += 1
                else:
                    assert side == 'front'
                    num -= 1
            else:
                num = 500000000000000
            db_key = '{0}-{1:015d}'.format(prefix, num) if prefix is not None else num
            self._row_insert(db_key, now, columns)
            self._cull(now, sql)
            return db_key
    
    async def apush(
        self,
        value: t.Any,
        prefix: t.Optional[str] = None,
        side: t.Literal['back', 'front'] = 'back',
        expire: t.Optional[float] = None,
        read: bool = False,
        tag: t.Optional[str] = None,
        retry: bool = False,
    ):
        """Push `value` onto `side` of queue identified by `prefix` in cache.

        When prefix is None, integer keys are used. Otherwise, string keys are
        used in the format "prefix-integer". Integer starts at 500 trillion.

        Defaults to pushing value on back of queue. Set side to 'front' to push
        value on front of queue. Side must be one of 'back' or 'front'.

        Operation is atomic. Concurrent operations will be serialized.

        When `read` is `True`, `value` should be a file-like object opened
        for reading in binary mode.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        See also `Cache.pull`.

        >>> cache = Cache()
        >>> print(cache.push('first value'))
        500000000000000
        >>> cache.get(500000000000000)
        'first value'
        >>> print(cache.push('second value'))
        500000000000001
        >>> print(cache.push('third value', side='front'))
        499999999999999
        >>> cache.push(1234, prefix='userids')
        'userids-500000000000000'

        :param value: value for item
        :param str prefix: key prefix (default None, key is integer)
        :param str side: either 'back' or 'front' (default 'back')
        :param float expire: seconds until the key expires
            (default None, no expiry)
        :param bool read: read value as bytes from file (default False)
        :param str tag: text to associate with key (default None)
        :param bool retry: retry if database timeout occurs (default False)
        :return: key for item in cache
        :raises Timeout: if database timeout occurs

        """
        if prefix is None:
            min_key = 0
            max_key = 999999999999999
        else:
            min_key = f'{prefix}-000000000000000'
            max_key = f'{prefix}-999999999999999'

        now = time.time()
        expire_time = None if expire is None else now + expire
        size = self.get_object_size(value)
        columns = (expire_time, tag, size, value)
        order = {'back': 'DESC', 'front': 'ASC'}
        select = (
            f'SELECT key FROM "{self.table}"'
            ' WHERE ? < key AND key < ?'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]
        async with self._atransact(retry) as sql:
            rows = await (await sql(select, (min_key, max_key))).fetchall()
            if rows:
                ((key,),) = rows
                key: str
                num = int(key[(key.rfind('-') + 1) :]) if prefix is not None else key
                if side == 'back': num += 1
                else:
                    assert side == 'front'
                    num -= 1
            else:
                num = 500000000000000
            db_key = '{0}-{1:015d}'.format(prefix, num) if prefix is not None else num
            await self._row_insert(db_key, now, columns, is_async = True)
            # self._cull(now, sql)
            self.abg_cull(now, retry = retry)
            return db_key

    def pull(
        self,
        prefix: t.Optional[str] = None,
        default: t.Tuple[t.Any, t.Any] = (None, None),
        side: t.Literal['front', 'back'] = 'front',
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):
        """Pull key and value item pair from `side` of queue in cache.

        When prefix is None, integer keys are used. Otherwise, string keys are
        used in the format "prefix-integer". Integer starts at 500 trillion.

        If queue is empty, return default.

        Defaults to pulling key and value item pairs from front of queue. Set
        side to 'back' to pull from back of queue. Side must be one of 'front'
        or 'back'.

        Operation is atomic. Concurrent operations will be serialized.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        See also `Cache.push` and `Cache.get`.

        >>> cache = Cache()
        >>> cache.pull()
        (None, None)
        >>> for letter in 'abc':
        ...     print(cache.push(letter))
        500000000000000
        500000000000001
        500000000000002
        >>> key, value = cache.pull()
        >>> print(key)
        500000000000000
        >>> value
        'a'
        >>> _, value = cache.pull(side='back')
        >>> value
        'c'
        >>> cache.push(1234, 'userids')
        'userids-500000000000000'
        >>> _, value = cache.pull('userids')
        >>> value
        1234

        :param str prefix: key prefix (default None, key is integer)
        :param default: value to return if key is missing
            (default (None, None))
        :param str side: either 'front' or 'back' (default 'front')
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: key and value item pair or default if queue is empty
        :raises Timeout: if database timeout occurs

        """
        # Caution: Nearly identical code exists in Cache.peek
        if prefix is None:
            min_key = 0
            max_key = 999999999999999
        else:
            min_key = f'{prefix}-000000000000000'
            max_key = f'{prefix}-999999999999999'

        order = {'front': 'ASC', 'back': 'DESC'}
        select = (
            'SELECT rowid, key, expire_time, tag, value'
            f' FROM "{self.table}" WHERE ? < key AND key < ?'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]

        if expire_time and tag: default = default, None, None
        elif expire_time or tag: default = default, None
        while True:
            while True:
                # with self._transact(retry) as (sql, cleanup):
                with self._transact(retry) as sql:
                    rows = sql(select, (min_key, max_key)).fetchall()
                    if not rows: return default
                    (
                        (rowid, key, db_expire, db_tag, value),
                    ) = rows
                    # (
                    #     (rowid, key, db_expire, db_tag, mode, name, db_value),
                    # ) = rows

                    sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))
                    break
                    # if db_expire is not None and db_expire < time.time():
                    #     cleanup(name)
                    # else:
                    #     break

            # try:
            #     value = self._disk.fetch(mode, name, db_value, False)
            # except IOError:
            #     # Key was deleted before we could retrieve result.
            #     continue
            # finally:
            #     if name is not None:
            #         self._disk.remove(name)
            break

        if expire_time and tag: return (key, value), db_expire, db_tag
        elif expire_time: return (key, value), db_expire
        elif tag: return (key, value), db_tag
        return key, value
    

    async def apull(
        self,
        prefix: t.Optional[str] = None,
        default: t.Tuple[t.Any, t.Any] = (None, None),
        side: t.Literal['front', 'back'] = 'front',
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):
        """Pull key and value item pair from `side` of queue in cache.

        When prefix is None, integer keys are used. Otherwise, string keys are
        used in the format "prefix-integer". Integer starts at 500 trillion.

        If queue is empty, return default.

        Defaults to pulling key and value item pairs from front of queue. Set
        side to 'back' to pull from back of queue. Side must be one of 'front'
        or 'back'.

        Operation is atomic. Concurrent operations will be serialized.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        See also `Cache.push` and `Cache.get`.

        >>> cache = Cache()
        >>> cache.pull()
        (None, None)
        >>> for letter in 'abc':
        ...     print(cache.push(letter))
        500000000000000
        500000000000001
        500000000000002
        >>> key, value = cache.pull()
        >>> print(key)
        500000000000000
        >>> value
        'a'
        >>> _, value = cache.pull(side='back')
        >>> value
        'c'
        >>> cache.push(1234, 'userids')
        'userids-500000000000000'
        >>> _, value = cache.pull('userids')
        >>> value
        1234

        :param str prefix: key prefix (default None, key is integer)
        :param default: value to return if key is missing
            (default (None, None))
        :param str side: either 'front' or 'back' (default 'front')
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: key and value item pair or default if queue is empty
        :raises Timeout: if database timeout occurs

        """
        # Caution: Nearly identical code exists in Cache.peek
        if prefix is None:
            min_key = 0
            max_key = 999999999999999
        else:
            min_key = f'{prefix}-000000000000000'
            max_key = f'{prefix}-999999999999999'

        order = {'front': 'ASC', 'back': 'DESC'}
        select = (
            'SELECT rowid, key, expire_time, tag, value'
            f' FROM "{self.table}" WHERE ? < key AND key < ?'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]

        if expire_time and tag: default = default, None, None
        elif expire_time or tag: default = default, None
        while True:
            while True:
                async with self._atransact(retry) as sql:
                    rows = await (await sql(select, (min_key, max_key))).fetchall()
                    if not rows: return default
                    (
                        (rowid, key, db_expire, db_tag, value),
                    ) = rows
                    await sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))
                    break
            break

        if expire_time and tag: return (key, value), db_expire, db_tag
        elif expire_time: return (key, value), db_expire
        elif tag: return (key, value), db_tag
        return key, value

    def peek(
        self,
        prefix: t.Optional[str] = None,
        default: t.Tuple[t.Any, t.Any] = (None, None),
        side: t.Literal['front', 'back'] = 'front',
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):
        """Peek at key and value item pair from `side` of queue in cache.

        When prefix is None, integer keys are used. Otherwise, string keys are
        used in the format "prefix-integer". Integer starts at 500 trillion.

        If queue is empty, return default.

        Defaults to peeking at key and value item pairs from front of queue.
        Set side to 'back' to pull from back of queue. Side must be one of
        'front' or 'back'.

        Expired items are deleted from cache. Operation is atomic. Concurrent
        operations will be serialized.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        See also `Cache.pull` and `Cache.push`.

        >>> cache = Cache()
        >>> for letter in 'abc':
        ...     print(cache.push(letter))
        500000000000000
        500000000000001
        500000000000002
        >>> key, value = cache.peek()
        >>> print(key)
        500000000000000
        >>> value
        'a'
        >>> key, value = cache.peek(side='back')
        >>> print(key)
        500000000000002
        >>> value
        'c'

        :param str prefix: key prefix (default None, key is integer)
        :param default: value to return if key is missing
            (default (None, None))
        :param str side: either 'front' or 'back' (default 'front')
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: key and value item pair or default if queue is empty
        :raises Timeout: if database timeout occurs

        """
        # Caution: Nearly identical code exists in Cache.pull
        if prefix is None:
            min_key = 0
            max_key = 999999999999999
        else:
            min_key = f'{prefix}-000000000000000'
            max_key = f'{prefix}-999999999999999'

        order = {'front': 'ASC', 'back': 'DESC'}
        select = (
            'SELECT rowid, key, expire_time, tag, value'
            f' FROM "{self.table}" WHERE ? < key AND key < ?'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]

        if expire_time and tag: default = default, None, None
        elif expire_time or tag: default = default, None

        while True:
            while True:
                with self._transact(retry) as sql:
                    rows = sql(select, (min_key, max_key)).fetchall()
                    if not rows: return default
                    (
                        (rowid, key, db_expire, db_tag, value),
                    ) = rows
                    # (
                    #     (rowid, key, db_expire, db_tag, mode, name, db_value),
                    # ) = rows

                    if db_expire is None or db_expire >= time.time(): break
                    sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))
                    # cleanup(name)
            # try:
            #     value = self._disk.fetch(mode, name, db_value, False)
            # except IOError:
            #     # Key was deleted before we could retrieve result.
            #     continue
            break

        if expire_time and tag: return (key, value), db_expire, db_tag
        elif expire_time: return (key, value), db_expire
        elif tag: return (key, value), db_tag
        return key, value
    
    async def apeek(
        self,
        prefix: t.Optional[str] = None,
        default: t.Tuple[t.Any, t.Any] = (None, None),
        side: t.Literal['front', 'back'] = 'front',
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):
        """Peek at key and value item pair from `side` of queue in cache.

        When prefix is None, integer keys are used. Otherwise, string keys are
        used in the format "prefix-integer". Integer starts at 500 trillion.

        If queue is empty, return default.

        Defaults to peeking at key and value item pairs from front of queue.
        Set side to 'back' to pull from back of queue. Side must be one of
        'front' or 'back'.

        Expired items are deleted from cache. Operation is atomic. Concurrent
        operations will be serialized.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        See also `Cache.pull` and `Cache.push`.

        >>> cache = Cache()
        >>> for letter in 'abc':
        ...     print(cache.push(letter))
        500000000000000
        500000000000001
        500000000000002
        >>> key, value = cache.peek()
        >>> print(key)
        500000000000000
        >>> value
        'a'
        >>> key, value = cache.peek(side='back')
        >>> print(key)
        500000000000002
        >>> value
        'c'

        :param str prefix: key prefix (default None, key is integer)
        :param default: value to return if key is missing
            (default (None, None))
        :param str side: either 'front' or 'back' (default 'front')
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: key and value item pair or default if queue is empty
        :raises Timeout: if database timeout occurs

        """
        # Caution: Nearly identical code exists in Cache.pull
        if prefix is None:
            min_key = 0
            max_key = 999999999999999
        else:
            min_key = f'{prefix}-000000000000000'
            max_key = f'{prefix}-999999999999999'

        order = {'front': 'ASC', 'back': 'DESC'}
        select = (
            'SELECT rowid, key, expire_time, tag, value'
            f' FROM "{self.table}" WHERE ? < key AND key < ?'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]

        if expire_time and tag: default = default, None, None
        elif expire_time or tag: default = default, None

        while True:
            while True:
                async with self._atransact(retry) as sql:
                    rows = await (await sql(select, (min_key, max_key))).fetchall()
                    if not rows: return default
                    (
                        (rowid, key, db_expire, db_tag, value),
                    ) = rows
                    if db_expire is None or db_expire >= time.time(): break
                    await sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))
            break
        if expire_time and tag: return (key, value), db_expire, db_tag
        elif expire_time: return (key, value), db_expire
        elif tag: return (key, value), db_tag
        return key, value

    def peekitem(self, last: bool = True, expire_time: bool = False, tag: bool = False, retry: bool = False):
        """Peek at key and value item pair in cache based on iteration order.

        Expired items are deleted from cache. Operation is atomic. Concurrent
        operations will be serialized.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        >>> cache = Cache()
        >>> for num, letter in enumerate('abc'):
        ...     cache[letter] = num
        >>> cache.peekitem()
        ('c', 2)
        >>> cache.peekitem(last=False)
        ('a', 0)

        :param bool last: last item in iteration order (default True)
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: key and value item pair
        :raises KeyError: if cache is empty
        :raises Timeout: if database timeout occurs

        """
        order = ('ASC', 'DESC')
        select = (
            'SELECT rowid, key, expire_time, tag, value'
            f' FROM "{self.table}" ORDER BY rowid %s LIMIT 1'
        ) % order[last]

        while True:
            while True:
                with self._transact(retry) as sql:
                    rows = sql(select).fetchall()
                    if not rows: raise KeyError('dictionary is empty')
                    (
                        (
                            rowid,
                            key,
                            db_expire,
                            db_tag,
                            value,
                        ),
                    ) = rows

                    if db_expire is not None and db_expire < time.time():
                        sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))
                    else:
                        break

            break

        if expire_time and tag: return (key, value), db_expire, db_tag
        elif expire_time: return (key, value), db_expire
        elif tag: return (key, value), db_tag
        return key, value
    
    async def apeekitem(self, last: bool = True, expire_time: bool = False, tag: bool = False, retry: bool = False):
        """Peek at key and value item pair in cache based on iteration order.

        Expired items are deleted from cache. Operation is atomic. Concurrent
        operations will be serialized.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        >>> cache = Cache()
        >>> for num, letter in enumerate('abc'):
        ...     cache[letter] = num
        >>> cache.peekitem()
        ('c', 2)
        >>> cache.peekitem(last=False)
        ('a', 0)

        :param bool last: last item in iteration order (default True)
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: key and value item pair
        :raises KeyError: if cache is empty
        :raises Timeout: if database timeout occurs

        """
        order = ('ASC', 'DESC')
        select = (
            'SELECT rowid, key, expire_time, tag, value'
            f' FROM "{self.table}" ORDER BY rowid %s LIMIT 1'
        ) % order[last]

        while True:
            while True:
                async with self._atransact(retry) as sql:
                    rows = await (await sql(select)).fetchall()
                    if not rows: raise KeyError('dictionary is empty')
                    (
                        (
                            rowid,
                            key,
                            db_expire,
                            db_tag,
                            value,
                        ),
                    ) = rows
                    if db_expire is not None and db_expire < time.time():
                        await sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))
                    else:
                        break
            break

        if expire_time and tag: return (key, value), db_expire, db_tag
        elif expire_time: return (key, value), db_expire
        elif tag: return (key, value), db_tag
        return key, value

    def evict(self, tag: str, retry: bool = False):
        """Remove items with matching `tag` from cache.

        Removing items is an iterative process. In each iteration, a subset of
        items is removed. Concurrent writes may occur between iterations.

        If a :exc:`Timeout` occurs, the first element of the exception's
        `args` attribute will be the number of items removed before the
        exception occurred.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param str tag: tag identifying items
        :param bool retry: retry if database timeout occurs (default False)
        :return: count of rows removed
        :raises Timeout: if database timeout occurs

        """
        select = (
            f'SELECT rowid FROM "{self.table}"'
            ' WHERE tag = ? AND rowid > ?'
            ' ORDER BY rowid LIMIT ?'
        )
        args = [tag, 0, 100]
        return self._select_delete(select, args, arg_index=1, retry=retry)
    

    async def aevict(self, tag: str, retry: bool = False):
        """Remove items with matching `tag` from cache.

        Removing items is an iterative process. In each iteration, a subset of
        items is removed. Concurrent writes may occur between iterations.

        If a :exc:`Timeout` occurs, the first element of the exception's
        `args` attribute will be the number of items removed before the
        exception occurred.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param str tag: tag identifying items
        :param bool retry: retry if database timeout occurs (default False)
        :return: count of rows removed
        :raises Timeout: if database timeout occurs

        """
        select = (
            f'SELECT rowid FROM "{self.table}"'
            ' WHERE tag = ? AND rowid > ?'
            ' ORDER BY rowid LIMIT ?'
        )
        args = [tag, 0, 100]
        return await self._aselect_delete(select, args, arg_index=1, retry=retry)
    

    def clear(self, retry=False):
        """Remove all items from cache.

        Removing items is an iterative process. In each iteration, a subset of
        items is removed. Concurrent writes may occur between iterations.

        If a :exc:`Timeout` occurs, the first element of the exception's
        `args` attribute will be the number of items removed before the
        exception occurred.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param bool retry: retry if database timeout occurs (default False)
        :return: count of rows removed
        :raises Timeout: if database timeout occurs

        """
        select = (
            f'SELECT rowid FROM "{self.table}"'
            ' WHERE rowid > ?'
            ' ORDER BY rowid LIMIT ?'
        )
        args = [0, 100]
        return self._select_delete(select, args, retry=retry)


    async def aclear(self, retry=False):
        """Remove all items from cache.

        Removing items is an iterative process. In each iteration, a subset of
        items is removed. Concurrent writes may occur between iterations.

        If a :exc:`Timeout` occurs, the first element of the exception's
        `args` attribute will be the number of items removed before the
        exception occurred.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param bool retry: retry if database timeout occurs (default False)
        :return: count of rows removed
        :raises Timeout: if database timeout occurs

        """
        select = (
            f'SELECT rowid FROM "{self.table}"'
            ' WHERE rowid > ?'
            ' ORDER BY rowid LIMIT ?'
        )
        args = [0, 100]
        return await self._aselect_delete(select, args, retry=retry)

    def expire(self, now: Optional[float] = None, retry: bool = False):
        """Remove expired items from cache.

        Removing items is an iterative process. In each iteration, a subset of
        items is removed. Concurrent writes may occur between iterations.

        If a :exc:`Timeout` occurs, the first element of the exception's
        `args` attribute will be the number of items removed before the
        exception occurred.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param float now: current time (default None, ``time.time()`` used)
        :param bool retry: retry if database timeout occurs (default False)
        :return: count of items removed
        :raises Timeout: if database timeout occurs

        """
        select = (
            f'SELECT rowid, expire_time FROM "{self.table}"'
            ' WHERE ? < expire_time AND expire_time < ?'
            ' ORDER BY expire_time LIMIT ?'
        )
        args = [0, now or time.time(), 100]
        return self._select_delete(select, args, row_index=1, retry=retry)

    
    async def aexpire(self, now: Optional[float] = None, retry: bool = False):
        """Remove expired items from cache.

        Removing items is an iterative process. In each iteration, a subset of
        items is removed. Concurrent writes may occur between iterations.

        If a :exc:`Timeout` occurs, the first element of the exception's
        `args` attribute will be the number of items removed before the
        exception occurred.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param float now: current time (default None, ``time.time()`` used)
        :param bool retry: retry if database timeout occurs (default False)
        :return: count of items removed
        :raises Timeout: if database timeout occurs

        """
        select = (
            f'SELECT rowid, expire_time FROM "{self.table}"'
            ' WHERE ? < expire_time AND expire_time < ?'
            ' ORDER BY expire_time LIMIT ?'
        )
        args = [0, now or time.time(), 100]
        return await self._aselect_delete(select, args, row_index=1, retry=retry)
    
    
    def cull(self, retry: bool = False):
        """Cull items from cache until volume is less than size limit.

        Removing items is an iterative process. In each iteration, a subset of
        items is removed. Concurrent writes may occur between iterations.

        If a :exc:`Timeout` occurs, the first element of the exception's
        `args` attribute will be the number of items removed before the
        exception occurred.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param bool retry: retry if database timeout occurs (default False)
        :return: count of items removed
        :raises Timeout: if database timeout occurs

        """
        now = time.time()
        # Remove expired items.
        count = self.expire(now)
        # Remove items by policy.
        select_policy = self.eviction_policies['cull']
        if select_policy is None: return 0

        select_key = select_policy.format(fields='key', now=now)
        # select_filename = select_policy.format(fields='filename', now=now)

        try:
            while self.volume() > self.size_limit:
                with self._transact(retry) as sql:
                    rows = sql(select_key, (10,)).fetchall()
                # with self._transact(retry) as (sql, cleanup):
                #     rows = sql(select_filename, (10,)).fetchall()

                    if not rows: break
                    count += len(rows)
                    delete = (
                        f'DELETE FROM "{self.table}" WHERE rowid IN (%s)'
                        % select_policy.format(fields='rowid', now=now)
                    )
                    sql(delete, (10,))

                    # for (filename,) in rows:
                    #     cleanup(filename)
        except Timeout:
            raise Timeout(count) from None

        return count
    
    async def acull(self, retry: bool = False):
        """Cull items from cache until volume is less than size limit.

        Removing items is an iterative process. In each iteration, a subset of
        items is removed. Concurrent writes may occur between iterations.

        If a :exc:`Timeout` occurs, the first element of the exception's
        `args` attribute will be the number of items removed before the
        exception occurred.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        :param bool retry: retry if database timeout occurs (default False)
        :return: count of items removed
        :raises Timeout: if database timeout occurs

        """
        now = time.time()
        # Remove expired items.
        count = await self.aexpire(now)
        # Remove items by policy.
        select_policy = self.eviction_policies['cull']
        if select_policy is None: return 0

        select_key = select_policy.format(fields='key', now=now)
        try:
            while (await self.avolume()) > self.size_limit:
                async with self._atransact(retry) as sql:
                    rows = await (await sql(select_key, (10,))).fetchall()
                    if not rows: break
                    count += len(rows)
                    delete = (
                        f'DELETE FROM "{self.table}" WHERE rowid IN (%s)'
                        % select_policy.format(fields='rowid', now=now)
                    )
                    await sql(delete, (10,))
        except Timeout:
            raise Timeout(count) from None
        return count


    """
    Class Methods
    """

    def __setitem__(self, key: str, value: t.Any):
        """Set corresponding `value` for `key` in cache.

        :param key: key for item
        :param value: value for item
        :return: corresponding value
        :raises KeyError: if key is not found

        """
        self.set(key, value, retry=True)
    

    def __getitem__(self, key: str):
        """Return corresponding value for `key` from cache.

        :param key: key matching item
        :return: corresponding value
        :raises KeyError: if key is not found

        """
        value = self.get(key, default=ENOVAL, retry=True)
        if value is ENOVAL: raise KeyError(key)
        return value
    

    def __contains__(self, key: str) -> bool:
        """Return `True` if `key` matching item is found in cache.

        :param key: key matching item
        :return: True if key matching item

        """
        return self.contains(key)
    
    def __delitem__(self, key: str, retry: bool = True):
        """Delete corresponding item for `key` from cache.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default `True`).

        :param key: key matching item
        :param bool retry: retry if database timeout occurs (default True)
        :raises KeyError: if key is not found
        :raises Timeout: if database timeout occurs

        """
        return self._delete_key_(key, retry=retry)
    

    def __len__(self):
        """Count of items in cache including expired items."""
        return self.length()
    
