from __future__ import annotations

"""
A Generic Postgres SQL Database Client

This module provides an abstract base class for a generic Postgres SQL database client.

Requires `sqlalchemy` and `psycopg2` to be installed.
"""

import abc
import asyncio
import datetime
import contextlib
from pathlib import Path
from pydantic.networks import PostgresDsn
from pydantic_settings import BaseSettings
from pydantic import validator, model_validator, computed_field, BaseModel, Field

from sqlalchemy import text as sql_text, TextClause
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from lazyops.utils.logs import logger, Logger
from lazyops.utils.lazy import lazy_import
from ...utils.helpers import update_dict
from typing import Any, Dict, List, Optional, Type, Literal, Iterable, Tuple, TypeVar, Union, Annotated, Callable, Generator, AsyncGenerator, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.engine import Result
    from lazyops.libs.pooler import ThreadPool
    from lazyops.libs.abcs.configs.base import AppSettings
    from .templates import SQLTemplates
    from .types import ModelType


class PostgresConfig(BaseModel):

    """
    The Postgres Settings
    """
    url: Optional[PostgresDsn] = None
    readonly_url: Optional[PostgresDsn] = None
    superuser_url: Optional[PostgresDsn] = None

    engine_poolclass: Optional[Union[Type[Union[NullPool, AsyncAdaptedQueuePool]], str]] = 'sqlalchemy.pool.AsyncAdaptedQueuePool'
    engine_json_serializer: Optional[Union[Type[Callable], str]] = 'json'

    engine_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)
    engine_rw_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)
    engine_ro_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)

    session_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)
    session_ro_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)
    session_rw_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)

    @computed_field
    @property
    def url_password(self) -> Optional[str]:
        """
        The Password
        """
        if ':' in str(self.url) and '@' in str(self.url):
            return str(self.url).split('@')[0].split(':')[-1]
        return None

    @computed_field
    @property
    def superuser_url_password(self) -> Optional[str]:
        """
        The Password
        """
        if not self.superuser_url: return None
        if ':' in str(self.superuser_url) and '@' in str(self.superuser_url):
            return str(self.superuser_url).split('@')[0].split(':')[-1]
        return None
    
    @computed_field
    @property
    def safe_url(self) -> Optional[str]:
        """
        The Password
        """
        if not self.url: return None
        return str(self.url).replace(self.url_password, '********') if self.url_password else str(self.url)
    
    @computed_field
    @property
    def safe_superuser_url(self) -> Optional[str]:
        """
        The Password
        """
        if not self.superuser_url: return None
        return str(self.superuser_url).replace(self.superuser_url_password, '********') if self.superuser_url_password else str(self.superuser_url)
    

    def log_db_url(self, verbose: Optional[bool] = False):
        """
        Log the Database URL
        """
        if not verbose: return
        logger.info(f'Using URL: |g|{self.safe_url}|e|', colored = True, prefix = 'PostgresDB')

    def log_readonly_warning(self, verbose: Optional[bool] = False):
        """
        Log the Readonly Warning
        """
        if not verbose: return
        if not self.readonly_url:
            safe_url = self.safe_url
            logger.info(f'|y|Readonly URL not set|e|, using default URL: {safe_url}', colored = True, prefix = 'PostgresDB')


    @model_validator(mode = 'after')
    def post_init_validate(self):
        """
        Validate after init
        """
        if not self.superuser_url: self.superuser_url = self.url
        if isinstance(self.engine_poolclass, str):
            self.engine_poolclass = lazy_import(self.engine_poolclass)
        if isinstance(self.engine_json_serializer, str):
            if self.engine_json_serializer == 'json':
                try:
                    from kvdb.io.serializers import get_serializer
                    serializer = get_serializer('json')
                    self.engine_json_serializer = serializer.dumps
                except ImportError:
                    from lazyops.utils.serialization import Json
                    self.engine_json_serializer = Json.dumps
            else:
                try:
                    self.engine_json_serializer = lazy_import(self.engine_json_serializer)
                except Exception as e:
                    logger.error(f'Failed to import the JSON Serializer: {e}')
        if not self.engine_kwargs:
            self.engine_kwargs['pool_pre_ping'] = True
        if not self.session_rw_kwargs:
            self.session_rw_kwargs['expire_on_commit'] = False
        if not self.session_ro_kwargs:
            self.session_ro_kwargs['autoflush'] = False
            self.session_ro_kwargs['autocommit'] = False
        return self
    
    @classmethod
    def from_settings(cls, settings: 'BaseSettings') -> 'PostgresConfig':
        """
        Create from Settings
        """
        return cls.model_validate(settings, from_attributes = True)
    

    def get_engine_kwargs(self, readonly: Optional[bool] = False, verbose: Optional[bool] = False, **engine_kwargs) -> Dict[str, Any]:
        """
        Get the Engine KWargs
        """
        kwargs = self.engine_kwargs or {}
        if engine_kwargs: kwargs = update_dict(kwargs, engine_kwargs)
        kwargs = (
            update_dict(kwargs, self.engine_ro_kwargs)
            if readonly
            else update_dict(kwargs, self.engine_rw_kwargs)
        )
        self.log_readonly_warning(verbose) if readonly else self.log_db_url(verbose)
        kwargs['url'] = str((self.readonly_url or self.url) if readonly else self.url)
        if self.engine_json_serializer:
            kwargs['json_serializer'] = self.engine_json_serializer
        if self.engine_poolclass:
            kwargs['poolclass'] = self.engine_poolclass
        return kwargs
    
    def get_session_kwargs(self, readonly: Optional[bool] = False, **session_kwargs) -> Dict[str, Any]:
        """
        Get the Session KWargs
        """
        kwargs = self.session_kwargs or {}
        if session_kwargs: kwargs = update_dict(kwargs, session_kwargs)
        kwargs = (
            update_dict(kwargs, self.session_ro_kwargs)
            if readonly
            else update_dict(kwargs, self.session_rw_kwargs)
        )
        return kwargs
    

    model_config = {'extra': 'allow', 'arbitrary_types_allowed': True}


class DatabaseClientBase(abc.ABC):

    name: Optional[str] = 'database'
    

    def __init__(
        self, 
        settings: Optional[BaseSettings] = None,
        config: Optional[PostgresConfig] = None,
        **kwargs
    ):
        """
        Initializes the Database Client
        """
        # assert settings or config, 'Either settings or config must be provided'
        self.config: Optional[PostgresConfig] = None
        self._engine_rw: Optional[AsyncEngine] = None
        self._engine_ro: Optional[AsyncEngine] = None
        self._session_rw: Optional[async_sessionmaker[AsyncSession]] = None
        self._session_ro: Optional[async_sessionmaker[AsyncSession]] = None

        self._on_failure_callbacks: List[Callable] = []
        self._settings: Optional['AppSettings'] = None
        self._tpool: Optional['ThreadPool'] = None
        self._sql_template: Optional['SQLTemplates'] = None
        self._sql_template_kwargs: Optional[Dict[str, Any]] = {}

        self.pre_init(**kwargs)
        if settings: self.config = PostgresConfig.from_settings(settings)
        elif config: self.config = config
        self.post_init(**kwargs)
        self._kwargs = kwargs

    def configure(
        self, 
        settings: Optional['AppSettings'] = None, 
        config: Optional[PostgresConfig] = None, 

        # Template Config
        template_name: Optional[str] = None,
        template_base_path: Optional[Union[str, Path]] = None,
        template_file_suffix: Optional[str] = None,
        **kwargs
    ):
        """
        Configures the Database Client
        """
        if settings:
            if hasattr(settings, 'ctx'):
                self._settings = settings
            if hasattr(settings, 'db'):
                if hasattr(settings.db, 'postgres'):
                    self.config = PostgresConfig.from_settings(settings.db.postgres)
                elif hasattr(settings.db, 'url'):
                    self.config = PostgresConfig.from_settings(settings.db)
            elif hasattr(settings, 'postgres'):
                self.config = PostgresConfig.from_settings(settings.postgres)
            
        # if settings: self.config = PostgresConfig.from_settings(settings)
        elif config: self.config = config

        if template_name: self._sql_template_kwargs['name'] = template_name
        if template_base_path: self._sql_template_kwargs['base_path'] = template_base_path
        if template_file_suffix: self._sql_template_kwargs['file_suffix'] = template_file_suffix
        if kwargs: self._kwargs = update_dict(self._kwargs, kwargs)

    def pre_init(self, **kwargs):
        """
        Pre-Init
        """
        pass

    def post_init(self, **kwargs):
        """
        Post-Init
        """
        pass

    @property
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return self.settings.logger
            
    @property
    def autologger(self) -> 'Logger':
        """
        Returns the autologger
        """
        return self.settings.autologger

    @property
    def tpool(self) -> 'ThreadPool':
        """
        Returns the ThreadPool
        """
        if not self._tpool:
            from lazyops.libs.pooler import ThreadPooler
            self._tpool = ThreadPooler
        return self._tpool
    
    @property
    def sql_template(self) -> 'SQLTemplates':
        """
        Returns the SQL Templates
        """
        if not self._sql:
            from .templates import SQLTemplates
            self._sql = SQLTemplates(
                settings = self.settings,
                **self._sql_template_kwargs
            )
        return self._sql

    @property
    def settings(self) -> 'AppSettings':
        """
        Returns the settings
        """
        # assert self._settings, 'The settings must be set'
        if self._settings is None:
            from lazyops.libs.abcs.configs.lazy import get_module_settings
            self._settings = get_module_settings(self.__module__.__name__)
        return self._settings

    def is_verbose_for(self, method: str) -> bool:
        """
        Returns if the method is verbose
        """
        if self.settings:
            return not self.settings.ctx.temp_data.has_logged(method)
        return True
    
    @property
    def engine(self) -> AsyncEngine:
        """
        Returns the engine
        """
        if self._engine_rw is None:
            assert self.config, 'The config must be set'
            self._engine_rw = create_async_engine(
                **self.config.get_engine_kwargs(
                    readonly = False, 
                    verbose = self.is_verbose_for('postgres_url'),
                    **self._kwargs
                )
            )
        return self._engine_rw
    
    @property
    def engine_ro(self) -> AsyncEngine:
        """
        Returns the readonly engine
        """
        if self._engine_ro is None:
            assert self.config, 'The config must be set'
            self._engine_ro = create_async_engine(
                **self.config.get_engine_kwargs(
                    readonly = True, 
                    verbose = self.is_verbose_for('postgres_readonly_warning'),
                    **self._kwargs
                )
            )
        return self._engine_ro
    
    @property
    def session_rw(self) -> async_sessionmaker[AsyncSession]:
        """
        Returns the session
        """
        if self._session_rw is None:
            assert self.config, 'The config must be set'
            self._session_rw = async_sessionmaker(
                self.engine, 
                class_ = AsyncSession, 
                **self.config.get_session_kwargs(
                    readonly = False, 
                    verbose = self.is_verbose_for('postgres_url'),
                    **self._kwargs
                )
            )
        return self._session_rw

    @property
    def session_ro(self) -> async_sessionmaker[AsyncSession]:
        """
        Returns the readonly session
        """
        if self._session_ro is None:
            assert self.config, 'The config must be set'
            self._session_ro = async_sessionmaker(
                self.engine_ro, class_ = AsyncSession, **self.config.get_session_kwargs(
                    readonly = True, 
                    verbose = self.is_verbose_for('postgres_readonly_warning'),
                    **self._kwargs
                )
            )
        return self._session_ro
    
    def run_error_callbacks(self, e: Exception):
        """
        Runs the error callbacks
        """
        import traceback
        tb = traceback.format_exc()
        for cb in self._on_failure_callbacks:
            self.tpool.create_background_task(cb, error = e, message = tb)
    

    async def get_db(self, readonly: Optional[bool] = None) -> AsyncGenerator[AsyncSession, None]:
        """
        Returns the database session
        """
        sess_type = self.session_ro if readonly else self.session_rw
        try:
            sess = sess_type()
            yield sess
        except Exception as e:
            logger.trace('Session error', e, depth=2)
            self.run_error_callbacks(e)
        finally:
            await sess.close()


    def get_database(
        self, 
        readonly: Optional[bool] = None,
        auto_commit: Optional[bool] = None,
        raise_errors: Optional[bool] = None,
    ) -> Callable[..., AsyncSession]:
        """
        Creates an inner dependency wrapper for the database session [FastAPI]
        """
        async def inner() -> AsyncGenerator[AsyncSession, None]:
            """
            Returns the database session
            """
            sess_type = self.session_ro if readonly else self.session_rw
            try:
                sess = sess_type()
                yield sess
            except Exception as e:
                logger.trace('Session error', e, depth=2)
                self.run_error_callbacks(e)
                if raise_errors: raise e
            finally:
                if auto_commit: await sess.commit()
                await sess.close()

        return inner
    

    @contextlib.asynccontextmanager
    async def session(
        self, 
        readonly: Optional[bool] = None,
        auto_commit: Optional[bool] = None,
        raise_errors: Optional[bool] = None,
        auto_rollback: Optional[bool] = True,
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for the database session
        """
        sess_type = self.session_ro if readonly else self.session_rw
        sess: AsyncSession = None
        try:
            sess: AsyncSession = sess_type()
            yield sess
        except Exception as e:
            logger.trace('Session error', e, depth = 2)
            self.run_error_callbacks(e)
            if auto_rollback: 
                try:
                    await sess.rollback()
                    logger.info('Rolled back session')
                except Exception as e:
                    logger.trace('Rollback error', e)
            if raise_errors: raise e
        finally:
            if auto_commit: await sess.commit()
            await sess.close()

    @contextlib.asynccontextmanager
    async def session_readonly(
        self,
        raise_errors: Optional[bool] = None,
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for the database session
        """
        try:
            sess = self.session_ro()
            yield sess
        except Exception as e:
            logger.trace('Session error', e, depth = 2)
            self.run_error_callbacks(e)
            if raise_errors: raise e
        finally:
            await sess.close()


    @staticmethod
    def text(sql: str) -> TextClause:
        """
        Returns the text
        """
        return sql_text(sql)
    
    """
    Utility Methods
    """

    async def wait_for_ready(
        self,
        max_attempts: Optional[int] = 10,
        interval: Optional[float] = 5.0,
    ):
        """
        Waits for the database to be ready
        """
        attempts = 0
        while attempts < max_attempts:
            try:
                async with self.engine.begin() as conn:
                    await conn.execute(self.text('SELECT 1'))
                return
            except Exception as e:
                logger.info(f'Database not ready: {attempts}/{max_attempts} attempts. Error: {e}')
                attempts += 1
                await asyncio.sleep(interval)
                if attempts >= max_attempts:
                    raise e
        

    async def cast_result_to_object(
        self,
        result: 'Result',
        obj: 'DeclarativeBase',
        fields: Optional[List[str]],
        **kwargs,
    ) -> List['ModelType']:
        """
        Casts the result to the object
        """
        fields = fields or obj.__table__.columns.keys()
        return [obj(**dict(zip(fields, i))) for i in result.all()]
    
    async def bulk_commit_and_refresh(
        self,
        db: AsyncSession, 
        orm_objects: List['ModelType'],
        **kwargs,
    ) -> List['ModelType']:
        """
        Runs a bulk commit and refresh
        """
        await db.commit()
        for orm_object in orm_objects:
            await db.refresh(orm_object)
        return orm_objects
    

    async def upgrade_extensions(
        self,
        extensions: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Upgrade the extensions
        """
        if not extensions: return
        async with self.engine.begin() as conn:
            for ext in extensions:
                await conn.execute(self.text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
                await conn.commit()
                await conn.execute(self.text(f"ALTER EXTENSION {ext} UPDATE"))
                await conn.commit()

                # Get the version
                result = await conn.execute(self.text(f"SELECT * FROM pg_extension WHERE extname = '{ext}'"))
                version = await result.scalar()
                logger.info(f"Extension {ext} version: {version}")

    
    def build_sql_filter_query(
        self,
        **filters: Dict[str, Union[int, float, datetime.datetime, Dict, List, Any]]
    ) -> List[str]: 
        """
        Constructs the WHERE clause of a SQL query

        - This is a generic method that can be used to build the WHERE clause of a SQL query
        """
        raise NotImplementedError
    

    def build_sql_filter(
        self,
        conditional: Optional[str] = 'AND',
        **filters: Dict[str, Union[int, float, datetime.datetime, Dict, List, Any]]
    ) -> Dict[str, Union[List[str], str]]:
        """
        Returns 
        {
            "conditional": "AND",
            "statements": [
                "statement1",
                "statement2",
                "statement3",
            ]
        }
        which is properly formatted for the template
        """
        return {
            "conditional": conditional,
            "statements": self.build_sql_filter_query(**filters),
        }
    
    

    def build_sql_filters(
        self,
        and_filters: Optional[Dict[str, Union[int, float, datetime.datetime, Dict, List, Any]]] = None,
        or_filters: Optional[Dict[str, Union[int, float, datetime.datetime, Dict, List, Any]]] = None,
    ) -> List[Dict[str, Union[List[str], str]]]:
        """
        Creates the proper SQL filters
        [
            {
                "conditional": "AND",
                "statements": [
                    "statement1",
                    "statement2",
                    "statement3",
                ]
            },
            {
                "conditional": "OR",
                "statements": [
                    "statement4",
                    "statement5",
                    "statement6",
                ]
            }
        ]
        which is properly formatted for the template
        """
        filters = []
        if and_filters:
            filters.append(self.build_sql_filter(conditional = "AND", **and_filters))
        if or_filters:
            filters.append(self.build_sql_filter(conditional = 'OR', **or_filters))
        return filters
    

    async def execute_sql(
        self,
        *ops: str,
        db: Optional[AsyncSession] = None,
        readonly: Optional[bool] = None,
        auto_commit: Optional[bool] = None,
        raise_errors: Optional[bool] = None,
        verbose: Optional[bool] = None,
        filters: Optional[Dict[str, Union[int, float, datetime.datetime, Dict, List, Any]]] = None,
        **kwargs: Any,
    ) -> 'Result':
        """
        Executes a SQL query from a template
        """

        filters = self.build_sql_filters(and_filters=filters) if filters else None
        sql_query = await self.sql_template.arender(*ops, filters = filters, **kwargs)
        if verbose: logger.info(sql_query, prefix = 'Executing SQL Query')
        if db is not None: return await db.execute(self.text(sql_query))
        async with self.session(readonly = readonly, auto_commit = auto_commit, raise_errors = raise_errors) as db:
            return await db.execute(self.text(sql_query))

    
    async def index_exists(
        self,
        index_name: str,
    ) -> bool:
        """
        Checks if the Index Exists
        """
        statement = self.text(
            """
            SELECT EXISTS (
                SELECT FROM pg_indexes
                WHERE indexname = :index_name
            );
            """
        )
        async with self.session() as session:
            result = await session.execute(statement, {'index_name': index_name})
            return result.scalar_one()