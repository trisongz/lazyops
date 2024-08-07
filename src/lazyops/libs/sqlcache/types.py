from __future__ import annotations

import os
import io
import abc
import zlib
import errno
import time
import struct
import sqlite3
import threading
import pickletools
import asyncio
import inspect
import dill as pkl
import functools as ft
import contextlib as cl
import warnings
from fileio.lib.types import File, FileLike
from typing import Any, Optional, Type, Dict, Union, Tuple, TYPE_CHECKING
from lazyops.utils.pooler import ThreadPooler

from lazyops.libs.sqlcache.constants import (
    UNKNOWN,
    MODE_NONE,
    MODE_RAW,
    MODE_TEXT,
    MODE_BINARY,
    MODE_PICKLE,
    ENOVAL,
    KeyT,
    ValueT,
    METADATA,
    WindowsExceptionError,
)

from lazyops.libs.sqlcache.config import SqlCacheConfig
from lazyops.libs.sqlcache.exceptions import (
    SqlTimeout, UnknownFileWarning, EmptyDirWarning
)
from lazyops.libs.sqlcache.utils import (
    full_name,
    args_to_key,

)

class BaseMedium(abc.ABC):

    pickle_protocol: int = 3

    """
    Base Medium Class for SqlCache
    """

    def serialize(self, value: ValueT, protocol: Optional[Any] = None, optimize: Optional[bool] = False, **kwargs) -> bytes:
        """
        Serialize value to bytes
        """
        protocol = protocol or self.pickle_protocol
        data = pkl.dumps(value, protocol=self.pickle_protocol)
        if optimize: data = pickletools.optimize(data)
        return data
    
    async def aserialize(self, value: ValueT, protocol: Optional[Any] = None, optimize: Optional[bool] = False, **kwargs) -> bytes:
        """
        Serialize value to bytes
        """
        return await ThreadPooler.run_async(
            self.serialize,
            value,
            protocol,
            optimize,
            **kwargs
        )

    def deserialize(self, data: bytes, **kwargs) -> ValueT:
        """
        Deserialize bytes to value
        """
        return pkl.loads(data)

    async def adeserialize(self, data: bytes, **kwargs) -> ValueT:
        """
        Deserialize bytes to value
        """
        return await ThreadPooler.run_async(
            self.deserialize,
            data,
            **kwargs
        )

    def hash(self, key: KeyT):
        """Compute portable hash for `key`.
        :param key: key to hash
        :return: hash value
        """
        mask = 0xFFFFFFFF
        disk_key, _ = self.put(key)
        type_disk_key = type(disk_key)

        if type_disk_key is sqlite3.Binary:
            return zlib.adler32(disk_key) & mask
        elif type_disk_key is str:
            return zlib.adler32(disk_key.encode('utf-8')) & mask  # noqa
        elif type_disk_key is int:
            return disk_key % mask
        else:
            assert type_disk_key is float
            return zlib.adler32(struct.pack('!d', disk_key)) & mask

    async def ahash(self, key: KeyT):
        """Compute portable hash for `key`.
        :param key: key to hash
        :return: hash value
        """
        return await ThreadPooler.run_async(
            self.hash,
            key
        )
    

    def put(self, key: KeyT):
        """Convert `key` to fields key and raw for Store table.
        :param key: key to convert
        :return: (database key, raw boolean) pair
        """
        # pylint: disable=unidiomatic-typecheck
        type_key = type(key)
        if type_key is bytes:
            return sqlite3.Binary(key), True
        elif (
            (type_key is str)
            or (
                type_key is int
                and -9223372036854775808 <= key <= 9223372036854775807
            )
            or (type_key is float)
        ):
            return key, True
        else:
            result = self.serialize(key, optimize=True)
            return sqlite3.Binary(result), False
    
    async def aput(self, key: KeyT):
        """Convert `key` to fields key and raw for Store table.
        :param key: key to convert
        :return: (database key, raw boolean) pair
        """
        return await ThreadPooler.run_async(
            self.put,
            key
        )


    def get(self, key: KeyT, raw: bool):
        """Convert fields `key` and `raw` from Store table to key.
        :param key: database key to convert
        :param bool raw: flag indicating raw database storage
        :return: corresponding Python key
        """
        # pylint: disable=no-self-use,unidiomatic-typecheck
        if raw:
            return bytes(key) if type(key) is sqlite3.Binary else key
        else:
            return self.deserialize(io.BytesIO(key))
    
    async def aget(self, key: KeyT, raw: bool):
        """Convert fields `key` and `raw` from Store table to key.
        :param key: database key to convert
        :param bool raw: flag indicating raw database storage
        :return: corresponding Python key
        """
        if raw:
            return bytes(key) if type(key) is sqlite3.Binary else key
        else:
            return await self.adeserialize(io.BytesIO(key))

    def store(self, value: ValueT, read: bool, key: KeyT = UNKNOWN):
        """Convert `value` to fields size, mode, filename, and value for Store
        table.
        :param value: value to convert
        :param bool read: True when value is file-like object
        :param key: key for item (default UNKNOWN)
        :return: (size, mode, filename, value) tuple for Store table
        """
        raise NotImplementedError
    
    async def astore(self, value: ValueT, read: bool, key: KeyT = UNKNOWN):
        """Convert `value` to fields size, mode, filename, and value for Store
        table.
        :param value: value to convert
        :param bool read: True when value is file-like object
        :param key: key for item (default UNKNOWN)
        :return: (size, mode, filename, value) tuple for Store table
        """
        raise NotImplementedError
    

    def _write(self, *args, **kwargs):
        """Write `value` to file-like object `file`.
        :param file: file-like object
        :param value: value to write
        """
        raise NotImplementedError
    
    async def _awrite(self, *args, **kwargs):
        """Write `value` to file-like object `file`.
        :param file: file-like object
        :param value: value to write
        """
        raise NotImplementedError
    
    def fetch(self, *args, **kwargs):
        """Fetch value from file-like object `file`.
        :param file: file-like object
        :return: value
        """
        raise NotImplementedError
    
    async def afetch(self, *args, **kwargs):
        """Fetch value from file-like object `file`.
        :param file: file-like object
        :return: value
        """
        raise NotImplementedError
    
    def filename(self, key: KeyT = UNKNOWN, value: ValueT = UNKNOWN):
        """Return filename and full-path tuple for file storage.
        Filename will be a randomly generated 28 character hexadecimal string
        with ".val" suffixed. Two levels of sub-directories will be used to
        reduce the size of directories. On older filesystems, lookups in
        directories with many files may be slow.
        The default implementation ignores the `key` and `value` parameters.
        In some scenarios, for example :meth:`Store.push
        <diskcache.Store.push>`, the `key` or `value` may not be known when the
        item is stored in the cache.
        :param key: key for item (default UNKNOWN)
        :param value: value for item (default UNKNOWN)
        """
        raise NotImplementedError
    
    def remove(self, *args, **kwargs):
        """Remove a file given by `filename`.
        This method is cross-thread and cross-process safe. If an "error no
        entry" occurs, it is suppressed.
        :param str filename: relative path to file
        """
        raise NotImplementedError
    
    async def aremove(self, *args, **kwargs):
        """Remove a file given by `filename`.
        This method is cross-thread and cross-process safe. If an "error no
        entry" occurs, it is suppressed.
        :param str filename: relative path to file
        """
        raise NotImplementedError
    


class BaseBackend(abc.ABC):
    """
    Base Caching Backend
    """

    # timeout: int = 60
    table_name: str = "sqlCache"
    connection_path: Union[str, FileLike]
    # medium: Type[BaseMedium]
    config: SqlCacheConfig
    settings: Dict[str, Any]

    count: Optional[int] = 0
    size: Optional[int] = 0

    def __init__(
        self, 
        medium: Type[BaseMedium], 
        connection_path: Optional[Union[str, FileLike]] = None,
        filename: Optional[str] = None,
        table_name: str = "sqlCache",
        timeout: int = 60,
        config: Union[str, Dict[str, Any]] = None,
        **kwargs
    ):
        """
        :param connection_path: path to database file
        :param medium: storage medium
        :param timeout: timeout for acquiring lock
        :param config: configuration file or dictionary
        :param kwargs: additional keyword arguments
        """
        self._medium_type = medium
        # self.timeout = timeout
        self.init_connection_path(connection_path)
        self._timeout = 0  # Manually handle retries during initialization.
        self._local = threading.local()
        self._txn_id = None
        self.init_config(table_name = table_name, config = config, filename = filename, **kwargs)
        self.init_conn(timeout = timeout)

    def init_connection_path(self, connection_path: Optional[Union[str, FileLike]] = None):
        """
        Handles initialization of connection path
        """
        self.connection_path = File(connection_path) if connection_path \
            else File.get_tempdir(prefix = 'kops-')
    

    def init_config(self, table_name: str, config: Union[str, Dict[str, Any]], filename: Optional[str] = None, **kwargs):
        """
        Handles initialization of config
        """
        if isinstance(config, str):
            self.config = SqlCacheConfig.from_optimized(
                table_name = table_name,
                optim = config,
                config = kwargs
            )
        elif isinstance(config, dict):
            self.config = SqlCacheConfig(
                table_name = table_name,
                **config,
                **kwargs
            )
        elif isinstance(config, SqlCacheConfig):
            self.config = config
        else:
            raise TypeError("config must be str, dict, or SqlCacheConfig")

        self.settings = self.config.sql_settings
        self.eviction_policy = self.config.eviction_policy_config
        self.filename = filename or self.config.db_name
        if '.db' not in self.filename:
            self.filename += '.db'
    
    def init_conn(
        self, 
        timeout: int,
        **kwargs
    ):
        """
        Handles initialization of connection
        """
        sql = self._sql_retry

        # Setup Settings table.

        try:
            current_settings = dict(sql(f'SELECT key, value FROM Settings_{self.table_name}').fetchall())
        except sqlite3.OperationalError:
            current_settings = {}

        sets = self.settings.copy()
        sets.update(current_settings)

        for key in METADATA:
            sets.pop(key, None)

        # Chance to set pragmas before any tables are created.

        for key, value in sorted(sets.items()):
            if key.startswith('sqlite_'):
                self.reset(key, value, update = False)

        sql(
            f'CREATE TABLE IF NOT EXISTS Settings_{self.table_name} ('
            ' key TEXT NOT NULL UNIQUE,'
            ' value)'
        )

        # Setup Disk object (must happen after settings initialized).

        kwargs = {
            key[5:]: value
            for key, value in sets.items()
            if key.startswith('disk_')
        }

        self._medium = self._medium_type(self.connection_path, **kwargs)

        # Set cached attributes: updates settings and sets pragmas.
        for key, value in sets.items():
            query = f'INSERT OR REPLACE INTO Settings_{self.table_name} VALUES (?, ?)'
            sql(query, (key, value))
            self.reset(key, value)

        for key, value in METADATA.items():
            query = f'INSERT OR IGNORE INTO Settings_{self.table_name} VALUES (?, ?)'
            sql(query, (key, value))
            self.reset(key)

        ((self._page_size,),) = sql('PRAGMA page_size').fetchall()

        # Setup Store table.
        sql(
            f'CREATE TABLE IF NOT EXISTS {self.table_name} ('
            ' rowid INTEGER PRIMARY KEY,'
            ' key BLOB,'
            ' raw INTEGER,'
            ' store_time REAL,'
            ' expire_time REAL,'
            ' access_time REAL,'
            ' access_count INTEGER DEFAULT 0,'
            ' tag BLOB,'
            ' size INTEGER DEFAULT 0,'
            ' mode INTEGER DEFAULT 0,'
            ' filename TEXT,'
            ' value BLOB)'
        )

        sql(
            'CREATE UNIQUE INDEX IF NOT EXISTS Store_key_raw ON'
            f' {self.table_name}(key, raw)'
        )

        sql(
            'CREATE INDEX IF NOT EXISTS Store_expire_time ON'
            f' {self.table_name} (expire_time)'
        )

        query = self.eviction_policy['init']
        if query is not None: sql(query)

        # Use triggers to keep Metadata updated.
        sql(
            f'CREATE TRIGGER IF NOT EXISTS Settings_{self.table_name}_count_insert'
            f' AFTER INSERT ON {self.table_name} FOR EACH ROW BEGIN'
            f' UPDATE Settings_{self.table_name} SET value = value + 1'
            ' WHERE key = "count"; END'
        )

        sql(
            f'CREATE TRIGGER IF NOT EXISTS Settings_{self.table_name}_count_delete'
            f' AFTER DELETE ON {self.table_name} FOR EACH ROW BEGIN'
            f' UPDATE Settings_{self.table_name} SET value = value - 1'
            ' WHERE key = "count"; END'
        )

        sql(
            f'CREATE TRIGGER IF NOT EXISTS Settings_{self.table_name}_size_insert'
            f' AFTER INSERT ON {self.table_name} FOR EACH ROW BEGIN'
            f' UPDATE Settings_{self.table_name} SET value = value + NEW.size'
            ' WHERE key = "size"; END'
        )

        sql(
            f'CREATE TRIGGER IF NOT EXISTS Settings_{self.table_name}_size_update'
            f' AFTER UPDATE ON {self.table_name} FOR EACH ROW BEGIN'
            f' UPDATE Settings_{self.table_name}'
            ' SET value = value + NEW.size - OLD.size'
            ' WHERE key = "size"; END'
        )

        sql(
            f'CREATE TRIGGER IF NOT EXISTS Settings_{self.table_name}_size_delete'
            f' AFTER DELETE ON {self.table_name} FOR EACH ROW BEGIN'
            f' UPDATE Settings_{self.table_name} SET value = value - OLD.size'
            ' WHERE key = "size"; END'
        )

        # Create tag index if requested.
        if self.config.tag_index:  # pylint: disable=no-member
            self.create_tag_index()
        else:
            self.drop_tag_index()

        # Close and re-open database connection with given timeout.

        self.close()
        self._timeout = timeout
        
        self._sql  # pylint: disable=pointless-statement


    def get_conn(self, **kwargs) -> sqlite3.Connection:
        """
        Handles initialization of connection
        """
        return sqlite3.connect(
            self.connection_path.joinpath(self.config.table_name),
            timeout = self._timeout,
            isolation_level = None
        )


    @property
    def timeout(self):
        """SQLite connection timeout value in seconds."""
        return self._timeout

    @property
    def medium(self):
        """Medium used for serialization."""
        return self._medium

    @property
    def _con(self):
        # Check process ID to support process forking. If the process
        # ID changes, close the connection and update the process ID.

        local_pid = getattr(self._local, 'pid', None)
        pid = os.getpid()

        if local_pid != pid:
            self.close()
            self._local.pid = pid

        con = getattr(self._local, 'con', None)

        if con is None:
            con = self._local.con = self.get_conn()
            # Some SQLite pragmas work on a per-connection basis so
            # query the Settings table and reset the pragmas. The
            # Settings table may not exist so catch and ignore the
            # OperationalError that may occur.
            with cl.suppress(sqlite3.OperationalError):
                select = f'SELECT key, value FROM Settings_{self.table_name}'
                settings = con.execute(select).fetchall()
                for key, value in settings:
                    if key.startswith('sqlite_'):
                        self.reset(key, value, update=False)
                
        return con

    
    @property
    def _sql(self):
        return self._con.execute
    
    @property
    def _asql(self):
        """
        Async Execute
        """
        return ft.partial(ThreadPooler.run_async, self._con.execute)

    @property
    def _sql_retry(self):
        sql = self._sql

        # 2018-11-01 GrantJ - Some SQLite builds/versions handle
        # the SQLITE_BUSY return value and connection parameter
        # "timeout" differently. For a more reliable duration,
        # manually retry the statement for 60 seconds. Only used
        # by statements which modify the database and do not use
        # a transaction (like those in ``__init__`` or ``reset``).
        # See Issue #85 for and tests/issue_85.py for more details.

        def _execute_with_retry(statement, *args, **kwargs):
            start = time.time()
            while True:
                try:
                    return sql(statement, *args, **kwargs)
                except sqlite3.OperationalError as exc:
                    if str(exc) != 'database is locked':
                        raise
                    diff = time.time() - start
                    if diff > 60:
                        raise
                    time.sleep(0.001)

        return _execute_with_retry


    @property
    def _asql_retry(self):
        asql = self._asql

        async def _aexecute_with_retry(statement, *args, **kwargs):
            start = asyncio.get_event_loop().time()
            while True:
                try:
                    return await asql(statement, *args, **kwargs)
                except sqlite3.OperationalError as exc:
                    if str(exc) != 'database is locked':
                        raise
                    diff = asyncio.get_event_loop().time() - start
                    if diff > 60:
                        raise
                    await asyncio.sleep(0.001)

        return _aexecute_with_retry


    def volume(self):
        """Return estimated total size of cache on disk.
        :return: size in bytes
        """
        ((page_count,),) = self._sql('PRAGMA page_count').fetchall()
        return self._page_size * page_count + self.reset('size')
    


    @cl.contextmanager
    def transact(self, retry=False):
        """Context manager to perform a transaction by locking the cache.
        While the cache is locked, no other write operation is permitted.
        Transactions should therefore be as short as possible. Read and write
        operations performed in a transaction are atomic. Read operations may
        occur concurrent to a transaction.
        Transactions may be nested and may not be shared between threads.
        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).
        >>> cache = Store()
        >>> with cache.transact():  # Atomically increment two keys.
        ...     _ = cache.incr('total', 123.4)
        ...     _ = cache.incr('count', 1)
        >>> with cache.transact():  # Atomically calculate average.
        ...     average = cache['total'] / cache['count']
        >>> average
        123.4
        :param bool retry: retry if database timeout occurs (default False)
        :return: context manager for use in `with` statement
        :raises Timeout: if database timeout occurs
        """
        with self._transact(retry=retry):
            yield

    @cl.contextmanager
    def _transact(
        self, 
        retry: bool = False, 
        filename: str = None
    ):
        sql = self._sql
        filenames = []
        tid = threading.get_ident()
        txn_id = self._txn_id
        if tid == txn_id: begin = False
        else:
            while True:
                try:
                    sql('BEGIN IMMEDIATE')
                    begin = True
                    self._txn_id = tid
                    break
                except sqlite3.OperationalError:
                    if retry: continue
                    if filename is not None:
                        self.medium.remove(filename)
                    raise SqlTimeout from None

        try:
            yield sql, filenames.append
        except BaseException:
            if begin:
                assert self._txn_id == tid
                self._txn_id = None
                sql('ROLLBACK')
            raise
        else:
            if begin:
                assert self._txn_id == tid
                self._txn_id = None
                sql('COMMIT')
            for name in filenames:
                if name is not None:
                    self.medium.remove(name)
    

    @cl.asynccontextmanager
    async def atransact(self, retry=False):
        """Context manager to perform a transaction by locking the cache.
        While the cache is locked, no other write operation is permitted.
        Transactions should therefore be as short as possible. Read and write
        operations performed in a transaction are atomic. Read operations may
        occur concurrent to a transaction.
        Transactions may be nested and may not be shared between threads.
        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).
        >>> cache = Store()
        >>> with cache.transact():  # Atomically increment two keys.
        ...     _ = cache.incr('total', 123.4)
        ...     _ = cache.incr('count', 1)
        >>> with cache.transact():  # Atomically calculate average.
        ...     average = cache['total'] / cache['count']
        >>> average
        123.4
        :param bool retry: retry if database timeout occurs (default False)
        :return: context manager for use in `with` statement
        :raises Timeout: if database timeout occurs
        """
        async with self._atransact(retry = retry):
            yield

    async def _atransact(
        self, 
        retry: bool = False, 
        filename: str = None
    ):
        sql = self._asql
        filenames = []
        tid = threading.get_ident()
        txn_id = self._txn_id
        if tid == txn_id: begin = False
        else:
            while True:
                try:
                    sql('BEGIN IMMEDIATE')
                    begin = True
                    self._txn_id = tid
                    break
                except sqlite3.OperationalError:
                    if retry: continue
                    if filename is not None:
                        await self.medium.aremove(filename)
                    raise SqlTimeout from None

        try:
            yield sql, filenames.append
        except BaseException:
            if begin:
                assert self._txn_id == tid
                self._txn_id = None
                sql('ROLLBACK')
            raise
        else:
            if begin:
                assert self._txn_id == tid
                self._txn_id = None
                sql('COMMIT')
            for name in filenames:
                if name is not None:
                    await self.medium.aremove(name)
    


    def set(self, key: KeyT, value: ValueT, expire: float = None, read: bool = False, tag: str = None, retry: bool = False):
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
        db_key, raw = self.medium.put(key)
        expire_time = None if expire is None else now + expire
        size, mode, filename, db_value = self.medium.store(value, read, key=key)
        columns = (expire_time, tag, size, mode, filename, db_value)

        # The order of SELECT, UPDATE, and INSERT is important below.
        #
        # Typical cache usage pattern is:
        #
        # value = cache.get(key)
        # if value is None:
        #     value = expensive_calculation()
        #     cache.set(key, value)
        #
        # Store.get does not evict expired keys to avoid writes during lookups.
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

        with self._transact(retry, filename) as (sql, cleanup):
            rows = sql(
                f'SELECT rowid, filename FROM {self.table_name}'
                ' WHERE key = ? AND raw = ?',
                (db_key, raw),
            ).fetchall()

            if rows:
                ((rowid, old_filename),) = rows
                cleanup(old_filename)
                self._row_update(rowid, now, columns)
            else:
                self._row_insert(db_key, raw, now, columns)

            self._cull(now, sql, cleanup)

            return True

    def __setitem__(self, key, value):
        """Set corresponding `value` for `key` in cache.
        :param key: key for item
        :param value: value for item
        :return: corresponding value
        :raises KeyError: if key is not found
        """
        self.set(key, value, retry=True)

    
    def _row_update(self, rowid, now, columns):
        sql = self._sql
        expire_time, tag, size, mode, filename, value = columns
        sql(
            f'UPDATE {self.table_name} SET'
            ' store_time = ?,'
            ' expire_time = ?,'
            ' access_time = ?,'
            ' access_count = ?,'
            ' tag = ?,'
            ' size = ?,'
            ' mode = ?,'
            ' filename = ?,'
            ' value = ?'
            ' WHERE rowid = ?',
            (
                now,  # store_time
                expire_time,
                now,  # access_time
                0,  # access_count
                tag,
                size,
                mode,
                filename,
                value,
                rowid,
            ),
        )

    def _row_insert(self, key, raw, now, columns):
        sql = self._sql
        expire_time, tag, size, mode, filename, value = columns
        sql(
            f'INSERT INTO {self.table_name}('
            ' key, raw, store_time, expire_time, access_time,'
            ' access_count, tag, size, mode, filename, value'
            ') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                key,
                raw,
                now,  # store_time
                expire_time,
                now,  # access_time
                0,  # access_count
                tag,
                size,
                mode,
                filename,
                value,
            ),
        )

    
    def _cull(self, now, sql, cleanup, limit: int = None):
        cull_limit = self.config.cull_limit if limit is None else limit
        if cull_limit == 0: return

        # Evict expired keys.
        select_expired_template = (
            f'SELECT %s FROM {self.table_name}'
            ' WHERE expire_time IS NOT NULL AND expire_time < ?'
            ' ORDER BY expire_time LIMIT ?'
        )

        select_expired = select_expired_template % 'filename'
        rows = sql(select_expired, (now, cull_limit)).fetchall()

        if rows:
            delete_expired = f'DELETE FROM {self.table_name} WHERE rowid IN (%s)' % (
                select_expired_template % 'rowid'
            )
            sql(delete_expired, (now, cull_limit))

            for (filename,) in rows: cleanup(filename)
            cull_limit -= len(rows)
            if cull_limit == 0: return

        # Evict keys by policy.

        select_policy: str = self.eviction_policy['cull']
        if select_policy is None or self.volume() < self.config.size_limit: return
        select_filename = select_policy.format(fields='filename', now=now)
        rows = sql(select_filename, (cull_limit,)).fetchall()

        if rows:
            delete = f'DELETE FROM {self.table_name} WHERE rowid IN (%s)' % (
                select_policy.format(fields='rowid', now=now)
            )
            sql(delete, (cull_limit,))

            for (filename,) in rows:
                cleanup(filename)
    

    def touch(self, key: KeyT, expire: float = None, retry: bool = False):
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
        db_key, raw = self.medium.put(key)
        expire_time = None if expire is None else now + expire

        with self._transact(retry) as (sql, _):
            rows = sql(
                f'SELECT rowid, expire_time FROM {self.table_name}'
                ' WHERE key = ? AND raw = ?',
                (db_key, raw),
            ).fetchall()

            if rows:
                ((rowid, old_expire_time),) = rows
                if old_expire_time is None or old_expire_time > now:
                    sql(
                        f'UPDATE {self.table_name} SET expire_time = ? WHERE rowid = ?',
                        (expire_time, rowid),
                    )
                    return True

        return False

    def add(self, key: KeyT, value: ValueT, expire: float = None, read: bool = False, tag: str = None, retry: bool = False):
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
        db_key, raw = self.medium.put(key)
        expire_time = None if expire is None else now + expire
        size, mode, filename, db_value = self.medium.store(value, read, key=key)
        columns = (expire_time, tag, size, mode, filename, db_value)

        with self._transact(retry, filename) as (sql, cleanup):
            rows = sql(
                f'SELECT rowid, filename, expire_time FROM {self.table_name} WHERE'
                ' WHERE key = ? AND raw = ?',
                (db_key, raw),
            ).fetchall()

            if rows:
                ((rowid, old_filename, old_expire_time),) = rows

                if old_expire_time is None or old_expire_time > now:
                    cleanup(filename)
                    return False

                cleanup(old_filename)
                self._row_update(rowid, now, columns)
            else:
                self._row_insert(db_key, raw, now, columns)

            self._cull(now, sql, cleanup)

            return True

    def incr(self, key: KeyT, delta: int = 1, default: int = 0, retry: bool = False):
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
        db_key, raw = self.medium.put(key)
        select = (
            f'SELECT rowid, expire_time, filename, value FROM {self.table_name}'
            ' WHERE key = ? AND raw = ?'
        )

        with self._transact(retry) as (sql, cleanup):
            rows = sql(select, (db_key, raw)).fetchall()

            if not rows:
                if default is None:
                    raise KeyError(key)

                value = default + delta
                columns = (None, None) + self.medium.store(
                    value, False, key = key
                )
                self._row_insert(db_key, raw, now, columns)
                self._cull(now, sql, cleanup)
                return value

            ((rowid, expire_time, filename, value),) = rows

            if expire_time is not None and expire_time < now:
                if default is None:
                    raise KeyError(key)

                value = default + delta
                columns = (None, None) + self.medium.store(
                    value, False, key=key
                )
                self._row_update(rowid, now, columns)
                self._cull(now, sql, cleanup)
                cleanup(filename)
                return value

            value += delta

            columns = 'store_time = ?, value = ?'
            update_column: str = self.eviction_policy['get']

            if update_column is not None:
                columns += f', {update_column.format(now=now)}'

            update = f'UPDATE {self.table_name} ' + f'SET {columns} WHERE rowid = ?'
            sql(update, (now, value, rowid))

            return value

    def decr(self, key: KeyT, delta: int = 1, default: int = 0, retry: bool = False):
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

    def get(
        self,
        key: KeyT,
        default: Any = None,
        read: bool = False,
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):    # sourcery skip: low-code-quality
        """Retrieve value from cache. If `key` is missing, return `default`.
        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).
        :param key: key for item
        :param default: value to return if key is missing (default None)
        :param bool read: if True, return file handle to value
            (default False)
        :param bool expire_time: if True, return expire_time in tuple
            (default False)
        :param bool tag: if True, return tag in tuple (default False)
        :param bool retry: retry if database timeout occurs (default False)
        :return: value for item or default if key not found
        :raises Timeout: if database timeout occurs
        """
        db_key, raw = self.medium.put(key)
        #update_column = EVICTION_POLICY[self.eviction_policy]['get']
        # update_column = self._sqlconf.policies[self.eviction_policy]['get']
        update_column: str = self.eviction_policy['get']
        select = (
            'SELECT rowid, expire_time, tag, mode, filename, value'
            f' FROM {self.table_name} WHERE key = ? AND raw = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )

        if expire_time and tag:
            default = (default, None, None)
        elif expire_time or tag:
            default = (default, None)

        if not self.config.statistics and update_column is None:
            # Fast path, no transaction necessary.

            rows = self._sql(select, (db_key, raw, time.time())).fetchall()

            if not rows:
                return default

            ((rowid, db_expire_time, db_tag, mode, filename, db_value),) = rows

            try:
                value = self.medium.fetch(mode, filename, db_value, read)
            except IOError:
                # Key was deleted before we could retrieve result.
                return default

        else:  # Slow path, transaction required.
            cache_hit = (
                f'UPDATE Settings_{self.table_name} SET value = value + 1 WHERE key = "hits"'
            )
            cache_miss = (
                f'UPDATE Settings_{self.table_name} SET value = value + 1 WHERE key = "misses"'
            )

            with self._transact(retry) as (sql, _):
                rows = sql(select, (db_key, raw, time.time())).fetchall()

                if not rows:
                    if self.config.statistics:
                        sql(cache_miss)
                    return default

                (
                    (rowid, db_expire_time, db_tag, mode, filename, db_value),
                ) = rows  # noqa: E127

                try:
                    value = self.medium.fetch(mode, filename, db_value, read)
                except IOError as error:
                    if error.errno != errno.ENOENT: raise

                    # Key was deleted before we could retrieve result.
                    if self.config.statistics: sql(cache_miss)
                    return default
                
                if self.config.statistics: sql(cache_hit)
                now = time.time()
                if update_column is not None:
                    update = f'UPDATE {self.table_name} SET %s WHERE rowid = ?'
                    sql(update % update_column.format(now=now), (rowid,))

        if expire_time and tag:
            return (value, db_expire_time, db_tag)
        elif expire_time:
            return (value, db_expire_time)
        elif tag:
            return (value, db_tag)
        return value


    def read(
        self, 
        key: KeyT, 
        retry: bool = False
    ):
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

    def __contains__(self, key: KeyT):
        """Return `True` if `key` matching item is found in cache.
        :param key: key matching item
        :return: True if key matching item
        """
        sql = self._sql
        db_key, raw = self.medium.put(key)
        select = (
            f'SELECT rowid FROM {self.table_name}'
            ' WHERE key = ? AND raw = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )

        rows = sql(select, (db_key, raw, time.time())).fetchall()
        return bool(rows)

    def pop(
        self, 
        key: KeyT, 
        default: Any = None, 
        expire_time: bool = False, 
        tag: bool = False, 
        retry: bool = False
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
        db_key, raw = self.medium.put(key)
        select = (
            'SELECT rowid, expire_time, tag, mode, filename, value'
            f' FROM {self.table_name} WHERE key = ? AND raw = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )

        if expire_time and tag:
            default = default, None, None
        elif expire_time or tag:
            default = default, None

        with self._transact(retry) as (sql, _):
            rows = sql(select, (db_key, raw, time.time())).fetchall()
            if not rows: return default
            ((rowid, db_expire_time, db_tag, mode, filename, db_value),) = rows
            sql(f'DELETE FROM {self.table_name} WHERE rowid = ?', (rowid,))

        try:
            value = self.medium.fetch(mode, filename, db_value, False)
        except IOError as error:
            if error.errno == errno.ENOENT:
                # Key was deleted before we could retrieve result.
                return default
            else:
                raise
        finally:
            if filename is not None: self.medium.remove(filename)

        if expire_time and tag:
            return value, db_expire_time, db_tag
        elif expire_time:
            return value, db_expire_time
        elif tag:
            return value, db_tag
        return value

    def __delitem__(self, key: KeyT, retry: bool = True):
        """Delete corresponding item for `key` from cache.
        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default `True`).
        :param key: key matching item
        :param bool retry: retry if database timeout occurs (default True)
        :raises KeyError: if key is not found
        :raises Timeout: if database timeout occurs
        """
        db_key, raw = self.medium.put(key)
        with self._transact(retry) as (sql, cleanup):
            rows = sql(
                f'SELECT rowid, filename FROM {self.table_name}'
                ' WHERE key = ? AND raw = ?'
                ' AND (expire_time IS NULL OR expire_time > ?)',
                (db_key, raw, time.time()),
            ).fetchall()

            if not rows: raise KeyError(key)
            ((rowid, filename),) = rows
            sql(f'DELETE FROM {self.table_name} WHERE rowid = ?', (rowid,))
            cleanup(filename)

            return True

    def delete(self, key: KeyT, retry: bool = False):
        """Delete corresponding item for `key` from cache.
        Missing keys are ignored.
        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).
        :param key: key matching item
        :param bool retry: retry if database timeout occurs (default False)
        :return: True if item was deleted
        :raises Timeout: if database timeout occurs
        """
        try:
            return self.__delitem__(key, retry=retry)
        except KeyError:
            return False

    def push(
        self,
        value: ValueT,
        prefix: str = None,
        side: str ='back',
        expire: float = None,
        read: bool = False,
        tag: str = None,
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
        See also `Store.pull`.
        >>> cache = Store()
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
        raw = True
        expire_time = None if expire is None else now + expire
        size, mode, filename, db_value = self._medium.store(value, read)
        columns = (expire_time, tag, size, mode, filename, db_value)
        order = {'back': 'DESC', 'front': 'ASC'}
        select = (
            f'SELECT key FROM {self.table_name}'
            ' WHERE ? < key AND key < ? AND raw = ?'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]

        with self._transact(retry, filename) as (sql, cleanup):
            rows = sql(select, (min_key, max_key, raw)).fetchall()

            if rows:
                ((key,),) = rows

                num = int(key[(key.rfind('-') + 1) :]) if prefix is not None else key
                if side == 'back':
                    num += 1
                else:
                    assert side == 'front'
                    num -= 1
            else:
                num = self.config.start_index_n

            db_key = '{0}-{1:015d}'.format(prefix, num) if prefix is not None else num
            self._row_insert(db_key, raw, now, columns)
            self._cull(now, sql, cleanup)

            return db_key

    def pull(
        self,
        prefix: str = None,
        default: Tuple[Any] = (None, None),
        side: str = 'front',
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):  # sourcery skip: low-code-quality
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
        See also `Store.push` and `Store.get`.
        >>> cache = Store()
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
        # Caution: Nearly identical code exists in Store.peek
        if prefix is None:
            min_key = 0
            max_key = 999999999999999
        else:
            min_key = f'{prefix}-000000000000000'
            max_key = f'{prefix}-999999999999999'

        order = {'front': 'ASC', 'back': 'DESC'}
        select = (
            'SELECT rowid, key, expire_time, tag, mode, filename, value'
            f' FROM {self.table_name} WHERE ? < key AND key < ? AND raw = 1'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]

        if expire_time and tag:
            default = default, None, None
        elif expire_time or tag:
            default = default, None

        while True:
            while True:
                with self._transact(retry) as (sql, cleanup):
                    rows = sql(select, (min_key, max_key)).fetchall()
                    if not rows: return default

                    (
                        (rowid, key, db_expire, db_tag, mode, name, db_value),
                    ) = rows

                    sql(f'DELETE FROM {self.table_name} WHERE rowid = ?', (rowid,))
                    if db_expire is not None and db_expire < time.time(): cleanup(name)
                    else: break

            try:
                value = self._medium.fetch(mode, name, db_value, False)
            except IOError as error:
                if error.errno == errno.ENOENT:
                    # Key was deleted before we could retrieve result.
                    continue
                raise
            finally:
                if name is not None: self._medium.remove(name)
            break

        if expire_time and tag:
            return (key, value), db_expire, db_tag
        elif expire_time:
            return (key, value), db_expire
        elif tag:
            return (key, value), db_tag
        return key, value

    def peek(
        self,
        prefix: str = None,
        default: Tuple[Any] = (None, None),
        side: str = 'front',
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):    # sourcery skip: low-code-quality
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
        See also `Store.pull` and `Store.push`.
        >>> cache = Store()
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
        # Caution: Nearly identical code exists in Store.pull
        if prefix is None:
            min_key = 0
            max_key = 999999999999999
        else:
            min_key = f'{prefix}-000000000000000'
            max_key = f'{prefix}-999999999999999'

        order = {'front': 'ASC', 'back': 'DESC'}
        select = (
            'SELECT rowid, key, expire_time, tag, mode, filename, value'
            f' FROM {self.table_name} WHERE ? < key AND key < ? AND raw = 1'
            ' ORDER BY key %s LIMIT 1'
        ) % order[side]

        if expire_time and tag:
            default = default, None, None
        elif expire_time or tag:
            default = default, None

        while True:
            while True:
                with self._transact(retry) as (sql, cleanup):
                    rows = sql(select, (min_key, max_key)).fetchall()

                    if not rows:
                        return default

                    (
                        (rowid, key, db_expire, db_tag, mode, name, db_value),
                    ) = rows

                    if db_expire is None or db_expire >= time.time():
                        break

                    sql(f'DELETE FROM {self.table_name} WHERE rowid = ?', (rowid,))
                    cleanup(name)
            try:
                value = self._medium.fetch(mode, name, db_value, False)
            except IOError as error:
                if error.errno == errno.ENOENT:
                    # Key was deleted before we could retrieve result.
                    continue
                raise
            finally:
                if name is not None: self._medium.remove(name)
            break

        if expire_time and tag:
            return (key, value), db_expire, db_tag
        elif expire_time:
            return (key, value), db_expire
        elif tag:
            return (key, value), db_tag
        return key, value

    def peekitem(
        self, 
        last: bool = True, 
        expire_time: bool = False, 
        tag: bool = False, 
        retry: bool = False
    ):
        """Peek at key and value item pair in cache based on iteration order.
        Expired items are deleted from cache. Operation is atomic. Concurrent
        operations will be serialized.
        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).
        >>> cache = Store()
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
            'SELECT rowid, key, raw, expire_time, tag, mode, filename, value'
            f' FROM {self.table_name} ORDER BY'
            ' rowid %s LIMIT 1'
        ) % order[last]

        while True:
            while True:
                with self._transact(retry) as (sql, cleanup):
                    rows = sql(select).fetchall()

                    if not rows:
                        raise KeyError('dictionary is empty')

                    (
                        (
                            rowid,
                            db_key,
                            raw,
                            db_expire,
                            db_tag,
                            mode,
                            name,
                            db_value,
                        ),
                    ) = rows

                    if db_expire is not None and db_expire < time.time():
                        sql(f'DELETE FROM {self.table_name} WHERE rowid = ?', (rowid,))
                        cleanup(name)
                    else: break

            key = self._medium.get(db_key, raw)

            try:
                value = self._medium.fetch(mode, name, db_value, False)
            except IOError as error:
                if error.errno == errno.ENOENT:
                    # Key was deleted before we could retrieve result.
                    continue
                raise
            break

        if expire_time and tag:
            return (key, value), db_expire, db_tag
        elif expire_time:
            return (key, value), db_expire
        elif tag:
            return (key, value), db_tag
        return key, value

    def __getitem__(self, key):
        """Return corresponding value for `key` from cache.
        :param key: key matching item
        :return: corresponding value
        :raises KeyError: if key is not found
        """
        value = self.get(key, default=ENOVAL, retry=True)
        if value is ENOVAL:
            raise KeyError(key)
        return value

    def close(self):
        """Close database connection."""
        con: sqlite3.Connection = getattr(self._local, 'con', None)
        if con is None: return
        con.close()
        with cl.suppress(AttributeError):
            delattr(self._local, 'con')

    def __enter__(self):
        # Create connection in thread.
        # pylint: disable=unused-variable
        connection = self._con  # noqa
        return self

    def __exit__(self, *exception):
        self.close()

    def __len__(self):
        "Count of items in cache including expired items."
        return self.reset('count')

    def __getstate__(self):
        return (self.connection_path, self.timeout, type(self.medium))

    def __setstate__(self, state):
        self.__init__(*state)

    def reset(
        self, 
        key: KeyT, 
        value: ValueT = ENOVAL, 
        update: bool = True
    ):
        """Reset `key` and `value` item from Settings table.
        Use `reset` to update the value of Store settings correctly. Store
        settings are stored in the Settings table of the SQLite database. If
        `update` is ``False`` then no attempt is made to update the database.
        If `value` is not given, it is reloaded from the Settings
        table. Otherwise, the Settings table is updated.
        Settings with the ``disk_`` prefix correspond to Disk
        attributes. Updating the value will change the unprefixed attribute on
        the associated Disk instance.
        Settings with the ``sqlite_`` prefix correspond to SQLite
        pragmas. Updating the value will execute the corresponding PRAGMA
        statement.
        SQLite PRAGMA statements may be executed before the Settings table
        exists in the database by setting `update` to ``False``.
        :param str key: Settings key for item
        :param value: value for item (optional)
        :param bool update: update database Settings table (default True)
        :return: updated value for item
        :raises Timeout: if database timeout occurs
        """
        sql = self._sql
        sql_retry = self._sql_retry

        if value is ENOVAL:
            select = f'SELECT value FROM Settings_{self.table_name} WHERE key = ?'
            ((value,),) = sql_retry(select, (key,)).fetchall()
            setattr(self, key, value)
            return value

        if update:
            statement = f'UPDATE Settings_{self.table_name} SET value = ? WHERE key = ?'
            sql_retry(statement, (value, key))

        if key.startswith('sqlite_'):
            pragma = key[7:]

            # 2016-02-17 GrantJ - PRAGMA and isolation_level=None
            # don't always play nicely together. Retry setting the
            # PRAGMA. I think some PRAGMA statements expect to
            # immediately take an EXCLUSIVE lock on the database. I
            # can't find any documentation for this but without the
            # retry, stress will intermittently fail with multiple
            # processes.

            # 2018-11-05 GrantJ - Avoid setting pragma values that
            # are already set. Pragma settings like auto_vacuum and
            # journal_mode can take a long time or may not work after
            # tables have been created.

            start = time.time()
            while True:
                try:
                    try:
                        ((old_value,),) = sql(f'PRAGMA {pragma}').fetchall()
                        update = old_value != value
                    except ValueError:
                        update = True
                    if update:
                        sql(f'PRAGMA {pragma} = {value}').fetchall()
                    break
                except sqlite3.OperationalError as exc:
                    if str(exc) != 'database is locked': raise
                    diff = time.time() - start
                    if diff > 60: raise
                    time.sleep(0.001)
        elif key.startswith('disk_'):
            attr = key[5:]
            setattr(self._medium, attr, value)

        setattr(self, key, value)
        return value
    

    def check(
        self, 
        fix: bool = False, 
        retry: bool = False
    ):
        """Check database and file system consistency.
        Intended for use in testing and post-mortem error analysis.
        While checking the Store table for consistency, a writer lock is held
        on the database. The lock blocks other cache clients from writing to
        the database. For caches with many file references, the lock may be
        held for a long time. For example, local benchmarking shows that a
        cache with 1,000 file references takes ~60ms to check.
        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).
        :param bool fix: correct inconsistencies
        :param bool retry: retry if database timeout occurs (default False)
        :return: list of warnings
        :raises Timeout: if database timeout occurs
        """
        # pylint: disable=access-member-before-definition,W0201
        with warnings.catch_warnings(record=True) as warns:
            sql = self._sql

            # Check integrity of database.
            rows = sql('PRAGMA integrity_check').fetchall()
            if len(rows) != 1 or rows[0][0] != u'ok':
                for (message,) in rows:
                    warnings.warn(message)

            if fix: sql('VACUUM')
            with self._transact(retry) as (sql, _):

                # Check Store.filename against file system.
                filenames = set()
                select = (
                    f'SELECT rowid, size, filename FROM {self.table_name}'
                    ' WHERE filename IS NOT NULL'
                )

                rows = sql(select).fetchall()
                for rowid, size, filename in rows:
                    full_path = self.connection_path.joinpath(filename)
                    # full_path = op.join(self._directory, filename)
                    filenames.add(full_path)
                    if full_path.exists():
                        real_size = full_path.info()['size']
                        # real_size = op.getsize(full_path)

                        if size != real_size:
                            message = 'wrong file size: %s, %d != %d'
                            args = full_path, real_size, size
                            warnings.warn(message % args)

                            if fix:
                                sql(
                                    f'UPDATE {self.table_name} SET size = ?'
                                    ' WHERE rowid = ?',
                                    (real_size, rowid),
                                )

                        continue

                    warnings.warn(f'file not found: {full_path}')

                    if fix:
                        sql(f'DELETE FROM {self.table_name} WHERE rowid = ?', (rowid,))

                # Check file system against Store.filename.
                # for filename in self.connection_path.iterdir()
                for dirpath, _, files in os.walk(self.connection_path):
                    paths = [os.path.join(dirpath, filename) for filename in files]
                    error = set(paths) - filenames

                    for full_path in error:
                        if self.filename in full_path:
                            continue

                        message = f'unknown file: {full_path}'
                        warnings.warn(message, UnknownFileWarning)

                        if fix:
                            os.remove(full_path)

                # Check for empty directories.
                for dirpath, dirs, files in os.walk(self.connection_path):
                    if not (dirs or files):
                        message = f'empty directory: {dirpath}'
                        warnings.warn(message, EmptyDirWarning)
                        if fix: os.rmdir(dirpath)

                # Check Settings.count against count of Store rows.

                self.reset('count')
                ((count,),) = sql(f'SELECT COUNT(key) FROM {self.table_name}').fetchall()

                if self.count != count:
                    message = f'Settings_{self.table_name}.count != COUNT({self.table_name}.key); %d != %d'
                    warnings.warn(message % (self.count, count))

                    if fix:
                        sql(
                            f'UPDATE Settings_{self.table_name} SET value = ? WHERE key = ?',
                            (count, 'count'),
                        )

                # Check Settings.size against sum of Store.size column.

                self.reset('size')
                select_size = f'SELECT COALESCE(SUM(size), 0) FROM {self.table_name}'
                ((size,),) = sql(select_size).fetchall()

                if self.size != size:
                    message = f'Settings_{self.table_name}.size != SUM({self.table_name}.size); %d != %d'
                    warnings.warn(message % (self.size, size))

                    if fix:
                        sql(
                            f'UPDATE Settings_{self.table_name} SET value = ? WHERE key =?',
                            (size, 'size'),
                        )

            return warns

    def create_tag_index(self):
        """Create tag index on cache database.
        It is better to initialize cache with `tag_index=True` than use this.
        :raises Timeout: if database timeout occurs
        """
        sql = self._sql
        sql(f'CREATE INDEX IF NOT EXISTS {self.table_name}_tag_rowid ON {self.table_name}(tag, rowid)')
        self.reset('tag_index', 1)

    def drop_tag_index(self):
        """Drop tag index on cache database.
        :raises Timeout: if database timeout occurs
        """
        sql = self._sql
        sql(f'DROP INDEX IF EXISTS {self.table_name}_tag_rowid')
        self.reset('tag_index', 0)

    def evict(
        self, 
        tag: str, 
        retry: bool = False
    ):
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
            f'SELECT rowid, filename FROM {self.table_name}'
            ' WHERE tag = ? AND rowid > ?'
            ' ORDER BY rowid LIMIT ?'
        )
        args = [tag, 0, 100]
        return self._select_delete(select, args, arg_index=1, retry=retry)

    def expire(
        self, 
        now: float = None, 
        retry: bool = False
    ):
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
            f'SELECT rowid, expire_time, filename FROM {self.table_name}'
            ' WHERE ? < expire_time AND expire_time < ?'
            ' ORDER BY expire_time LIMIT ?'
        )
        args = [0, now or time.time(), 100]
        return self._select_delete(select, args, row_index=1, retry=retry)

    def cull(
        self, 
        retry: bool = False
    ):
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

        #select_policy = EVICTION_POLICY[self.eviction_policy]['cull']
        # select_policy = self._sqlconf.policies[self.eviction_policy]['cull']
        select_policy: str = self.eviction_policy['cull']

        if select_policy is None:
            return 0

        select_filename = select_policy.format(fields='filename', now=now)
        try:
            while self.volume() > self.config.size_limit:
                with self._transact(retry) as (sql, cleanup):
                    rows = sql(select_filename, (10,)).fetchall()

                    if not rows:
                        break

                    count += len(rows)
                    delete = (
                        f'DELETE FROM {self.table_name} WHERE rowid IN ({select_policy.format(fields="rowid", now=now)})'
                    )
                    #delete = (
                    #    'DELETE FROM Store WHERE rowid IN (%s)'
                    #    % select_policy.format(fields='rowid', now=now)
                    #)
                    sql(delete, (10,))

                    for (filename,) in rows:
                        cleanup(filename)
        except SqlTimeout:
            raise SqlTimeout(count) from None

        return count

    def clear(
        self, 
        retry: bool = False
    ):
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
            f'SELECT rowid, filename FROM {self.table_name}'
            ' WHERE rowid > ?'
            ' ORDER BY rowid LIMIT ?'
        )
        args = [0, 100]
        return self._select_delete(select, args, retry=retry)

    def _select_delete(
        self, 
        select, 
        args, 
        row_index: int = 0, 
        arg_index: int = 0, 
        retry: bool = False
    ):
        count = 0
        delete = f'DELETE FROM {self.table_name} WHERE rowid IN (%s)'

        try:
            while True:
                with self._transact(retry) as (sql, cleanup):
                    rows = sql(select, args).fetchall()

                    if not rows:
                        break

                    count += len(rows)
                    sql(delete % ','.join(str(row[0]) for row in rows))

                    for row in rows:
                        args[arg_index] = row[row_index]
                        cleanup(row[-1])

        except SqlTimeout:
            raise SqlTimeout(count) from None

        return count

    def iterkeys(self, reverse=False):
        """Iterate Store keys in database sort order.
        >>> cache = Store()
        >>> for key in [4, 1, 3, 0, 2]:
        ...     cache[key] = key
        >>> list(cache.iterkeys())
        [0, 1, 2, 3, 4]
        >>> list(cache.iterkeys(reverse=True))
        [4, 3, 2, 1, 0]
        :param bool reverse: reverse sort order (default False)
        :return: iterator of Store keys
        """
        sql = self._sql
        limit = 100
        _disk_get = self._medium.get

        if reverse:
            select = (
                f'SELECT key, raw FROM {self.table_name}'
                ' ORDER BY key DESC, raw DESC LIMIT 1'
            )
            iterate = (
                f'SELECT key, raw FROM {self.table_name}'
                ' WHERE key = ? AND raw < ? OR key < ?'
                ' ORDER BY key DESC, raw DESC LIMIT ?'
            )
        else:
            select = (
                f'SELECT key, raw FROM {self.table_name}'
                ' ORDER BY key ASC, raw ASC LIMIT 1'
            )
            iterate = (
                f'SELECT key, raw FROM {self.table_name}'
                ' WHERE key = ? AND raw > ? OR key > ?'
                ' ORDER BY key ASC, raw ASC LIMIT ?'
            )

        row = sql(select).fetchall()

        if row: ((key, raw),) = row
        else: return

        yield _disk_get(key, raw)
        while True:
            rows = sql(iterate, (key, raw, key, limit)).fetchall()
            if not rows: break

            for key, raw in rows:
                yield _disk_get(key, raw)

    def _iter(self, ascending=True):
        sql = self._sql
        rows = sql(f'SELECT MAX(rowid) FROM {self.table_name}').fetchall()
        ((max_rowid,),) = rows
        yield  # Signal ready.

        if max_rowid is None: return
        bound = max_rowid + 1
        limit = 100
        _disk_get = self._medium.get
        rowid = 0 if ascending else bound
        select = (
            f'SELECT rowid, key, raw FROM {self.table_name}'
            ' WHERE ? < rowid AND rowid < ?'
            ' ORDER BY rowid %s LIMIT ?'
        ) % ('ASC' if ascending else 'DESC')

        while True:
            args = (rowid, bound, limit) if ascending else (0, rowid, limit)
            rows = sql(select, args).fetchall()

            if not rows:
                break

            for rowid, key, raw in rows:
                yield _disk_get(key, raw)

    def __iter__(self):
        "Iterate keys in cache including expired items."
        iterator = self._iter()
        next(iterator)
        return iterator

    def __reversed__(self):
        "Reverse iterate keys in cache including expired items."
        iterator = self._iter(ascending=False)
        next(iterator)
        return iterator

    def stats(self, enable=True, reset=False):
        """Return cache statistics hits and misses.
        :param bool enable: enable collecting statistics (default True)
        :param bool reset: reset hits and misses to 0 (default False)
        :return: (hits, misses)
        """
        # pylint: disable=E0203,W0201
        result = (self.reset('hits'), self.reset('misses'))

        if reset:
            self.reset('hits', 0)
            self.reset('misses', 0)

        self.reset('statistics', enable)
        return result
    

    def cachify(
        self, 
        name: Optional[str] = None, 
        typed: Optional[bool] = False, 
        expire: Optional[int] = None, 
        tag: Optional[str] = None
    ):
        """Memoizing cache decorator.
        Decorator to wrap callable with memoizing function using cache.
        Repeated calls with the same arguments will lookup result in cache and
        avoid function evaluation.
        If name is set to None (default), the callable name will be determined
        automatically.
        When expire is set to zero, function results will not be set in the
        cache. Store lookups still occur, however. Read
        :doc:`case-study-landing-page-caching` for example usage.
        If typed is set to True, function arguments of different types will be
        cached separately. For example, f(3) and f(3.0) will be treated as
        distinct calls with distinct results.
        The original underlying function is accessible through the __wrapped__
        attribute. This is useful for introspection, for bypassing the cache,
        or for rewrapping the function with a different cache.
        >>> from diskcache import Store
        >>> cache = Store()
        >>> @cache.cachify(expire=1, tag='fib')
        ... def fibonacci(number):
        ...     if number == 0:
        ...         return 0
        ...     elif number == 1:
        ...         return 1
        ...     else:
        ...         return fibonacci(number - 1) + fibonacci(number - 2)
        >>> print(fibonacci(100))
        354224848179261915075
        An additional `__cache_key__` attribute can be used to generate the
        cache key used for the given arguments.
        >>> key = fibonacci.__cache_key__(100)
        >>> print(cache[key])
        354224848179261915075
        Remember to call memoize when decorating a callable. If you forget,
        then a TypeError will occur. Note the lack of parenthenses after
        memoize below:
        >>> @cache.memoize
        ... def test():
        ...     pass
        Traceback (most recent call last):
            ...
        TypeError: name cannot be callable
        :param cache: cache to store callable arguments and return values
        :param str name: name given for callable (default None, automatic)
        :param bool typed: cache different types separately (default False)
        :param float expire: seconds until arguments expire
            (default None, no expiry)
        :param str tag: text to associate with arguments (default None)
        :return: callable decorator
        """
        # Caution: Nearly identical code exists in DjangoStore.memoize
        if callable(name):
            raise TypeError('name cannot be callable')

        def decorator(func):
            "Decorator created by memoize() for callable `func`."
            base = (full_name(func),) if name is None else (name,)
            if not inspect.iscoroutinefunction(func):
                @ft.wraps(func)
                def wrapper(*args, **kwargs):
                    "Wrapper for callable to cache arguments and return values."
                    key = wrapper.__cache_key__(*args, **kwargs)
                    result = self.get(key, default=ENOVAL, retry=True)

                    if result is ENOVAL:
                        result = func(*args, **kwargs)
                        if expire is None or expire > 0:
                            self.set(key, result, expire, tag=tag, retry=True)

                    return result
            else:
                @ft.wraps(func)
                async def wrapper(*args, **kwargs):
                    "Wrapper for callable to cache arguments and return values."
                    key = wrapper.__cache_key__(*args, **kwargs)
                    result = self.get(key, default=ENOVAL, retry=True)

                    if result is ENOVAL:
                        result = await func(*args, **kwargs)
                        if expire is None or expire > 0:
                            self.set(key, result, expire, tag=tag, retry=True)

                    return result

            def __cache_key__(*args, **kwargs):
                "Make key for cache given function arguments."
                return args_to_key(base, args, kwargs, typed)

            wrapper.__cache_key__ = __cache_key__
            return wrapper

        return decorator