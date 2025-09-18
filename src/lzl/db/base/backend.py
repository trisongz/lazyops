from __future__ import annotations

"""
Base Backends
"""

import abc
import time
import asyncio
import contextlib

from lzl.logging import logger, null_logger, Logger
from lzl.types import eproperty
from .config import BackendType, DBConfigT
from .utils import SQLAlchemyUtilities
import typing as t

if t.TYPE_CHECKING:
    from sqlalchemy import Connection, Engine
    from sqlalchemy.orm import Session, session, sessionmaker, scoped_session
    from sqlalchemy.ext.asyncio import async_sessionmaker, async_scoped_session
    from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, AsyncConnection

    from sqlmodel import Session as SMSession
    from sqlmodel.ext.asyncio.session import AsyncSession as SMAsyncSession

    SessionT = t.Union[SMSession, Session]
    AsyncSessionT = t.Union[SMAsyncSession, AsyncSession]

    SessionMakerT = sessionmaker[SessionT]
    AsyncSessionMakerT = async_sessionmaker[AsyncSessionT]

    ScopedSessionMakerT = scoped_session[SessionT]
    AsyncScopedSessionMakerT = async_scoped_session[AsyncSessionT]

    SessionGetT = t.Union[SessionMakerT, ScopedSessionMakerT]
    AsyncSessionGetT = t.Union[AsyncSessionMakerT, AsyncScopedSessionMakerT]

    SessionGetterT = t.Union[SessionGetT, AsyncSessionGetT]

    SMSessionMakerT = sessionmaker[SMSession]
    SMAsyncSessionMakerT = async_sessionmaker[SMAsyncSession]

    SMScopedSessionMakerT = scoped_session[SMSession]
    SMAsyncScopedSessionMakerT = async_scoped_session[SMAsyncSession]

    SMSessionGetT = t.Union[SMSessionMakerT, SMScopedSessionMakerT]
    SMAsyncSessionGetT = t.Union[SMAsyncSessionMakerT, SMAsyncScopedSessionMakerT]
    SMSessionGetterT = t.Union[SMSessionGetT, SMAsyncSessionGetT]

    from lzl.pool import ThreadPool
    from sqlalchemy import TextClause


class BaseDatabaseBackend(abc.ABC):
    """
    Base Database Connection
    """
    name: t.Optional[str] = 'default'
    backend: t.Optional[BackendType] = None
    
    _extra: t.Dict[str, t.Any] = {}

    def __init__(
        self,
        config: DBConfigT,
        name: t.Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Initializes the Database Connection
        """
        if name: self.name = name
        elif config.name: self.name = config.name
        self.config = config
        self.extra_kws = kwargs
        self._default_scoped = {
            'sync': self.config.session.scoped,
            'async': self.config.asession.scoped,
        }
        self.db_type = self.config.adapter_prefix
        self.db_type_name = self.db_type.capitalize()
        if not self.db_type_name.endswith('DB'): self.db_type_name += 'DB'
        self.post_init(**kwargs)

    def post_init(self, **kwargs):
        """
        Post Initialization
        """
        pass

    @eproperty
    def tpool(self) -> 'ThreadPool':
        """
        Returns the ThreadPool
        """
        from lzl.pool import ThreadPool
        return ThreadPool
    
    @property
    def url(self) -> str:
        """
        Returns the URL
        """
        return str(self.config.url)
    

    @eproperty
    def engine(self) -> 'Engine':
        """
        Returns the engine
        """
        from sqlalchemy import create_engine
        return create_engine(
            **self.config.get_engine_kwargs(
                readonly = False,
                mode = 'sync',
            )
        )
    


    @eproperty
    def engine_su(self) -> 'Engine':
        """
        Returns the superuser engine
        """
        from sqlalchemy import create_engine
        return create_engine(
            **self.config.get_engine_kwargs(
                readonly = False,
                superuser = True,
                mode = 'sync',
            )
        )
    

    @eproperty
    def engine_ro(self) -> 'Engine':
        """
        Returns the readonly engine
        """
        from sqlalchemy import create_engine
        return create_engine(
            **self.config.get_engine_kwargs(
                readonly = True,
                mode = 'sync',
            )
        )

    @eproperty
    def aengine(self) -> 'AsyncEngine':
        """
        [Async] Returns the engine
        """
        from sqlalchemy.ext.asyncio import create_async_engine
        return create_async_engine(
            **self.config.get_engine_kwargs(
                readonly = False,
                mode = 'async',
            )
        )
    

    @eproperty
    def aengine_su(self) -> 'AsyncEngine':
        """
        [Async] Returns the superuser engine
        """
        from sqlalchemy.ext.asyncio import create_async_engine
        return create_async_engine(
            **self.config.get_engine_kwargs(
                readonly = False,
                superuser = True,
                mode = 'async',
            )
        )
    

    @eproperty
    def aengine_ro(self) -> 'AsyncEngine':
        """
        [Async] Returns the readonly engine
        """
        from sqlalchemy.ext.asyncio import create_async_engine
        return create_async_engine(
            **self.config.get_engine_kwargs(
                readonly = True,
                mode = 'async',
            )
        )

    @eproperty
    def session(self) -> 'SessionMakerT':
        """
        Returns the session
        """
        from sqlalchemy.orm import sessionmaker
        return sessionmaker(
            self.engine,
            **self.config.get_session_kwargs(
                readonly = False,
                mode = 'sync',
                backend = self.backend,
            )
        )
    
    @eproperty
    def session_ro(self) -> 'SessionMakerT':
        """
        Returns the readonly session
        """
        from sqlalchemy.orm import sessionmaker
        return sessionmaker(
            self.engine_ro,
            **self.config.get_session_kwargs(
                readonly = True,
                mode = 'sync',
                backend = self.backend,
            )
        )
    
    @eproperty
    def session_su(self) -> 'SessionMakerT':
        """
        Returns the superuser session
        """
        from sqlalchemy.orm import sessionmaker
        return sessionmaker(
            self.engine_su,
            **self.config.get_session_kwargs(
                readonly = False,
                superuser = True,
                mode = 'sync',
                backend = self.backend,
            )
        )
    
    @eproperty
    def asession(self) -> 'AsyncSessionMakerT':
        """
        [Async] Returns the session
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        return async_sessionmaker(
            self.aengine,
            **self.config.get_session_kwargs(
                readonly = False,
                mode = 'async',
                backend = self.backend,
            )
        )
    
    @eproperty
    def asession_su(self) -> 'AsyncSessionMakerT':
        """
        [Async] Returns the superuser session
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        return async_sessionmaker(
            self.aengine_su,
            **self.config.get_session_kwargs(
                readonly = False,
                superuser = True,
                mode = 'async',
                backend = self.backend,
            )
        )

    @eproperty
    def asession_ro(self) -> 'AsyncSessionMakerT':
        """
        [Async] Returns the readonly session
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        return async_sessionmaker(
            self.aengine_ro,
            **self.config.get_session_kwargs(
                readonly = True,
                mode = 'async',
                backend = self.backend,
            )
        )
    
    """
    Scoped Sessions
    """

    @eproperty
    def session_scoped(self) -> 'ScopedSessionMakerT':
        """
        Returns the Scoped Session 
        """
        from sqlalchemy.orm import scoped_session
        return scoped_session(
            self.session,
            scopefunc = self.extra_kws.get('scopefunc', None),
        )
    
    @eproperty
    def session_ro_scoped(self) -> 'ScopedSessionMakerT':
        """
        Returns the readonly Scoped Session
        """
        from sqlalchemy.orm import scoped_session
        return scoped_session(
            self.session_ro,
            scopefunc = self.extra_kws.get('scopefunc', None),
        )
        
    
    @eproperty
    def asession_scoped(self) -> 'AsyncScopedSessionMakerT':
        """
        [Async] Returns the Scoped Session
        """
        from sqlalchemy.ext.asyncio import async_scoped_session
        return async_scoped_session(
            self.asession,
            scopefunc = self.extra_kws.get('scopefunc', None),
        )
        
    
    @eproperty
    def asession_ro_scoped(self) -> 'AsyncScopedSessionMakerT':
        """
        [Async] Returns the readonly Scoped Session
        """
        from sqlalchemy.ext.asyncio import async_scoped_session
        return async_scoped_session(
            self.asession_ro,
            scopefunc = self.extra_kws.get('scopefunc', None),
        )
        

    @eproperty
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return logger
    
    @eproperty
    def autologger(self) -> 'Logger':
        """
        Returns the autologger
        """
        return logger if self.config.debug_enabled else null_logger
    

    def _get_session_type(
        self,
        readonly: t.Optional[bool] = None,
        scoped: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
    ) -> t.Tuple['SessionGetT', bool]:
        """
        Returns the session
        """
        if superuser: return (self.session_su, False)
        if scoped is None: scoped = self._default_scoped['sync']
        if readonly: return (self.session_ro_scoped, True) if scoped else (self.session_ro, False)
        return (self.session_scoped, True) if scoped else (self.session, False)
    
    def _get_async_session_type(
        self,
        readonly: t.Optional[bool] = None,
        scoped: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
    ) -> t.Tuple['AsyncSessionGetT', bool]:
        """
        Returns the session
        """
        if superuser: return (self.asession_su, False)
        if scoped is None: scoped = self._default_scoped['async']
        if readonly: return (self.asession_ro_scoped, True) if scoped else (self.asession_ro, False)
        return (self.asession_scoped, True) if scoped else (self.asession, False)


    def _get_session(
        self,
        readonly: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        mode: t.Optional[t.Literal['sync', 'async']] = 'sync',
        scoped: t.Optional[bool] = None,
    ) -> t.Tuple['SessionGetterT', bool]:
        """
        Returns the session
        """
        if mode == 'sync': return self._get_session_type(readonly = readonly, scoped = scoped, superuser = superuser)
        return self._get_async_session_type(readonly = readonly, scoped = scoped, superuser = superuser)


    """
    Direct Engine Connections
    """

    def get_engine(
        self,
        url: t.Optional[str] = None,
        readonly: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        adapter: t.Optional[str] = None,
        **kwargs,
    ) -> 'Engine':
        """
        [Sync] Creates an Engine. This is unmanaged
        """
        from sqlalchemy import create_engine
        engine_kwargs = self.config.get_engine_kwargs(
            readonly = readonly, 
            superuser = superuser, 
            url = url, 
            adapter = adapter,
            mode = 'sync',
            **kwargs
        )
        if execution_options: engine_kwargs['execution_options'] = execution_options
        return create_engine(**engine_kwargs)
    
    def get_aengine(
        self,
        url: t.Optional[str] = None,
        readonly: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        adapter: t.Optional[str] = None,
        **kwargs,
    ) -> 'AsyncEngine':
        """
        [Async] Creates an Async Engine. This is unmanaged
        """
        from sqlalchemy.ext.asyncio import create_async_engine
        engine_kwargs = self.config.get_engine_kwargs(
            readonly = readonly, 
            superuser = superuser, 
            url = url, 
            adapter = adapter,
            mode = 'async',
            **kwargs
        )
        if execution_options: engine_kwargs['execution_options'] = execution_options
        return create_async_engine(**engine_kwargs)
    
    """
    Raw Connection Methods
    """

    def _get_engine_type(
        self,
        readonly: t.Optional[bool] = None,
        mode: t.Optional[t.Literal['sync', 'async']] = 'sync',
    ) -> t.Union['Engine', 'AsyncEngine']:
        """
        Returns the session type
        """
        if mode == 'sync': return self.engine_ro if readonly else self.engine
        return self.aengine_ro if readonly else self.aengine
    

    @contextlib.contextmanager
    def connection(
        self,
        readonly: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        url: t.Optional[str] = None,
        **kwargs,
    ) -> t.Generator['Connection', None, None]:
        """
        Context Manager for the connection
        """
        if any(
            url is not None,
            execution_options is not None,
            superuser is not None,
        ):
            engine = self.get_engine(
                url = url,
                readonly = readonly,
                superuser = superuser,
                execution_options = execution_options,
                **kwargs,
            )
        else:
            engine = self._get_engine_type(readonly = readonly)
        conn: Connection = None
        try:
            conn = engine.connect()
            conn.begin()
            yield conn
        except Exception as e:
            self.logger.trace(f'[{self.name} - {self.backend}] Engine Error', e, depth = 5)
            if auto_rollback is None: auto_rollback = self.config.auto_rollback_enabled
            if auto_rollback: 
                try:
                    conn.rollback()
                    self.logger.info(f'[{self.name} - {self.backend}] Connection Rolled Back')
                except Exception as e:
                    self.logger.trace(f'[{self.name} - {self.backend}] Connection Rollback Error', e)
            if raise_errors: raise e
        finally:
            if auto_commit is None: auto_commit = self.config.autocommit_enabled
            if auto_commit: conn.commit()
            conn.close()

    @contextlib.asynccontextmanager
    async def aconnection(
        self,
        readonly: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        url: t.Optional[str] = None,
        **kwargs,
    ) -> t.AsyncGenerator['AsyncConnection', None]:
        """
        Context Manager for the connection
        """
        if any(
            url is not None,
            execution_options is not None,
            superuser is not None,
        ):
            engine = self.get_aengine(
                url = url,
                readonly = readonly,
                superuser = superuser,
                execution_options = execution_options,
                **kwargs,
            )
        else:
            engine = self._get_engine_type(readonly = readonly, mode = 'async')
        conn: AsyncConnection = None
        try:
            conn = await engine.connect()
            await conn.start()
            yield conn
        except Exception as e:
            self.logger.trace(f'[{self.name} - {self.backend}] Engine Error', e, depth = 5)
            if auto_rollback is None: auto_rollback = self.config.auto_rollback_enabled
            if auto_rollback: 
                try:
                    await conn.rollback()
                    logger.info('Connection Rolled Back')
                except Exception as e:
                    logger.trace('Connection Rollback Error', e)
            if raise_errors: raise e
        finally:
            if auto_commit is None: auto_commit = self.config.autocommit_enabled
            if auto_commit: await conn.commit()
            await conn.aclose()



    @eproperty
    def sql(self) -> 'SQLAlchemyUtilities':
        """
        Returns the SQLAlchemy Utilities
        """
        return SQLAlchemyUtilities()

    """
    Utility Methods
    """


    def dbexec(
        self, 
        sql: str,
        superuser: t.Optional[bool] = None,
        readonly: t.Optional[bool] = None,
        database: t.Optional[str] = None,
        debug_enabled: t.Optional[bool] = None,
        verbose: t.Optional[bool] = True,
        **kwargs,
    ) -> str:
        """
        Runs a Raw SQL Query through the Postgres CLI
        """
        if not sql.endswith(';'): sql += ';'
        cmd = f'{self.config.get_cli_connect_string(superuser=superuser, readonly=readonly, database=database)} -c "{sql}"'
        # if debug_enabled: cmd += ' -v ON_ERROR_STOP=1 -a -b -e -E'
        # safe_cmd = cmd.split("psql", 1)[-1]
        if debug_enabled: cmd += self.config.get_cli_debug_args()
        safe_cmd = self.config.get_cli_safe_cmd(cmd)
        if verbose: self.logger.info(f'Executing Command: {safe_cmd}', prefix = f'{self.name} - {self.backend}', colored = True)        
        import subprocess
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = ''
        for line in process.stdout:
            if isinstance(line, bytes): line = line.decode('utf-8')
            result += f'{line.strip()}\n'
        if verbose: self.logger.info(f'Result: {result}', prefix = f'{self.name} - {self.backend}', colored = True)
        return result

    async def adbexec(
        self, 
        sql: str,
        superuser: t.Optional[bool] = None,
        readonly: t.Optional[bool] = None,
        database: t.Optional[str] = None,
        debug_enabled: t.Optional[bool] = None,
        verbose: t.Optional[bool] = True,
        **kwargs,
    ) -> str:
        """
        Runs a Raw SQL Query through the Postgres CLI
        """
        if not sql.endswith(';'): sql += ';'
        cmd = f'{self.config.get_cli_connect_string(superuser=superuser, readonly=readonly, database=database)} -c "{sql}"'
        # if debug_enabled: cmd += ' -v ON_ERROR_STOP=1 -a -b -e -E'
        if debug_enabled: cmd += self.config.get_cli_debug_args()
        safe_cmd = self.config.get_cli_safe_cmd(cmd)
        # safe_cmd = cmd.split("psql", 1)[-1]
        if verbose: self.logger.info(f'Executing Command: {safe_cmd}', prefix = f'{self.name} - {self.backend}', colored = True)
        process = await self.tpool.async_run_command(cmd, output_only=False)
        result = ''
        async for line in process.stdout:
            if isinstance(line, bytes): line = line.decode('utf-8')
            result += f'{line.strip()}\n'
        if verbose: self.logger.info(f'Result: {result}', prefix = f'{self.name} - {self.backend}', colored = True)
        return result


    def wait_for_ready(
        self,
        max_attempts: t.Optional[int] = 10,
        interval: t.Optional[float] = 5.0,
    ):
        """
        Waits for the database to be ready
        """
        attempts = 0
        while attempts < max_attempts:
            try:
                with self.engine.begin() as conn:
                    conn.execute(self.sql.text('SELECT 1'))
                return
            except Exception as e:
                if attempts == 0:
                    logger.info(f'Database not ready: {attempts}/{max_attempts} attempts @ {self.config.safe_url}. Error: {e}', prefix = f'{self.name} - {self.backend}')
                else:    
                    logger.info(f'Database not ready: {attempts}/{max_attempts} attempts. Error: {e}', prefix = f'{self.name} - {self.backend}')
                attempts += 1
                time.sleep(interval)
                if attempts >= max_attempts:
                    raise e

    async def await_for_ready(
        self,
        max_attempts: t.Optional[int] = 10,
        interval: t.Optional[float] = 5.0,
    ):
        """
        Waits for the database to be ready
        """
        attempts = 0
        while attempts < max_attempts:
            try:
                async with self.aengine.begin() as conn:
                    await conn.execute(self.sql.text('SELECT 1'))
                return
            except Exception as e:
                if attempts == 0:
                    logger.info(f'Database not ready: {attempts}/{max_attempts} attempts @ {self.config.safe_url}. Error: {e}', prefix = f'{self.name} - {self.backend}')
                else:    
                    logger.info(f'Database not ready: {attempts}/{max_attempts} attempts. Error: {e}', prefix = f'{self.name} - {self.backend}')
                attempts += 1
                await asyncio.sleep(interval)
                if attempts >= max_attempts:
                    raise e
    
    def _execute_scalar(
        self,
        query: 'TextClause',
        params: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs,
    ) -> t.Any:
        """
        Executes a scalar query
        """
        with self.session() as session:
            result = session.execute(query, params = params, **kwargs)
            return result.scalar_one()
    
    async def _aexecute_scalar(
        self,
        query: 'TextClause',
        params: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs,
    ) -> t.Any:
        """
        Executes a scalar query
        """
        async with self.asession() as session:
            result = await session.execute(query, params = params, **kwargs)
            return result.scalar_one()

    def index_exists(
        self,
        index_name: str,
    ) -> bool:
        """
        Checks if the Index Exists
        """
        statement = self.sql.text(
            """
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE indexname = :index_name
            );
            """
        )
        return self._execute_scalar(statement, {'index_name': index_name})

    
    async def aindex_exists(
        self,
        index_name: str,
    ) -> bool:
        """
        Checks if the Index Exists
        """
        statement = self.sql.text(
            """
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE indexname = :index_name
            );
            """
        )
        return await self._aexecute_scalar(statement, {'index_name': index_name})


    def database_exists(
        self,
        db_name: str,
        verbose: t.Optional[bool] = True,
    ) -> bool:
        """
        Checks if the database exists
        """
        statement = self.sql.text(
            f"SELECT 1 FROM pg_database WHERE datname = '{db_name}';"
        )
        result = self._execute_scalar(statement)
        if verbose: logger.info(f'Database {db_name} Exists: {result}')
        return result
        

    async def adatabase_exists(
        self,
        db_name: str,
        verbose: t.Optional[bool] = True,
    ) -> bool:
        """
        Checks if the database exists
        """
        statement = self.sql.text(
            f"SELECT 1 FROM pg_database WHERE datname = '{db_name}';"
        )
        result = await self._aexecute_scalar(statement)
        if verbose: logger.info(f'Database {db_name} Exists: {result}')
        return result
    

    def get_table_names(
        self,
        schema: t.Optional[str] = None,
    ) -> t.List[str]:
        """
        Returns the table names
        """
        from sqlalchemy.engine.reflection import Inspector
        inspector = Inspector.from_engine(self.engine)
        return inspector.get_table_names(schema = schema)
    
    def get_table_column_size(
        self,
        table: str,
        column: str,
        schema: t.Optional[str] = None,
        verbose: t.Optional[bool] = False,
    ) -> t.Dict[str, t.Union[str, float]]:
        """
        Displays the table column size
        """
        table_name = f'{schema}.{table}' if schema else table
        with self.connection(readonly=True) as conn:
            result = conn.execute(
                self.sql.text(f'''
                select
                    pg_size_pretty(sum(pg_column_size({column}))) as total_size,
                    pg_size_pretty(avg(pg_column_size({column}))) as average_size,
                    sum(pg_column_size({column})) * 100.0 / pg_total_relation_size('{table_name}') as percentage
                from {table_name};
                '''
            ))
        row = result.fetchone()
        if verbose: self.logger.info(f'Total Size: |g|{row[0]}|e|, Avg Size: |g|{row[1]}|e|, Percentage: |y|{row[2]:.2f}%|e|', prefix = f'{table_name}.{column}', colored = True)
        else: self.autologger.info(f'Total Size: |g|{row[0]}|e|, Avg Size: |g|{row[1]}|e|, Percentage: |y|{row[2]:.2f}%|e|', prefix = f'{table_name}.{column}', colored = True)
        return {
            'total_size': row[0],
            'average_size': row[1],
            'percentage': row[2],
        }
    
    def get_table_column_names(
        self,
        table: str,
        schema: t.Optional[str] = None,
    ) -> t.List[str]:
        """
        Returns the table column names
        """
        table_name = f'{schema}.{table}' if schema else table
        with self.connection(readonly=True) as conn:
            result = conn.execute(
                self.sql.text(f'''
                select column_name
                from information_schema.columns
                where table_name = '{table_name}';
                '''
            ))
        return [row[0] for row in result.fetchall()]


    def upgrade_extensions(
        self,
        extensions: t.Optional[t.List[str]] = None,
        verbose: t.Optional[bool] = True,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        """
        Upgrade the extensions
        """
        if not extensions: return
        results = {}
        with self.engine.begin() as conn:
            for ext in extensions:
                conn.execute(self.sql.text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
                conn.commit()
                conn.execute(self.sql.text(f"ALTER EXTENSION {ext} UPDATE"))
                conn.commit()

                # Get the version
                result = conn.execute(self.sql.text(f"SELECT * FROM pg_extension WHERE extname = '{ext}'"))
                version = result.scalar()
                results[ext] = version
                if verbose: self.logger.info(f"Extension {ext} version: {version}")
                else: self.autologger.info(f"Extension {ext} version: {version}")
        return results


    async def aupgrade_extensions(
        self,
        extensions: t.Optional[t.List[str]] = None,
        verbose: t.Optional[bool] = True,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        """
        Upgrade the extensions
        """
        if not extensions: return
        results = {}
        async with self.aengine.begin() as conn:
            for ext in extensions:
                await conn.execute(self.sql.text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
                await conn.commit()
                await conn.execute(self.sql.text(f"ALTER EXTENSION {ext} UPDATE"))
                await conn.commit()

                # Get the version
                result = await conn.execute(self.sql.text(f"SELECT * FROM pg_extension WHERE extname = '{ext}'"))
                version = await result.scalar()
                results[ext] = version
                if verbose: self.logger.info(f"Extension {ext} version: {version}")
                else: self.autologger.info(f"Extension {ext} version: {version}")
        return results



BackendClassT = t.TypeVar('BackendClassT', bound = BaseDatabaseBackend)
