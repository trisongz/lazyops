from __future__ import annotations

"""
A Generic Postgres SQL Database Client

This module provides an abstract base class for a generic Postgres SQL database client.

Requires `sqlalchemy` and `psycopg2` to be installed.
"""
import gc
import abc
import copy
import asyncio
import datetime
import contextlib
from pathlib import Path
from pydantic.networks import PostgresDsn
from pydantic_settings import BaseSettings
from pydantic import validator, model_validator, computed_field, BaseModel, Field, PrivateAttr
from sqlalchemy import create_engine, Connection, Engine
from sqlalchemy import text as sql_text, TextClause
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, async_scoped_session
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, AsyncConnection

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


_default_pool_classes: Dict[str, str] = {
    'default': 'sqlalchemy.pool.AsyncAdaptedQueuePool',
    'pooled': 'sqlalchemy.pool.NullPool',
}

class PostgresConfig(BaseModel):

    """
    The Postgres Settings
    """
    url: Optional[PostgresDsn] = None
    readonly_url: Optional[PostgresDsn] = None
    superuser_url: Optional[PostgresDsn] = None

    engine_poolclass: Optional[Union[Type[Union[NullPool, AsyncAdaptedQueuePool]], str]] = None
    engine_json_serializer: Optional[Union[Callable, str]] = 'json'
    engine_json_deserializer: Optional[Union[Callable, str]] = 'json'

    engine_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)
    engine_rw_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)
    engine_ro_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)

    session_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)
    session_ro_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)
    session_rw_kwargs: Optional[Dict[str, Any]] = Field(default_factory = dict)

    scoped_sessions_enabled: Optional[bool] = None

    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

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
    
    @property
    def has_diff_readonly_url(self) -> bool:
        """
        Checks if the url is different
        """
        if 'diff_readonly_url' not in self._extra: 
            self._extra['diff_readonly_url'] = self.readonly_url and str(self.url) != str(self.readonly_url)
        return self._extra['diff_readonly_url']

    @property
    def has_pooler_in_url(self) -> bool:
        """
        Checks if the url has a pooler in it
        """
        if 'has_pooler_in_url' not in self._extra: 
            self._extra['has_pooler_in_url'] = 'pooler' in str(self.url)
        return self._extra['has_pooler_in_url']
    
    @property
    def in_cluster(self) -> bool:
        """
        Checks if the url is in a cluster
        """
        if 'in_cluster' not in self._extra: 
            self._extra['in_cluster'] = 'svc.cluster.local' in str(self.url)
        return self._extra['in_cluster']


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

    def configure_engine_serializers(
        self,
        engine_json_serializer: Optional[Union[Callable, str]] = None,
        engine_json_deserializer: Optional[Union[Callable, str]] = None,
    ):
        """
        Configures the engine serializers
        """
        valid_ser, valid_deser = True, True
        if engine_json_serializer is not None:
            if isinstance(engine_json_serializer, str) and engine_json_serializer == 'json':
                try:
                    from kvdb.io.serializers import get_serializer
                    serializer = get_serializer('json')
                    serializer.ensure_string_value = True
                    engine_json_serializer = serializer.dumps
                    if engine_json_deserializer is None or engine_json_deserializer == 'json':
                        engine_json_deserializer = serializer.loads
                except ImportError:
                    from lazyops.utils.serialization import Json
                    engine_json_serializer = Json.dumps
                    if engine_json_deserializer is None or engine_json_deserializer == 'json':
                        engine_json_deserializer = Json.loads
            else:
                try:
                    engine_json_serializer = lazy_import(engine_json_serializer)
                    if not callable(engine_json_serializer) and hasattr(engine_json_serializer, 'dumps'):
                        engine_json_serializer = getattr(engine_json_serializer, 'dumps')
                except Exception as e:
                    valid_ser = False
                    logger.error(f'Failed to import the JSON Serializer: {e}')
        
        if engine_json_deserializer is not None and isinstance(engine_json_deserializer, str):
            if engine_json_deserializer == 'json':
                try:
                    from kvdb.io.serializers import get_serializer
                    serializer = get_serializer('json')
                    serializer.ensure_string_value = True
                    engine_json_deserializer = serializer.loads
                except ImportError:
                    from lazyops.utils.serialization import Json
                    engine_json_deserializer = Json.loads
            else:
                try:
                    engine_json_deserializer = lazy_import(engine_json_deserializer)
                    if not callable(engine_json_deserializer) and hasattr(engine_json_deserializer, 'loads'):
                        engine_json_deserializer = getattr(engine_json_deserializer, 'loads')
                except Exception as e:
                    logger.error(f'Failed to import the JSON Deserializer: {e}')
                    valid_deser = False
        
        if valid_ser: self.engine_json_serializer = engine_json_serializer
        if valid_deser: self.engine_json_deserializer = engine_json_deserializer
    

    @model_validator(mode = 'after')
    def post_init_validate(self):
        """
        Validate after init
        """
        if not self.superuser_url: self.superuser_url = self.url
        if self.engine_poolclass is None:
            self.engine_poolclass = _default_pool_classes['pooled'] if \
                self.has_pooler_in_url else _default_pool_classes['default']
        if isinstance(self.engine_poolclass, str):
            if self.engine_poolclass in _default_pool_classes:
                self.engine_poolclass = _default_pool_classes[self.engine_poolclass]
            self.engine_poolclass = lazy_import(self.engine_poolclass)
        self.configure_engine_serializers(
            engine_json_serializer = self.engine_json_serializer,
            engine_json_deserializer = self.engine_json_deserializer,
        )
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
    

    def get_engine_kwargs(
        self, 
        readonly: Optional[bool] = False, 
        verbose: Optional[bool] = False, 
        superuser: Optional[bool] = None,
        driver: Optional[str] = None,
        **engine_kwargs
    ) -> Dict[str, Any]:
        """
        Get the Engine KWargs
        """
        kwargs = copy.deepcopy(self.engine_kwargs) if self.engine_kwargs else {}
        if engine_kwargs: kwargs = update_dict(kwargs, engine_kwargs)
        kwargs = (
            update_dict(kwargs, self.engine_ro_kwargs)
            if readonly
            else update_dict(kwargs, self.engine_rw_kwargs)
        )
        self.log_readonly_warning(verbose) if readonly else self.log_db_url(verbose)
        if not kwargs.get('url'):
            if superuser and self.superuser_url:
                kwargs['url'] = str(self.superuser_url)
            else:
                kwargs['url'] = str((self.readonly_url or self.url) if readonly else self.url)
        if driver is not None and driver not in kwargs['url']:
            kwargs['url'] = f'postgresql+{driver}://' + kwargs['url'].split('://', 1)[-1]
        if self.engine_json_serializer and 'json_serializer' not in kwargs:
            kwargs['json_serializer'] = self.engine_json_serializer
        if self.engine_json_deserializer and 'json_deserializer' not in kwargs:
            kwargs['json_deserializer'] = self.engine_json_deserializer
        if self.engine_poolclass and 'poolclass' not in kwargs:
            kwargs['poolclass'] = self.engine_poolclass
        # logger.info(kwargs, prefix = 'Engine KWargs')
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
        # logger.info(kwargs, prefix = 'Session KWargs')
        return kwargs
    

    model_config = {'extra': 'allow', 'arbitrary_types_allowed': True}


class RemoteDatabaseConnection(PostgresConfig):
    """
    Remote Database
    """

    name: str
    extra_kws: Optional[Dict[str, Any]] = Field(default_factory = dict)
    _engine_rw: Optional[AsyncEngine] = PrivateAttr(None)
    _engine_ro: Optional[AsyncEngine] = PrivateAttr(None)
    _session_rw: Optional[async_sessionmaker[AsyncSession]] = PrivateAttr(None)
    _session_ro: Optional[async_sessionmaker[AsyncSession]] = PrivateAttr(None)

    @property
    def engine(self) -> AsyncEngine:
        """
        Returns the engine
        """
        if self._engine_rw is None:
            self._engine_rw = create_async_engine(**self.get_engine_kwargs(readonly = False, **self.extra_kws))
        return self._engine_rw
    
    @property
    def engine_ro(self) -> AsyncEngine:
        """
        Returns the readonly engine
        """
        if self._engine_ro is None:
            self._engine_ro = create_async_engine(**self.get_engine_kwargs(readonly = True, **self.extra_kws))
        return self._engine_ro
    
    @property
    def session_rw(self) -> async_sessionmaker[AsyncSession]:
        """
        Returns the session
        """
        if self._session_rw is None:
            self._session_rw = async_sessionmaker(
                self.engine, 
                class_ = AsyncSession, 
                **self.get_session_kwargs(readonly = False, **self.extra_kws)
            )
        return self._session_rw

    @property
    def session_ro(self) -> async_sessionmaker[AsyncSession]:
        """
        Returns the readonly session
        """
        if self._session_ro is None:
            self._session_ro = async_sessionmaker(
                self.engine_ro, class_ = AsyncSession, **self.get_session_kwargs(readonly = True, **self.extra_kws)
            )
        return self._session_ro



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
        self._session_scoped_rw: Optional[async_scoped_session[AsyncSession]] = None
        self._session_scoped_ro: Optional[async_scoped_session[AsyncSession]] = None

        self._on_failure_callbacks: List[Callable] = []
        self._settings: Optional['AppSettings'] = None
        self._tpool: Optional['ThreadPool'] = None
        self._sql_template: Optional['SQLTemplates'] = None
        self._sql_template_kwargs: Optional[Dict[str, Any]] = {}

        # Remote Configs to Connect
        self.remote_connections: Dict[str, RemoteDatabaseConnection] = {}

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

    def configure_remote(
        self,
        url: str,
        name: str,
        readonly_url: Optional[str] = None,
        superuser_url: Optional[str] = None,
        overwrite: Optional[bool] = None,
        **kwargs
    ):
        """
        Configures the remote database
        """
        if name in self.remote_connections and not overwrite: raise ValueError(f'Remote Connection {name} already exists')
        _config = {
            'name': name,
            'url': url,
            'readonly_url': readonly_url,
            'superuser_url': superuser_url,
        }
        _config = {k:v for k, v in _config.items() if v is not None}
        _config['extra_kws'] = kwargs
        self.remote_connections[name] = RemoteDatabaseConnection.model_validate(_config)

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
    
    def configure_sql_templates(self, **kwargs):
        """
        Configures the SQL Templates
        """
        pass


    @property
    def sql_template(self) -> 'SQLTemplates':
        """
        Returns the SQL Templates
        """
        if not self._sql_template:
            from .templates import SQLTemplates
            self.configure_sql_templates()
            self._sql_template = SQLTemplates(
                settings = self.settings,
                **self._sql_template_kwargs
            )
        return self._sql_template

    @property
    def settings(self) -> 'AppSettings':
        """
        Returns the settings
        """
        # assert self._settings, 'The settings must be set'
        if self._settings is None:
            from lazyops.libs.abcs.configs.lazy import get_module_settings
            self._settings = get_module_settings(self.__module__)
        return self._settings

    def is_verbose_for(self, method: str) -> bool:
        """
        Returns if the method is verbose
        """
        if self.settings:
            return not self.settings.ctx.temp_data.has_logged(method)
        return True
    
    @property
    def default_scoped_session(self) -> Optional[bool]:
        """
        Checks if the default scoped sessions are enabled
        """
        return self.config.scoped_sessions_enabled

    def set_default_scoped_session(self, enabled: bool):
        """
        Sets the default scoped session
        """
        self.config.scoped_sessions_enabled = enabled
    
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
                    # verbose = self.is_verbose_for('postgres_url'),
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
                    # verbose = self.is_verbose_for('postgres_readonly_warning'),
                    **self._kwargs
                )
            )
        return self._session_ro

    @property
    def session_scoped_rw(self) -> async_scoped_session[AsyncSession]:
        """
        Returns the scoped session
        """
        if self._session_scoped_rw is None:
            self._session_scoped_rw = async_scoped_session(
                self.session_rw, 
                scopefunc = self._kwargs.get('scopefunc', asyncio.current_task),
            )
        return self._session_scoped_rw

    @property
    def session_scoped_ro(self) -> async_scoped_session[AsyncSession]:
        """
        Returns the scoped session
        """
        if self._session_scoped_ro is None:
            self._session_scoped_ro = async_scoped_session(
                self.session_ro, 
                scopefunc = self._kwargs.get('scopefunc', asyncio.current_task),
            )
        return self._session_scoped_ro
    
    def _get_session_type(
        self,
        readonly: Optional[bool] = None,
        scoped: Optional[bool] = None,
    ) -> Union[async_sessionmaker[AsyncSession], async_scoped_session[AsyncSession]]:
        """
        Returns the session type
        """
        if scoped is None: scoped = self.default_scoped_session
        # if scoped is not None: return self.session_scoped_rw if scoped else self.session_scoped_ro
        if readonly: return self.session_scoped_ro if scoped else self.session_ro
        return self.session_scoped_rw if scoped else self.session_rw
    
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
        scoped: Optional[bool] = None,
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for the database session
        """
        # sess_type = self.session_ro if readonly else self.session_rw
        if scoped is None: scoped = self.default_scoped_session
        sess_type = self._get_session_type(readonly = readonly, scoped = scoped)
        sess: AsyncSession = None
        try:
            sess: AsyncSession = sess_type()
            yield sess
        except Exception as e:
            logger.trace('Session error', e, depth = 5)
            self.run_error_callbacks(e)
            if auto_rollback: 
                try:
                    await sess.rollback()
                    logger.info('session Rolled Back ')
                except Exception as e:
                    logger.trace('Session Rollback Error', e)
            if raise_errors: raise e
        finally:
            if auto_commit:
                if scoped: await sess_type.commit()
                else: await sess.commit()
            if scoped: 
                sess_type.expire_all()
                await sess_type.close()
                await sess_type.remove()
            else:
                await sess.close()
            # if readonly: gc.collect()

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
            # gc.collect()


    @contextlib.asynccontextmanager
    async def remote_session(
        self, 
        name: str,
        readonly: Optional[bool] = None,
        auto_commit: Optional[bool] = None,
        raise_errors: Optional[bool] = None,
        auto_rollback: Optional[bool] = True,
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for the remote database session
        """
        if name not in self.remote_connections: raise ValueError(f'Remote Connection {name} does not exist')
        remote_conn = self.remote_connections[name]
        sess_type = remote_conn.session_ro if readonly else remote_conn.session_rw
        sess: AsyncSession = None
        try:
            sess: AsyncSession = sess_type()
            yield sess
        except Exception as e:
            logger.trace('Session error', e, depth = 5)
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
            # if readonly: gc.collect()

    """
    Direct Engine Connections
    """

    def get_engine(
        self,
        url: Optional[str] = None,
        readonly: Optional[bool] = None,
        superuser: Optional[bool] = None,
        execution_options: Optional[Dict[str, Any]] = None,
        driver: Optional[str] = 'psycopg2',
        **kwargs,
    ) -> Engine:
        """
        Creates an Engine. This is unmanaged
        """
        engine_kwargs = self.config.get_engine_kwargs(readonly = readonly, superuser = superuser, url = url, driver = driver, **kwargs)
        if execution_options: engine_kwargs['execution_options'] = execution_options
        return create_engine(**engine_kwargs)
    
    def get_aengine(
        self,
        url: Optional[str] = None,
        readonly: Optional[bool] = None,
        superuser: Optional[bool] = None,
        execution_options: Optional[Dict[str, Any]] = None,
        driver: Optional[str] = 'asyncpg',
        **kwargs,
    ) -> AsyncEngine:
        """
        Creates an Async Engine. This is unmanaged
        """
        engine_kwargs = self.config.get_engine_kwargs(readonly = readonly, superuser = superuser, url = url, driver = driver,**kwargs)
        if execution_options: engine_kwargs['execution_options'] = execution_options
        return create_async_engine(**engine_kwargs)
    

    def _get_engine_type(
        self,
        readonly: Optional[bool] = None,
    ) -> AsyncEngine:
        """
        Returns the session type
        """
        return self.engine_ro if readonly else self.engine
    
    @contextlib.asynccontextmanager
    async def connection(
        self,
        readonly: Optional[bool] = None,
        raise_errors: Optional[bool] = None,
        auto_rollback: Optional[bool] = True,
        auto_commit: Optional[bool] = None,
        superuser: Optional[bool] = None,
        execution_options: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[AsyncConnection, None]:
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
            engine = self._get_engine_type(readonly = readonly)
        conn: AsyncConnection = None
        try:
            conn = await engine.connect()
            await conn.start()
            yield conn
        except Exception as e:
            logger.trace('Engine error', e, depth = 5)
            self.run_error_callbacks(e)
            if auto_rollback: 
                try:
                    await conn.rollback()
                    logger.info('Connection Rolled Back')
                except Exception as e:
                    logger.trace('Connection Rollback Error', e)
            if raise_errors: raise e
        finally:
            if auto_commit: await conn.commit()
            await conn.aclose()
            # if readonly: gc.collect()

    @contextlib.contextmanager
    def sconnection(
        self,
        readonly: Optional[bool] = None,
        raise_errors: Optional[bool] = None,
        auto_rollback: Optional[bool] = True,
        auto_commit: Optional[bool] = None,
        superuser: Optional[bool] = None,
        execution_options: Optional[Dict[str, Any]] = None,
        url: Optional[str] = None,
        **kwargs,
    ) -> Generator[Connection, None, None]:
        """
        Context Manager for the connection
        """
        engine = self.get_engine(
            url = url,
            readonly = readonly,
            superuser = superuser,
            execution_options = execution_options,
            **kwargs,
        )
        conn: Connection = None
        try:
            with engine.connect() as conn:
                yield conn
        except Exception as e:
            logger.trace('Engine error', e, depth = 5)
            self.run_error_callbacks(e)
            if auto_rollback: 
                try:
                    conn.rollback()
                    logger.info('Connection Rolled Back')
                except Exception as e:
                    logger.trace('Connection Rollback Error', e)
            if raise_errors: raise e
        finally:
            if conn is not None:
                if auto_commit: conn.commit()
                conn.close()
            # if readonly: gc.collect()
            

    
    """
    Utility Methods
    """

    @staticmethod
    def text(sql: str) -> TextClause:
        """
        Returns the text
        """
        return sql_text(sql)

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


    async def database_exists(
        self,
        db_name: str,
    ) -> bool:
        """
        Checks if the database exists
        """
        statement = self.text(
            f"SELECT 1 FROM pg_database WHERE datname = '{db_name}';"
        )
        async with self.session() as session:
            result = await session.execute(statement)
            output = result.scalar_one()
            logger.info(f'Database Exists: {output}')
            return output
    
    def get_table_names(
        self,
        schema: Optional[str] = None,
    ) -> List[str]:
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
        schema: Optional[str] = None,
        verbose: Optional[bool] = False,
    ) -> Dict[str, Union[str, float]]:
        """
        Displays the table column size
        """
        table_name = f'{schema}.{table}' if schema else table
        with self.sconnection() as conn:
            result = conn.execute(
                self.text(f'''
                select
                    pg_size_pretty(sum(pg_column_size({column}))) as total_size,
                    pg_size_pretty(avg(pg_column_size({column}))) as average_size,
                    sum(pg_column_size({column})) * 100.0 / pg_total_relation_size('{table_name}') as percentage
                from {table_name};
                '''
            ))
        row = result.fetchone()
        if verbose: logger.info(f'Total Size: |g|{row[0]}|e|, Avg Size: |g|{row[1]}|e|, Percentage: |y|{row[2]:.2f}%|e|', prefix = f'{table_name}.{column}', colored = True)
        return {
            'total_size': row[0],
            'average_size': row[1],
            'percentage': row[2],
        }
    
    def get_table_column_names(
        self,
        table: str,
        schema: Optional[str] = None,
    ) -> List[str]:
        """
        Returns the table column names
        """
        table_name = f'{schema}.{table}' if schema else table
        with self.sconnection() as conn:
            result = conn.execute(
                self.text(f'''
                select column_name
                from information_schema.columns
                where table_name = '{table_name}';
                '''
            ))
        return [row[0] for row in result.fetchall()]

