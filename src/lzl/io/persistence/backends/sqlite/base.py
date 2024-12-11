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
import atexit
from lzl import load
from lzl.pool import ThreadPool
from lzo.types import eproperty
from pydantic.networks import UrlConstraints, Annotated
from pydantic.networks import UrlConstraints, Annotated
try:
    from pydantic_core import MultiHostUrl
except ImportError:
    from pydantic.networks import MultiHostUrl

from pydantic.alias_generators import to_camel
from ..base import logger
from .utils import dict_diff
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Tuple, Iterable, List, Type, Callable, Generator, AsyncGenerator, TYPE_CHECKING

try:
    import dill as pickle
except ImportError:
    import pickle

if load.TYPE_CHECKING:
    import sqlite3
    import aiosqlite

    from sqlite3 import Connection, Cursor
    from aiosqlite import Connection as AsyncConnection, Cursor as AsyncCursor
else:
    sqlite3 = load.LazyLoad("sqlite3")
    aiosqlite = load.LazyLoad("aiosqlite")

class Constant(tuple):
    """Pretty display of immutable constant."""

    def __new__(cls, name):
        return tuple.__new__(cls, (name,))

    def __repr__(self):
        return f'{self[0]}'


ENOVAL = Constant('ENOVAL')
UNKNOWN = Constant('UNKNOWN')

class Timeout(Exception):
    """Database timeout expired."""

SqliteDsn = Annotated[
    MultiHostUrl,
    UrlConstraints(
        host_required=True,
        allowed_schemes=[
            'sqlite',
            'sqlite+aiosqlite',
            'sqlite+asyncio',
            'sqlite+aiosqlite3',
            'sqlite+pysqlite3',

            # Support rqlite
        ],
    ),
]


DEFAULT_SETTINGS = {
    'statistics': 1,  # True
    'tag_index': 1,  # True
    'eviction_policy': 'least-recently-stored',
    'size_limit': 2**30,  # 1gb
    'cull_limit': 10,
    'sqlite_auto_vacuum': 1,  # FULL
    'sqlite_cache_size': 2**13,  # 8,192 pages
    'sqlite_journal_mode': 'wal',
    'sqlite_mmap_size': 2**26,  # 64mb
    'sqlite_synchronous': 1,  # NORMAL
}

OPTIMIZED = {
    'standard': {
        'statistics': 0,
        'tag_index': 0,
    },
    'balanced': {
        'sqlite_mmap_size': 1024 * 128,  # 128mb
    },
    'cache': {
        'eviction_policy': 'least-frequently-used',
        'sqlite_mmap_size': 1024 * 512,  # 512mb
        'size_limit': 1024 * 1024 * 1024 * 5,  # 5gb
    },
    'write': {
        'sqlite_mmap_size': 1024 * 256,  # 256mb
        'size_limit': 1024 * 1024 * 1024 * 2,  # 2gb
    },
    'read': {
        'sqlite_mmap_size': 1024 * 128,  # 128mb
        'size_limit': 1024 * 1024 * 1024 * 1,  # 1gb
    },
}

METADATA = {
    'count': 0,
    'size': 0,
    'hits': 0,
    'misses': 0,
}

Optimization = t.Literal[
    'standard', 
    'balanced', 
    'cache',
    'write',
    'read',
]

def get_optimized_settings(
    optimization: Optional[str] = None, 
    **kwargs
) -> Dict[str, Any]:
    """
    Returns the Optimized Settings
    """
    base = copy.deepcopy(DEFAULT_SETTINGS)
    if optimization:
        base.update(OPTIMIZED.get(optimization, {}))
    if kwargs: base.update(kwargs)
    return base

def get_eviction_policies(table_name: str) -> Dict[str, t.Optional[str]]:
    """
    Returns the Eviction Policies
    """

    return {
        'none': {
            'init': None,
            'get': 'hit_count = hit_count + 1',
            'cull': None,
        },
        'least-recently-stored': {
            'init': (
                f'CREATE INDEX IF NOT EXISTS "{table_name}_store_time" ON'
                f' "{table_name}" (store_time)'
            ),
            # 'get': None,
            'get': 'hit_count = hit_count + 1',
            'cull': 'SELECT {fields} FROM "' + table_name + '" ORDER BY store_time LIMIT ?',
        },
        'least-recently-used': {
            'init': (
                f'CREATE INDEX IF NOT EXISTS "{table_name}_access_time" ON'
                f' "{table_name}" (access_time)'
            ),
            'get': 'access_time = {now}, hit_count = hit_count + 1',
            'cull': 'SELECT {fields} FROM "' + table_name + '" ORDER BY access_time LIMIT ?',
        },
        'least-frequently-used': {
            'init': (
                f'CREATE INDEX IF NOT EXISTS "{table_name}_access_count" ON'
                f' "{table_name}" (access_count)'
            ),
            'get': 'access_count = access_count + 1, hit_count = hit_count + 1',
            'cull': 'SELECT {fields} FROM "' + table_name + '" ORDER BY access_count LIMIT ?',
        },
    }

def format_table_name(table_name: str) -> str:
    """
    Formats the table name

    >>> format_table_name('my.test.table_name') 
    'my_test_tableName'
    """
    parts = table_name.split('.')
    parts = [to_camel(part) for part in parts]
    return '_'.join(parts)


class BaseSqliteDB(abc.ABC):
    """
    The Sqlite Database
    """
    timeout: Optional[float] = 60.0
    _db_kind: Optional[str] = 'SQLite'

    def __init__(
        self, 
        conn_uri: str, 
        table: str, 
        optimization: Optional[Optimization] = None, 
        timeout: Optional[float] = None,
        is_remote: Optional[bool] = False,
        **kwargs
    ):
        """
        Initializes the Sqlite Database
        """
        self._extra: t.Dict[str, t.Any] = {}
        self.conn_uri = conn_uri
        self.table = format_table_name(table)
        self.optimization = optimization
        self._io: t.Optional['Connection'] = None
        self._aio: t.Optional['AsyncConnection'] = None
        # self.configured: bool = kwargs.pop('configured', False)
        self.is_child_db = kwargs.pop('is_child_db', False)
        self._debug_enabled = kwargs.pop('debug_enabled', False)
        self.configured: bool = False
        self.is_remote = is_remote
        self._config = kwargs
        self._txn_id = None
        self._is_configuring: bool = False
        if timeout is not None: self.timeout = timeout
        self._policies = get_eviction_policies(table_name = self.table)
        self._child_kwargs = {
            'conn_uri': self.conn_uri,
            'optimization': self.optimization,
            'is_remote': self.is_remote,
            'timeout': self.timeout,
            'kwargs': self._config,
        }
        self._spawned: t.Dict[str, t.List[t.Union['Connection', 'AsyncConnection']]] = {
            'io': [],
            'aio': [],
        }
        self.pool = ThreadPool
        self._register_exit_()

    
    
    """
    The Sqlite Database Connection
    """

    def _get_io_(self, timeout: t.Optional[float] = None) -> 'Connection':
        """
        Returns the IO Connection
        """
        new = sqlite3.connect(
            self.conn_uri, 
            uri = self.is_remote, 
            timeout = timeout or (self.timeout if self.configured else 0.0),
            check_same_thread = False,
            isolation_level = None,
        )
        self._spawned['io'].append(new)
        return new

    async def _get_aio_(self, timeout: Optional[float] = None) -> 'aiosqlite.Connection':
        """
        [Async] Returns the IO Connection
        """
        new = await aiosqlite.connect(
            self.conn_uri,
            uri = self.is_remote,
            timeout = timeout or (self.timeout if self.configured else 0.0),
            check_same_thread = False,
            isolation_level = None,
        )
        self._spawned['aio'].append(new)
        return new
    

    def _init_io_(self) -> None:
        """
        Initializes the IO Connection
        """
        if self._io is not None: return
        self._io = self._get_io_()
        if self._debug_enabled: logger.info(f'[Sync] Opened {self._db_kind} Database Connection: {self.conn_uri}', prefix = self.table, colored = True)
        self._validate_table_(self._io)
        if not self.is_configured:
            self._is_configuring = True
            self.run_configure()
            self._io = self._get_io_()
            self._is_configuring = False

    async def _init_aio_(self) -> None:
        """
        [Async] Initializes the IO Connection
        """
        if self._aio is not None: return
        self._aio = await self._get_aio_()
        if self._debug_enabled: logger.info(f'[Async] Opened {self._db_kind} Database Connection: {self.conn_uri}', prefix = self.table, colored = True)
        await self._avalidate_table_()
        if not self.is_configured:
            self._is_configuring = True
            await self.arun_configure()
            self._aio = await self._get_aio_()
            self._is_configuring = False
            

    @property
    def io(self) -> 'Connection':
        """
        Returns the IO Connection
        """
        if self._io is None: self._init_io_()
        return self._io


    @property
    def aio(self) -> 'AsyncConnection':
        """
        [Async] Returns the IO Connection
        """
        if self._aio is None: raise ValueError('Async Connection must be configured first')
        return self._aio

    """
    IO Wrappers 
    """

    @property
    def _sql_debug(self) -> t.Callable[..., 'Cursor']:
        """
        Returns the SQL
        """
        def _execute(statement, *args, **kwargs):
            logger.info(f'SQL: {statement}: {args} {kwargs}')
            return self._io.execute(statement, *args, **kwargs)
        return _execute

    @property
    def _asql_debug(self) -> t.Callable[..., t.Awaitable['AsyncCursor']]:
        """
        [Async] Returns the SQL
        """
        async def _aexecute(statement, *args, **kwargs):
            logger.info(f'SQL: {statement}: {args} {kwargs}')
            return await self._aio.execute(statement, *args, **kwargs)
        return _aexecute
    

    @property
    def _sqlmany_debug(self) -> t.Callable[..., 'Cursor']:
        """
        Returns the SQL
        """
        def _executemany(statement, *args, **kwargs):
            logger.info(f'SQL: {statement}: {args} {kwargs}')
            return self._io.executemany(statement, *args, **kwargs)
        return _executemany

    @property
    def _asqlmany_debug(self) -> t.Callable[..., t.Awaitable['AsyncCursor']]:
        """
        [Async] Returns the SQL
        """
        async def _aexecutemany(statement, *args, **kwargs):
            logger.info(f'[Async] SQL: {statement}: {args} {kwargs}')
            return await self._aio.executemany(statement, *args, **kwargs)
        return _aexecutemany

    @property
    def _sql(self) -> t.Callable[..., 'Cursor']:
        """
        Returns the SQL
        """
        if not self._io and not self._is_configuring: self._init_io_()
        return self._sql_debug if self._debug_enabled else self._io.execute

    @property
    def _asql(self) -> t.Callable[..., t.Awaitable['AsyncCursor']]:
        """
        [Async] Returns the SQL
        """
        if self._aio or self._is_configuring:
            return self._asql_debug if self._debug_enabled else self._aio.execute
        else: raise RuntimeError('Async Connection must be configured first')

    
    @property
    def _sqlmany(self) -> t.Callable[..., 'Cursor']:
        """
        Returns the SQL
        """
        return self._sqlmany_debug if self._debug_enabled else self._io.executemany

    @property
    def _asqlmany(self) -> t.Callable[..., t.Awaitable['AsyncCursor']]:
        """
        [Async] Returns the SQL
        """
        return self._asqlmany_debug if self._debug_enabled else self._aio.executemany
    
    @property
    def _sql_retry(self) -> t.Callable[..., 'Cursor']:
        """
        Returns the SQL Retry
        """
        sql = self._sql
        def _execute_with_retry(statement, *args, **kwargs):
            start = time.time()
            while True:
                try:
                    return sql(statement, *args, **kwargs)
                except sqlite3.OperationalError as exc:
                    logger.info(f'{self._db_kind} Error: {exc}: {statement}')
                    if str(exc) != 'database is locked': raise
                    diff = time.time() - start
                    if diff > 60: raise
                    time.sleep(0.001)
        return _execute_with_retry

    
    @property
    def _asql_retry(self) -> t.Callable[..., t.Awaitable['AsyncCursor']]:
        """
        [Async] Returns the SQL Retry
        """
        sql = self._asql
        async def _aexecute_with_retry(statement, *args, **kwargs):
            start = time.time()
            while True:
                try:
                    return await sql(statement, *args, **kwargs)
                except aiosqlite.OperationalError as exc:
                    if str(exc) != 'database is locked': raise
                    diff = time.time() - start
                    if diff > 60: raise
                    await asyncio.sleep(0.001)
        return _aexecute_with_retry

    @property
    def _sqlmany_retry(self) -> t.Callable[..., 'Cursor']:
        """
        Returns the SQL Retry
        """
        sql = self._sqlmany
        def _executemany_with_retry(statement, *args, **kwargs):
            start = time.time()
            while True:
                try:
                    return sql(statement, *args, **kwargs)
                except sqlite3.OperationalError as exc:
                    logger.info(f'SQLite Error: {exc}: {statement}')
                    if str(exc) != 'database is locked': raise
                    diff = time.time() - start
                    if diff > 60: raise
                    time.sleep(0.001)
        return _executemany_with_retry

    
    @property
    def _asqlmany_retry(self) -> t.Callable[..., t.Awaitable['AsyncCursor']]:
        """
        [Async] Returns the SQL Retry
        """
        sql = self._asqlmany
        async def _aexecutemany_with_retry(statement, *args, **kwargs):
            start = time.time()
            while True:
                try:
                    return await sql(statement, *args, **kwargs)
                except aiosqlite.OperationalError as exc:
                    if str(exc) != 'database is locked': raise
                    diff = time.time() - start
                    if diff > 60: raise
                    await asyncio.sleep(0.001)
        return _aexecutemany_with_retry

    @property
    def _sql_io_(self) -> t.Dict[str, bool]:
        """
        Shows the current IO Connection
        """
        return {
            'aio': self._aio is not None,
            'io': self._io is not None,
        }
    
    def close(self):
        """
        Closes the IO Connection
        """
        if self._io is not None:
            self._io.close()
            self._io = None
    
    async def aclose(self):
        """
        Closes the IO Connection
        """
        if self._aio is not None:
            await self._aio.close()
            self._aio = None
        self.close()
    
    
    """
    Exit Methods
    """
    
    def _register_exit_(self):
        """
        Registers the exit functions
        """
        from lzo.utils.aexit import register
        with contextlib.suppress(Exception):
            register(self._aon_exit_)
        atexit.register(self._on_exit_)
    
    def _on_exit_(self):
        """
        Closes the DBs on Exit
        """
        self.close()
        self._close_conns()
    
    async def _aon_exit_(self):
        """
        Closes the DBs on Exit
        """
        await self.aclose()
        await self._aclose_conns()

    def _close_conns(self):
        """
        Close all connections
        """
        if not self._spawned['io']: return
        while self._spawned['io']:
            conn = self._spawned['io'].pop()
            with contextlib.suppress(Exception):
                conn.close()
    
    async def _aclose_conns(self):
        """
        Close all connections
        """
        if not self._spawned['aio']: return
        while self._spawned['aio']:
            conn = self._spawned['aio'].pop()
            if not conn._running: continue
            await conn.close()

    
    """
    Configuration Steps
    """

    def _check_table_configured_(self, conn: t.Optional['Connection'] = None) -> bool:
        # sourcery skip: extract-method
        """
        Checks whether the DB has configured tables
        """
        conn = conn or self._get_io_()
        try:
            result = conn.execute(f'SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type = "table" AND name = "{self.table}")').fetchone()
            return bool(result[0])
        except sqlite3.OperationalError: return False
    
    async def _acheck_table_configured_(self, conn: t.Optional['AsyncConnection'] = None) -> bool:
        # sourcery skip: extract-method
        """
        Checks whether the DB has configured tables
        """
        conn = conn or await self._get_aio_()
        try:
            result = await (await conn.execute(f'SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type = "table" AND name = "{self.table}")')).fetchone()
            configured = bool(result[0])
            if configured: self._extra['has_configured_table'] = configured
            return configured
        except aiosqlite.OperationalError: return False

    @eproperty
    def has_configured_table(self) -> bool:
        """
        Returns whether the DB has configured the primary table
        """
        return self._check_table_configured_()
    
    def _validate_table_settings_(self, conn: t.Optional['Connection'] = None) -> bool: 
        # sourcery skip: extract-method
        """
        Validates the table settings
        """
        conn = conn or self._get_io_()
        if not self.has_configured_table: return False
        try:
            update_statement = f'UPDATE "{self.table}_settings" SET value = ? WHERE key = ?'
            # This means that the DB should have already been configured
            current_settings = dict(conn.execute(f'SELECT key, value FROM "{self.table}_settings"').fetchall())
            settings = get_optimized_settings(optimization = self.optimization, **self._config)
            diff_settings = dict_diff(current_settings, settings)['value_diffs']
            if diff_settings:
                for key, value in diff_settings.items():
                    if key.startswith('sqlite_'): 
                        if self._debug_enabled: logger.info(f'Skipping Diff: {key}: {value}')
                        continue
                    if self._debug_enabled: logger.info(f'Settings Diff: {key}: {value}')
                    current_settings[key] = value[1]
                    conn.execute(update_statement, (value[1], key))
            # We'll just set the values
            self._extra.update(current_settings)

            # Create tag index if requested.
            if self.tag_index:  # pylint: disable=no-member
                self.create_tag_index()
            # else:
            #     self.drop_tag_index()
            self.configured = True
            return True
        except sqlite3.OperationalError: 
            return False

    async def _avalidate_table_settings_(self, conn: t.Optional['AsyncConnection'] = None) -> bool: 
        # sourcery skip: extract-method
        """
        Validates the table settings
        """
        conn = conn or await self._get_aio_()
        if not await self._acheck_table_configured_(conn): return False
        try:
            update_statement = f'UPDATE "{self.table}_settings" SET value = ? WHERE key = ?'
            # This means that the DB should have already been configured
            current_settings: t.Dict[str, t.Union[str, int]] = dict(await (await conn.execute(f'SELECT key, value FROM "{self.table}_settings" ')).fetchall())
            settings = get_optimized_settings(optimization = self.optimization, **self._config)
            diff_settings = dict_diff(current_settings, settings)['value_diffs']
            if diff_settings:
                for key, value in diff_settings.items():
                    if key.startswith('sqlite_'): 
                        if self._debug_enabled: logger.info(f'Skipping Diff: {key}: {value}')
                        continue
                    if self._debug_enabled: logger.info(f'Settings Diff: {key}: {value}')
                    current_settings[key] = value[1]
                    await conn.execute(update_statement, (value[1], key))
            # We'll just set the values

            self._extra.update(current_settings)
            # Create tag index if requested.
            if self.tag_index:  # pylint: disable=no-member
                await self.acreate_tag_index()
        
            self.configured = True
            self._extra['has_configured_settings'] = True
            return True
        except aiosqlite.OperationalError: 
            return False
    
    @eproperty
    def has_configured_settings(self) -> bool:
        """
        Returns whether the DB has configured settings
        """
        return self._validate_table_settings_()

    @eproperty
    def _page_size(self) -> int:
        """
        Returns the page size
        """
        conn = self._io or self._get_io_()
        ((page_size,),) = conn.execute('PRAGMA page_size').fetchall()
        return page_size
    
    @eproperty
    def is_configured(self) -> bool:
        """
        Returns whether the DB has been configured
        """
        return self.has_configured_table and self.has_configured_settings

    def _validate_table_(self, conn: t.Optional['Connection'] = None) -> bool:
        # sourcery skip: extract-method
        """
        Validates the table settings
        """
        if self._extra.get('is_configured', False): return
        conn = conn or self._get_io_()
        self._extra['has_configured_table'] = self._check_table_configured_(conn)
        self._extra['has_configured_settings'] = self._validate_table_settings_(conn)
    
    async def _avalidate_table_(self, conn: t.Optional['AsyncConnection'] = None) -> bool:
        # sourcery skip: extract-method
        """
        Validates the table settings
        """
        if self._extra.get('is_configured', False): return
        provided_conn = conn is not None
        conn = conn or await self._get_aio_()
        await self._acheck_table_configured_(conn)
        await self._avalidate_table_settings_(conn)
        ((page_size,),) = (await (await conn.execute('PRAGMA page_size')).fetchall())
        self._extra['_page_size'] = page_size
        if not provided_conn: await conn.close()


    """
    Dynamic Properties
    """

    def _get_default_property(self, key):
        """
        Gets a default property
        """
        if self._config.get(key): return self._config[key]
        settings = get_optimized_settings(optimization = self.optimization)
        return settings[key]


    @eproperty
    def statistics(self) -> t.Union[bool, int]:
        """
        Returns the statistics
        """
        return self.reset('statistics', is_getter = True)

    @eproperty
    def tag_index(self) -> t.Union[bool, int]:
        """
        Returns the tag index
        """
        return self.reset('tag_index', is_getter = True)

    @eproperty
    def cull_limit(self) -> int:
        """
        Returns the cull limit
        """
        return self.reset('cull_limit', is_getter = True)
    
    @eproperty
    def size_limit(self) -> int:
        """
        Returns the size limit of items in the DB
        """
        return self.reset('size_limit', is_getter = True)
    
    @eproperty
    def eviction_policy(self) -> str:
        """
        Returns the Eviction Policy
        """
        if not self.configured:
            return self._get_default_property('eviction_policy')
        return self.reset('eviction_policy', is_getter = True)

    
    @eproperty
    def eviction_policies(self) -> Dict[str, str]:
        """
        Returns the eviction policies
        """
        return self._policies[self.eviction_policy]

    def run_configure(self):
        """
        Runs the configure
        """
        sql = self._sql_retry
        try: current_settings = dict(sql(f'SELECT key, value FROM "{self.table}_settings" ').fetchall())
        except sqlite3.OperationalError: current_settings = {}

        settings = get_optimized_settings(optimization = self.optimization, **current_settings)
        if self._config: settings.update(self._config)

        for key in METADATA:
            settings.pop(key, None)

        # Chance to set pragmas before any tables are created.
        for key, value in sorted(settings.items()):
            if key.startswith('sqlite_'):
                self.reset(key, value, update=False)
        
        # Setup Settings table.
        sql(
            f'CREATE TABLE IF NOT EXISTS "{self.table}_settings" ('
            ' key TEXT NOT NULL UNIQUE,'
            ' value)'
        )

        # Set cached attributes: updates settings and sets pragmas.
        for key, value in settings.items():
            query = f'INSERT OR REPLACE INTO "{self.table}_settings" VALUES (?, ?)'
            sql(query, (key, value))
            self.reset(key, value)

        for key, value in METADATA.items():
            query = f'INSERT OR IGNORE INTO "{self.table}_settings" VALUES (?, ?)'
            sql(query, (key, value))
            self.reset(key)

        # Setup Cache table.
        sql(
            f'CREATE TABLE IF NOT EXISTS "{self.table}" ('
            ' rowid INTEGER PRIMARY KEY,'
            ' key BLOB UNIQUE,'
            ' value BLOB,'
            ' store_time REAL,'
            ' expire_time REAL,'
            ' access_time REAL,'
            ' access_count INTEGER DEFAULT 0,'
            ' hit_count INTEGER DEFAULT 0,' # This doesn't reset whenever it is updated
            ' tag BLOB,'
            ' size INTEGER DEFAULT 0)'
        )
        sql(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{self.table}_key_rowid" ON'
            f' "{self.table}"(key, rowid)'
        )
        sql(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{self.table}_key_hits" ON'
            f' "{self.table}"(key, hit_count)'
        )
        sql(
            f'CREATE INDEX IF NOT EXISTS "{self.table}_expire_time" ON'
            f' "{self.table}" (expire_time) WHERE expire_time IS NOT NULL'
        )
        query = self.eviction_policies['init']
        if query is not None: sql(query)

        # Use triggers to keep Metadata updated.
        sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_count_insert"'
            f' AFTER INSERT ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings" SET value = value + 1'
            ' WHERE key = "count"; END'
        )

        sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_count_delete"'
            f' AFTER DELETE ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings" SET value = value - 1'
            ' WHERE key = "count"; END'
        )

        sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_size_insert"'
            f' AFTER INSERT ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings" SET value = value + NEW.size'
            ' WHERE key = "size"; END'
        )

        sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_size_update"'
            f' AFTER UPDATE ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings"'
            ' SET value = value + NEW.size - OLD.size'
            ' WHERE key = "size"; END'
        )

        sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_size_delete"'
            f' AFTER DELETE ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings" SET value = value - OLD.size'
            ' WHERE key = "size"; END'
        )


        # Create tag index if requested.
        if self.tag_index:  # pylint: disable=no-member
            self.create_tag_index()
        # else:
        #     self.drop_tag_index()

        self.configured = True
        self.is_configured = True

        # Close and re-open database connection with given timeout.
        self.close()
        if self._debug_enabled: logger.info(f'Completed SQLite Database Connection: {self.conn_uri}')
        # self._get_io_()

    async def arun_configure(self):
        """
        Runs the configure
        """
        sql = self._asql_retry
        try: current_settings: t.Dict[str, t.Union[str, int]] = dict(await (await sql(f'SELECT key, value FROM "{self.table}_settings" ')).fetchall())
        except aiosqlite.OperationalError: current_settings = {}

        settings = get_optimized_settings(optimization = self.optimization, **current_settings)
        if self._config: settings.update(self._config)

        for key in METADATA:
            settings.pop(key, None)

        # Chance to set pragmas before any tables are created.
        for key, value in sorted(settings.items()):
            if key.startswith('sqlite_'):
                await self.areset(key, value, update=False)
        
        # Setup Settings table.
        await sql(
            f'CREATE TABLE IF NOT EXISTS "{self.table}_settings" ('
            ' key TEXT NOT NULL UNIQUE,'
            ' value)'
        )

        # Set cached attributes: updates settings and sets pragmas.
        for key, value in settings.items():
            query = f'INSERT OR REPLACE INTO "{self.table}_settings" VALUES (?, ?)'
            await sql(query, (key, value))
            await self.areset(key, value)

        for key, value in METADATA.items():
            query = f'INSERT OR IGNORE INTO "{self.table}_settings" VALUES (?, ?)'
            await sql(query, (key, value))
            await self.areset(key)

        # Setup Cache table.
        await sql(
            f'CREATE TABLE IF NOT EXISTS "{self.table}" ('
            ' rowid INTEGER PRIMARY KEY,'
            ' key BLOB UNIQUE,'
            ' value BLOB,'
            ' store_time REAL,'
            ' expire_time REAL,'
            ' access_time REAL,'
            ' access_count INTEGER DEFAULT 0,'
            ' hit_count INTEGER DEFAULT 0,' # This doesn't reset whenever it is updated
            ' tag BLOB,'
            ' size INTEGER DEFAULT 0)'
        )
        await sql(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{self.table}_key_rowid" ON'
            f' "{self.table}"(key, rowid)'
        )
        await sql(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{self.table}_key_hits" ON'
            f' "{self.table}"(key, hit_count)'
        )
        await sql(
            f'CREATE INDEX IF NOT EXISTS "{self.table}_expire_time" ON'
            f' "{self.table}" (expire_time) WHERE expire_time IS NOT NULL'
        )
        query = self.eviction_policies['init']
        if query is not None: await sql(query)

        # Use triggers to keep Metadata updated.
        await sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_count_insert"'
            f' AFTER INSERT ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings" SET value = value + 1'
            ' WHERE key = "count"; END'
        )

        await sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_count_delete"'
            f' AFTER DELETE ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings" SET value = value - 1'
            ' WHERE key = "count"; END'
        )

        await sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_size_insert"'
            f' AFTER INSERT ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings" SET value = value + NEW.size'
            ' WHERE key = "size"; END'
        )

        await sql(
            f'CREATE TRIGGER IF NOT EXISTS {self.table}_settings_size_update'
            f' AFTER UPDATE ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings"'
            ' SET value = value + NEW.size - OLD.size'
            ' WHERE key = "size"; END'
        )

        await sql(
            f'CREATE TRIGGER IF NOT EXISTS "{self.table}_settings_size_delete"'
            f' AFTER DELETE ON "{self.table}" FOR EACH ROW BEGIN'
            f' UPDATE "{self.table}_settings" SET value = value - OLD.size'
            ' WHERE key = "size"; END'
        )


        # Create tag index if requested.
        if self.tag_index:  # pylint: disable=no-member
            await self.acreate_tag_index()
        # else:
        #     self.drop_tag_index()

        self.configured = True
        self.is_configured = True

        # Close and re-open database connection with given timeout.
        await self.aclose()
        if self._debug_enabled: logger.info(f'Completed SQLite Database Connection: {self.conn_uri}')
        # self._get_io_()




    """
    Context Managers
    """

    @contextlib.contextmanager
    def transact(self, retry: bool = False) -> t.Generator[t.Callable[..., 'Cursor'], None, None]:
        """Context manager to perform a transaction by locking the cache.

        While the cache is locked, no other write operation is permitted.
        Transactions should therefore be as short as possible. Read and write
        operations performed in a transaction are atomic. Read operations may
        occur concurrent to a transaction.

        Transactions may be nested and may not be shared between threads.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        >>> cache = Cache()
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

    @contextlib.contextmanager
    def _transact(self, retry: bool = False) -> t.Generator[t.Callable[..., 'Cursor'], None, None]:
        """
        Transaction Context Manager
        """
        self._init_io_()
        sql = self._sql
        # try:
        #     tid = asyncio.get_running_loop()._thread_id
        # except:
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
                except sqlite3.OperationalError as e:
                    logger.info(f'SQLite Error: {e}')
                    if retry: continue
                    raise Timeout from None

        try:
            yield sql
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


    @contextlib.asynccontextmanager
    async def atransact(self, retry: bool = False) -> t.AsyncGenerator[t.Awaitable[t.Callable[..., t.Awaitable['AsyncCursor']]], None]:
        """Context manager to perform a transaction by locking the cache.

        While the cache is locked, no other write operation is permitted.
        Transactions should therefore be as short as possible. Read and write
        operations performed in a transaction are atomic. Read operations may
        occur concurrent to a transaction.

        Transactions may be nested and may not be shared between threads.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default).

        >>> cache = Cache()
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
        async with self._atransact(retry=retry):
            yield

    @contextlib.asynccontextmanager
    async def _atransact(self, retry: bool = False) -> t.AsyncGenerator[t.Callable[..., t.Awaitable['AsyncCursor']], None]:
        """
        [Async] Transaction Context Manager
        """
        await self._init_aio_()
        sql = self._asql
        tid = asyncio.get_running_loop()._thread_id
        txn_id = self._txn_id
        if tid == txn_id: begin = False
        else:
            while True:
                try:
                    await sql('BEGIN IMMEDIATE')
                    begin = True
                    self._txn_id = tid
                    break
                except aiosqlite.OperationalError:
                    if retry: continue
                    raise Timeout from None

        try:
            yield sql
        except BaseException:
            if begin:
                assert self._txn_id == tid
                self._txn_id = None
                await sql('ROLLBACK')
            raise
        else:
            if begin:
                assert self._txn_id == tid
                self._txn_id = None
                await sql('COMMIT')

    @contextlib.contextmanager
    def _transact_many(self, retry: bool = False) -> t.Generator[t.Callable[..., t.Tuple['Cursor', 'Cursor']], None, None]:
        """
        [Many] Transaction Context Manager

        Returns a tuple of (io.execute, io.executemany) cursors
        """
        self._init_io_()
        sql = self._sql
        sqlmany = self._sqlmany
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
                except sqlite3.OperationalError as e:
                    logger.info(f'SQLite Error: {e}')
                    if retry: continue
                    raise Timeout from None

        try:
            yield (sql, sqlmany)
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


    @contextlib.asynccontextmanager
    async def _atransact_many(self, retry: bool = False) -> t.AsyncGenerator[t.Callable[..., t.Tuple[t.Awaitable['AsyncCursor'], t.Awaitable['AsyncCursor']]], None]:
        """
        [Async - Many] Transaction Context Manager
        
        Returns a tuple of (aio.execute, aio.executemany) cursors
        """
        await self._init_aio_()
        sql = self._asql
        sqlmany = self._asqlmany
        tid = asyncio.get_running_loop()._thread_id
        txn_id = self._txn_id
        if tid == txn_id: begin = False
        else:
            while True:
                try:
                    await sql('BEGIN IMMEDIATE')
                    begin = True
                    self._txn_id = tid
                    break
                except aiosqlite.OperationalError:
                    if retry: continue
                    raise Timeout from None

        try:
            yield (sql, sqlmany)
        except BaseException:
            if begin:
                assert self._txn_id == tid
                self._txn_id = None
                await sql('ROLLBACK')
            raise
        else:
            if begin:
                assert self._txn_id == tid
                self._txn_id = None
                await sql('COMMIT')
    
    def _format_keys_(self, keys: t.Iterable[str]) -> str:
        """
        Formats the keys
    
        >>> format_keys_(['key1', 'key2'])
        '"key1", "key2"'
        """
        return ', '.join([f'"{key}"' for key in keys])
    
    def _format_rowids_(self, rowids: t.Iterable[int]) -> str:
        """
        Formats the rowids
        
        >>> format_rowids_([1, 2])
        '(1, 2)'
        """
        return  ', '.join(str(rowid) for rowid in rowids)



    """
    Basic CRUD Methods 
    """
    
    def _select_delete(
        self, 
        select: str, 
        args: List[Any],
        row_index: int = 0,
        arg_index: int = 0,
        retry: bool = False
    ):
        """
        Delete rows from Cache
        """
        count = 0
        delete = f'DELETE FROM "{self.table}" WHERE rowid IN (%s)'
        try:
            while True:
                with self._transact(retry) as sql:
                    rows = sql(select, args).fetchall()
                    if not rows: break
                    count += len(rows)
                    sql(delete % self._format_rowids_((row[0] for row in rows)))
                    # sql(delete % ','.join(str(row[0]) for row in rows))
                    for row in rows:
                        args[arg_index] = row[row_index]
                    #     cleanup(row[-1])

        except Timeout: raise Timeout(count) from None
        return count
    
    async def _aselect_delete(
        self, 
        select: str, 
        args: List[Any],
        row_index: int = 0,
        arg_index: int = 0,
        retry: bool = False
    ):
        """
        Delete rows from Cache
        """
        count = 0
        delete = f'DELETE FROM "{self.table}" WHERE rowid IN (%s)'
        try:
            while True:
                async with self._atransact(retry) as sql:
                    rows = await (await sql(select, args)).fetchall()
                    if not rows: break
                    count += len(rows)
                    await sql(delete % self._format_rowids_((row[0] for row in rows)))
                    # await sql(delete % ','.join(str(row[0]) for row in rows))
                    for row in rows:
                        args[arg_index] = row[row_index]
        
        except Timeout: raise Timeout(count) from None
        return count


    def _row_update(self, rowid: int, now: float, columns: t.Tuple[t.Any, ...], is_async: bool = False):
        """
        Updates the row
        """
        sql = self._asql if is_async else self._sql
        # expire_time, tag, size, mode, filename, value = columns
        expire_time, tag, size, value = columns
        return sql(
            f'UPDATE "{self.table}" SET'
            ' store_time = ?,'
            ' expire_time = ?,'
            ' access_time = ?,'
            ' access_count = ?,'
            ' tag = ?,'
            ' size = ?,'
            ' value = ?'
            ' WHERE rowid = ?',
            (
                now,  # store_time
                expire_time,
                now,  # access_time
                0,  # access_count
                tag,
                size,
                value,
                rowid,
            ),
        )


    # def _row_insert(self, key: str, raw: int, now: float, columns: t.Tuple[t.Any, ...], is_async: bool = False):
    def _row_insert(self, key: str, now: float, columns: t.Tuple[t.Any, ...], is_async: bool = False):
        """
        Inserts the row
        """
        sql = self._asql if is_async else self._sql
        # expire_time, tag, size, mode, filename, value = columns
        expire_time, tag, size, value = columns
        return sql(
            f'INSERT INTO "{self.table}"('
            ' key, store_time, expire_time, access_time,'
            ' access_count, tag, size, value'
            ') VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (
                key,
                now,  # store_time
                expire_time,
                now,  # access_time
                0,  # access_count
                tag,
                size,
                value,
            ),
        )

    def _row_upsert(self, key: str, now: float, columns: t.Tuple[t.Any, ...], is_async: bool = False, sql: t.Union[t.Callable[..., t.Awaitable['Cursor']], t.Callable[..., 'Cursor']] = None):
        """
        Upserts a row
        """
        if sql is None: sql = self._asql if is_async else self._sql
        expire_time, tag, size, value = columns
        return sql(
            f'INSERT INTO "{self.table}" ('
            ' key, store_time, expire_time, access_time,'
            ' access_count, tag, size, value'
            ') VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
            ' ON CONFLICT(key) DO UPDATE SET'
                ' store_time = excluded.store_time,'
                ' expire_time = excluded.expire_time,'
                ' access_time = excluded.access_time,'
                ' access_count = excluded.access_count,'
                ' tag = excluded.tag,'
                ' size = excluded.size,'
                ' value = excluded.value',
            (
                key,
                now,  # store_time
                expire_time,
                now,  # access_time
                0,  # access_count
                tag,
                size,
                value,
            ),
        )

    def _bulk_insert(self, data: t.Dict[str, t.Any], now: float, columns: t.Tuple[t.Any, ...], is_async: bool = False, sql: t.Union[t.Callable[..., t.Awaitable['Cursor']], t.Callable[..., 'Cursor']] = None):
        """
        Inserts the many rows of data
        where data = {
            key: value
        }
        """
        if sql is None: sql = self._asql if is_async else self._sql
        # sql = self._asql if is_async else self._sql
        # expire_time, tag, size, mode, filename, value = columns
        expire_time, tag = columns
        batch_data = [
            (
                key,
                now,  # store_time
                expire_time,
                now,  # access_time
                0,  # access_count
                tag,
                self.get_object_size(value),
                value,
            )
            for key, value in data.items()
        ]
        if not batch_data: return
        sql(
            f'INSERT INTO "{self.table}"('
            ' key, store_time, expire_time, access_time,'
            ' access_count, tag, size, value'
            ') VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            batch_data,
        )

    def _bulk_update(self, data: t.Dict[str, t.Any], now: float, columns: t.Tuple[t.Any, ...], is_async: bool = False):
        """
        Updates the a batch of rows of data
        """
        sql = self._asqlmany if is_async else self._sqlmany
        expire_time, tag = columns
        batch_data = [
            (
                now,  # store_time
                expire_time,
                now,  # access_time
                0,  # access_count
                tag,
                self.get_object_size(value),
                value,
                key,
            )
            for key, value in data.items()
        ]
        return sql(
            f'UPDATE "{self.table}" SET'
            ' store_time = ?,'
            ' expire_time = ?,'
            ' access_time = ?,'
            ' access_count = ?,'
            ' tag = ?,'
            ' size = ?,'
            ' value = ?'
            ' WHERE key = ?',
            batch_data,
        )

    def _bulk_upsert(self, data: t.Dict[str, t.Any], now: float, columns: t.Tuple[t.Any, ...], is_async: bool = False, sql: t.Callable[..., t.Awaitable[t.Any]] = None):
        """
        Upserts the a batch of rows of data
        """
        if sql is None: sql = self._asqlmany if is_async else self._sqlmany
        expire_time, tag = columns
        batch_data = [
            (
                key,
                now,  # store_time
                expire_time,
                now,  # access_time
                0,  # access_count
                tag,
                self.get_object_size(value),
                value,
            )
            for key, value in data.items()
        ]
        return sql(
            f'INSERT INTO "{self.table}" ('
            ' key, store_time, expire_time, access_time,'
            ' access_count, tag, size, value'
            ') VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
            ' ON CONFLICT(key) DO UPDATE SET'
                ' store_time = excluded.store_time,'
                ' expire_time = excluded.expire_time,'
                ' access_time = excluded.access_time,'
                ' access_count = excluded.access_count,'
                ' tag = excluded.tag,'
                ' size = excluded.size,'
                ' value = excluded.value',
            batch_data,
        )
    
    """
    Index / Tag Methods
    """

    def create_tag_index(self):
        """Create tag index on cache database.

        It is better to initialize cache with `tag_index=True` than use this.

        :raises Timeout: if database timeout occurs

        """
        sql = self._sql
        sql(
            f'CREATE INDEX IF NOT EXISTS "{self.table}_tag_rowid" ON "{self.table}"(tag, rowid) '
            'WHERE tag IS NOT NULL'
        )
        self.reset('tag_index', 1)
    
    async def acreate_tag_index(self):
        """Create tag index on cache database.

        It is better to initialize cache with `tag_index=True` than use this.

        :raises Timeout: if database timeout occurs

        """
        sql = self._asql
        await sql(
            f'CREATE INDEX IF NOT EXISTS "{self.table}_tag_rowid" ON "{self.table}"(tag, rowid) '
            'WHERE tag IS NOT NULL'
        )
        await self.areset('tag_index', 1)

    def drop_tag_index(self):
        """Drop tag index on cache database.

        :raises Timeout: if database timeout occurs
        """
        sql = self._sql
        sql(f'DROP INDEX IF EXISTS "{self.table}_tag_rowid"')
        self.reset('tag_index', 0)
    
    async def adrop_tag_index(self):
        """Drop tag index on cache database.

        :raises Timeout: if database timeout occurs
        """
        await self._asql(f'DROP INDEX IF EXISTS "{self.table}_tag_rowid"')
        await self.areset('tag_index', 0)
    

    def get_object_size(self, value: t.Any) -> int:
        """
        Returns the object size
        """
        return len(value) if isinstance(value, (bytes, bytearray)) else len(pickle.dumps(value))

    def reset(self, key: str, value: t.Any = ENOVAL, update: bool = True, is_getter: bool = False):
        # sourcery skip: extract-duplicate-method
        """Reset `key` and `value` item from Settings table.

        Use `reset` to update the value of Cache settings correctly. Cache
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
            select = f'SELECT value FROM "{self.table}_settings"  WHERE key = ?'
            ((value,),) = sql_retry(select, (key,)).fetchall()
            if not is_getter: self._extra[key] = value
            if key == 'eviction_policy': self._extra['eviction_policies'] = self._policies[value]
            return value

        if update and value:
            statement = f'UPDATE "{self.table}_settings" SET value = ? WHERE key = ?'
            sql_retry(statement, (value, key))

        if key.startswith('sqlite_') and not self.is_child_db:
            # if self.is_child_db: return
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
                    except ValueError: update = True
                    if update: sql(f'PRAGMA {pragma} = {value}').fetchall()
                    break
                except sqlite3.OperationalError as exc:
                    if str(exc) != 'database is locked': raise
                    diff = time.time() - start
                    if diff > 60: raise
                    time.sleep(0.001)

        if not is_getter: self._extra[key] = value
        if key == 'eviction_policy': self._extra['eviction_policies'] = self._policies[value]
        return value
    

    async def areset(self, key: str, value: t.Any = ENOVAL, update: bool = True, is_getter: bool = False):
        # sourcery skip: extract-duplicate-method
        """Reset `key` and `value` item from Settings table.

        Use `reset` to update the value of Cache settings correctly. Cache
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
        sql = self._asql
        sql_retry = self._asql_retry
        if value is ENOVAL:
            select = f'SELECT value FROM "{self.table}_settings"  WHERE key = ?'
            ((value,),) = await (await sql_retry(select, (key,))).fetchall()
            if not is_getter: self._extra[key] = value
            if key == 'eviction_policy': self._extra['eviction_policies'] = self._policies[value]
            return value

        if update and value:
            statement = f'UPDATE "{self.table}_settings" SET value = ? WHERE key = ?'
            await sql_retry(statement, (value, key))

        if key.startswith('sqlite_') and not self.is_child_db:
            # if self.is_child_db: return
            pragma = key[7:]

            start = time.time()
            while True:
                try:
                    try:
                        ((old_value,),) = await (await sql(f'PRAGMA {pragma}')).fetchall()
                        update = old_value != value
                    except ValueError: update = True
                    if update: await (await sql(f'PRAGMA {pragma} = {value}')).fetchall()
                    break
                except aiosqlite.OperationalError as exc:
                    if str(exc) != 'database is locked': raise
                    diff = time.time() - start
                    if diff > 60: raise
                    await asyncio.sleep(0.001)

        if not is_getter: self._extra[key] = value
        if key == 'eviction_policy': self._extra['eviction_policies'] = self._policies[value]
        return value
    
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

    async def astats(self, enable=True, reset=False):
        """Return cache statistics hits and misses.

        :param bool enable: enable collecting statistics (default True)
        :param bool reset: reset hits and misses to 0 (default False)
        :return: (hits, misses)

        """
        # pylint: disable=E0203,W0201
        hits, misses = await self.areset('hits'), await self.areset('misses')
        result = (hits, misses)
        if reset:
            await self.areset('hits', 0)
            await self.areset('misses', 0)
        
        await self.areset('statistics', enable)
        return result

    def volume(self):
        """Return estimated total size of cache on disk.

        :return: size in bytes
        """
        ((page_count,),) = self._sql('PRAGMA page_count').fetchall()
        return self._page_size * page_count + self.reset('size')
    

    async def avolume(self):
        """Return estimated total size of cache on disk.

        :return: size in bytes
        """
        ((page_count,),) = await (await self._asql('PRAGMA page_count')).fetchall()
        return self._page_size * page_count + await self.areset('size')


    def fetch_keys(
        self,
        pattern: t.Optional[str] = None,
        include_rowid: Optional[bool] = False,
        order: t.Optional[t.Literal['ASC', 'DESC']] = 'ASC',
        order_by: t.Optional[str] = 'rowid',
        limit: Optional[int] = None,
        retry: bool = False,
    ) -> t.Union[List[str], t.Tuple[List[str], List[int]]]:
        # sourcery skip: extract-method
        """
        Fetches the keys
        """
        select = (
            f'SELECT key, rowid FROM "{self.table}"'
        )
        args = ()
        if pattern: 
            select += ' WHERE key LIKE ?'
            args = (pattern,)
        if order: select += f' ORDER BY {order_by} {order}'
        if limit: select += f' LIMIT {limit}'
        with self._transact(retry) as sql:
            rows = sql(
                select,
                args,
            ).fetchall()
            if not rows: return [], [] if include_rowid else []
            keys = [row[0] for row in rows]
            if not include_rowid: return keys
            rowids = [row[1] for row in rows]
            return keys, rowids

    async def afetch_keys(
        self,
        pattern: t.Optional[str] = None,
        include_rowid: Optional[bool] = False,
        order: t.Optional[t.Literal['ASC', 'DESC']] = 'ASC',
        order_by: t.Optional[str] = 'rowid',
        limit: Optional[int] = None,
        retry: bool = False,
    ) -> t.Union[List[str], t.Tuple[List[str], List[int]]]:
        # sourcery skip: extract-method
        """
        Fetches the keys
        """
        select = (
            f'SELECT key, rowid FROM "{self.table}"'
        )
        args = ()
        if pattern: 
            select += ' WHERE key LIKE ?'
            args = (pattern,)
        if order: select += f' ORDER BY {order_by} {order}'
        if limit: select += f' LIMIT {limit}'
        
        async with self._atransact(retry) as sql:
            rows = await (await sql(
                select,
                args,
            )).fetchall()
            if not rows: return [], [] if include_rowid else []
            keys = [row[0] for row in rows]
            if not include_rowid: return keys
            rowids = [row[1] for row in rows]
            return keys, rowids
    """
    Class Methods
    """

    def _delete_key_(self, key: str, retry: bool = True):
        """Delete corresponding item for `key` from cache.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default `True`).

        :param key: key matching item
        :param bool retry: retry if database timeout occurs (default True)
        :raises KeyError: if key is not found
        :raises Timeout: if database timeout occurs

        """
        with self._transact(retry) as sql:
            rows = sql(
                f'SELECT rowid FROM "{self.table}"'
                ' WHERE key = ? AND raw = ?'
                ' AND (expire_time IS NULL OR expire_time > ?)',
                (key, time.time()),
            ).fetchall()
            if not rows: raise KeyError(key)
            ((rowid,),) = rows
            sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))
            return True
    
    async def _adelete_key_(self, key: str, retry: bool = True):
        """[Async Background] Delete corresponding item for `key` from cache.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default `True`).

        :param key: key matching item
        :param bool retry: retry if database timeout occurs (default True)
        :raises KeyError: if key is not found
        :raises Timeout: if database timeout occurs

        """
        async with self._atransact(retry) as sql:
            rows = await (await sql(
                f'SELECT rowid FROM "{self.table}"'
                ' WHERE key = ?'
                ' AND (expire_time IS NULL OR expire_time > ?)',
                (key, time.time()),
            )).fetchall()
            if not rows: raise KeyError(key)
            ((rowid,),) = rows
            await sql(f'DELETE FROM "{self.table}" WHERE rowid = ?', (rowid,))
            return True

    def _delete_keys_(self, *keys: str, retry: bool = True) -> int:
        """Delete corresponding item for `key` from cache.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default `True`).

        :param keys: keys matching item
        :param bool retry: retry if database timeout occurs (default True)
        :raises KeyError: if key is not found
        :raises Timeout: if database timeout occurs

        """
        with self._transact(retry) as sql:
            rows = sql(
                f'SELECT rowid FROM "{self.table}"'
                ' WHERE key IN (%s)'
                ' AND (expire_time IS NULL OR expire_time > ?)' % self._format_keys_(keys),
                (time.time(),),
            ).fetchall()
            if not rows: raise KeyError(keys)
            rowids = [row[0] for row in rows if row]
            sql(f'DELETE FROM "{self.table}" WHERE rowid IN (%s)' % self._format_rowids_(rowids))
            return len(rowids)
    
    async def _adelete_keys_(self, *keys: str, retry: bool = True) -> int:
        """[Async] Delete corresponding item for `keys` from cache.

        Raises :exc:`Timeout` error when database timeout occurs and `retry` is
        `False` (default `True`).

        :param keys: keys matching item
        :param bool retry: retry if database timeout occurs (default True)
        :raises KeyError: if key is not found
        :raises Timeout: if database timeout occurs
        """
        async with self._atransact(retry) as sql:
            rows = await (await sql(
                f'SELECT rowid FROM "{self.table}"'
                ' WHERE key IN (%s)'
                ' AND (expire_time IS NULL OR expire_time > ?)' % self._format_keys_(keys),
                (time.time(),),
            )).fetchall()
            if not rows: raise KeyError(keys)
            rowids = [row[0] for row in rows if row]
            await sql(f'DELETE FROM "{self.table}" WHERE rowid IN (%s)' % self._format_rowids_(rowids))
            return len(rowids)

    def _set_key_expiration_(self, key: str, ex: float, retry: bool = True) -> None:
        """
        Sets the expiration for a key
        """
        sql = self._sql_retry if retry else self._sql
        now = time.time()
        if ex < now: ex = now + ex
        sql(f'UPDATE "{self.table}" SET expire_time = ? WHERE key = ?', (ex, key))

    async def _aset_key_expiration_(self, key: str, ex: float, retry: bool = True) -> None:
        """
        [Async] Sets the expiration for a key
        """
        sql = self._asql_retry if retry else self._asql
        now = time.time()
        if ex < now: ex = now + ex
        await sql(f'UPDATE "{self.table}" SET expire_time = ? WHERE key = ?', (ex, key))

    def _set_key_tag_(self, key: str, tag: str, retry: bool = True) -> None:
        """
        Sets the tag for a key
        """
        sql = self._sql_retry if retry else self._sql
        sql(f'UPDATE "{self.table}" SET tag = ? WHERE key = ?', (tag, key))

    async def _aset_key_tag_(self, key: str, tag: str, retry: bool = True) -> None:
        """
        [Async] Sets the tag for a key
        """
        sql = self._asql_retry if retry else self._asql
        await sql(f'UPDATE "{self.table}" SET tag = ? WHERE key = ?', (tag, key))
    
    def contains(self, key: str, retry: bool = True) -> bool:
        """Return `True` if `key` matching item is found in cache.

        :param key: key matching item
        :return: True if key matching item

        """
        sql = self._sql_retry if retry else self._sql
        select = (
            f'SELECT rowid FROM "{self.table}"'
            ' WHERE key = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )
        rows = sql(select, (key, time.time())).fetchall()
        return bool(rows)
    
    async def acontains(self, key: str, retry: bool = True) -> bool:
        """[Async Background] Return `True` if `key` matching item is found in cache.

        :param key: key matching item
        :return: True if key matching item

        """
        sql = self._asql_retry if retry else self._asql
        select = (
            f'SELECT rowid FROM "{self.table}"'
            ' WHERE key = ?'
            ' AND (expire_time IS NULL OR expire_time > ?)'
        )
        rows = await (await sql(select, (key, time.time()))).fetchall()
        return bool(rows)

    def _iter(self, ascending: bool = True) -> t.Generator[t.Any, None, None]:
        """
        Iterate Cache items in database sort order.
        """
        sql = self._sql
        rows = sql(f'SELECT MAX(rowid) FROM "{self.table}"').fetchall()
        ((max_rowid,),) = rows
        yield  # Signal ready.

        if max_rowid is None: return
        bound = max_rowid + 1
        limit = 100
        # _disk_get = self._disk.get
        rowid = 0 if ascending else bound
        select = (
            f'SELECT rowid, key FROM "{self.table}"'
            ' WHERE ? < rowid AND rowid < ?'
            ' ORDER BY rowid %s LIMIT ?'
        ) % ('ASC' if ascending else 'DESC')

        while True:
            args = (rowid, bound, limit) if ascending else (0, rowid, limit)
            rows = sql(select, args).fetchall()
            if not rows: break
            for rowid, key in rows: yield iter(key)
    
    async def _aiter(self, ascending: bool = True) -> t.AsyncGenerator[t.Any, None]:
        """
        [Async Background] Iterate Cache items in database sort order.
        """
        sql = self._asql
        rows = await (await sql(f'SELECT MAX(rowid) FROM "{self.table}"')).fetchall()
        ((max_rowid,),) = rows
        yield  # Signal ready.

        if max_rowid is None: return
        bound = max_rowid + 1
        limit = 100
        rowid = 0 if ascending else bound
        select = (
            f'SELECT rowid, key FROM "{self.table}"'
            ' WHERE ? < rowid AND rowid < ?'
            ' ORDER BY rowid %s LIMIT ?'
        ) % ('ASC' if ascending else 'DESC')

        while True:
            args = (rowid, bound, limit) if ascending else (0, rowid, limit)
            rows = await (await sql(select, args)).fetchall()
            if not rows: break
            for rowid, key in rows: yield aiter(key)

    
    def iterkeys(self, reverse=False):
        """Iterate Cache keys in database sort order.

        >>> cache = Cache()
        >>> for key in [4, 1, 3, 0, 2]:
        ...     cache[key] = key
        >>> list(cache.iterkeys())
        [0, 1, 2, 3, 4]
        >>> list(cache.iterkeys(reverse=True))
        [4, 3, 2, 1, 0]

        :param bool reverse: reverse sort order (default False)
        :return: iterator of Cache keys

        """
        sql = self._sql
        limit = 100
        if reverse:
            select = (
                f'SELECT key FROM "{self.table}"'
                ' ORDER BY key DESC LIMIT 1'
            )
            iterate = (
                f'SELECT key FROM "{self.table}"'
                ' WHERE key = ? OR key < ?'
                ' ORDER BY key DESC LIMIT ?'
            )
        else:
            select = (
                f'SELECT key FROM "{self.table}"'
                ' ORDER BY key ASC LIMIT 1'
            )
            iterate = (
                f'SELECT key FROM "{self.table}"'
                ' WHERE key = ? OR key > ?'
                ' ORDER BY key ASC LIMIT ?'
            )

        row = sql(select).fetchall()
        if row: ((key,),) = row
        else: return
        yield iter(key)
        while True:
            rows = sql(iterate, (key, key, limit)).fetchall()
            if not rows: break
            for key in rows: yield iter(key)
    
    async def aiterkeys(self, reverse=False):
        """[Async] Iterate Cache keys in database sort order.

        >>> cache = Cache()
        >>> for key in [4, 1, 3, 0, 2]:
        ...     cache[key] = key
        >>> list(cache.aiterkeys())
        [0, 1, 2, 3, 4]
        >>> list(cache.aiterkeys(reverse=True))
        [4, 3, 2, 1, 0]

        :param bool reverse: reverse sort order (default False)
        :return: iterator of Cache keys

        """
        sql = self._asql
        limit = 100
        if reverse:
            select = (
                f'SELECT key FROM "{self.table}"'
                ' ORDER BY key DESC LIMIT 1'
            )
            iterate = (
                f'SELECT key FROM "{self.table}"'
                ' WHERE key = ? OR key < ?'
                ' ORDER BY key DESC LIMIT ?'
            )
        else:
            select = (
                f'SELECT key FROM "{self.table}"'
                ' ORDER BY key ASC LIMIT 1'
            )
            iterate = (
                f'SELECT key FROM "{self.table}"'
                ' WHERE key = ? OR key > ?'
                ' ORDER BY key ASC LIMIT ?'
            )

        row = await (await sql(select)).fetchall()
        if row: ((key,),) = row
        else: return
        yield aiter(key)
        while True:
            rows = await (await sql(iterate, (key, key, limit))).fetchall()
            if not rows: break
            for key in rows: yield aiter(key)
    

    def __iter__(self):
        """Iterate keys in cache including expired items."""
        iterator = self._iter()
        next(iterator)
        return iterator

    async def __aiter__(self):
        """[Async] Iterate keys in cache including expired items."""
        iterator = self._aiter()
        await anext(iterator)
        return iterator
    
    def __reversed__(self):
        """Reverse iterate keys in cache including expired items."""
        iterator = self._iter(ascending=False)
        next(iterator)
        return iterator

    def length(self) -> int:
        """Return the length of the cache.
        """
        return self.reset('count')
    
    async def alength(self) -> int:
        """[Async] Return the length of the cache.
        """
        return await self.areset('count')

    def __hash__(self):
        """Return the hash of the cache.
        """
        return hash(f'{self.table}:{self.conn_uri}')


    def __enter__(self):
        # Create connection in thread.
        # pylint: disable=unused-variable
        self._init_io_()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close connection in thread.
        # pylint: disable=unused-variable
        self.close()
    
    async def __aenter__(self):
        # Create connection in thread.
        # pylint: disable=unused-variable
        await self._init_aio_()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Close connection in thread.
        # pylint: disable=unused-variable    
        await self.aclose()
