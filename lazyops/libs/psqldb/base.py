import os
import time
import asyncio
import contextlib

from lazyops.imports._sqlalchemy import require_sql

require_sql(required=True, require_asyncpg=True, require_psycopg2=True)

from sqlalchemy import create_engine, event, exc
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine

from lazyops.utils.logs import logger
from lazyops.utils import Json
from lazyops.types import BaseModel, lazyproperty, BaseSettings, Field
from typing import Any, Generator, AsyncGenerator, Optional, Union, Type, Dict, cast, TYPE_CHECKING, List, Tuple, TypeVar, Callable
from pydantic.networks import PostgresDsn
from lazyops.libs.psqldb.retry import reconnecting_engine

Base = declarative_base()

EngineT = Union[Engine, AsyncEngine]
SessionT = Union[Session, AsyncSession]
SettingsT = Union[Type[BaseSettings], Any]



class Dummy(BaseModel):
    dsn: PostgresDsn

def uri_builder(uri: Union[str, PostgresDsn], scheme: Optional[str] = None) -> PostgresDsn:
    """
    Helper to construct a PostgresDsn from a string
    """
    # print(uri)
    if uri is None: raise ValueError('uri cannot be empty')
    if isinstance(uri, str):
        # if scheme and not uri.startswith(scheme):
        if scheme and '://' not in uri:
            uri = f'{scheme}://{uri}'
        x = Dummy(dsn=uri)
        uri = x.dsn
    
    if scheme and uri.scheme != scheme:
        new = uri.replace(uri.scheme, scheme)
        x = Dummy(dsn=new)
        uri = x.dsn
    
    return uri

def get_nested_arg(
    config: Dict[str, Any],
    base_config: Dict[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    """
    Helper to get a nested value from a config
    """
    return config.pop(key) if key in config else base_config.get(key, default)




class Context(BaseModel):
    uri: PostgresDsn

    scheme: Optional[str] = 'postgresql+psycopg2'
    async_scheme: Optional[str] = 'postgresql+asyncpg'
    
    eng: Optional[EngineT] = None
    eng_ro: Optional[EngineT] = None

    sess: Optional[SessionT] = None
    sess_ro: Optional[SessionT] = None

    asess: Optional[SessionT] = None
    asess_ro: Optional[SessionT] = None

    aeng: Optional[EngineT] = None
    aeng_ro: Optional[EngineT] = None

    settings: Optional[SettingsT] = None
    config: Optional[Dict[str, Any]] = Field(default = {})

    @property
    def debug_enabled(self) -> bool:
        """
        Returns the debug_enabled flag from the settings
        """
        if self.settings:
            return getattr(self.settings, 'debug_enabled', False)
        return os.getenv('DEBUG_ENABLED', 'false') in ['true', 'True', '1']
        # return cast(bool, os.getenv('DEBUG_ENABLED', 'false'))
    
    @property
    def is_verbose(self) -> bool:
        """
        Returns the verbose flag from the settings
        """
        if self.settings:
            if hasattr(self.settings, 'logging'):
                return getattr(self.settings.logging, 'db_verbose', False)
            if hasattr(self.settings, 'db_verbose'):
                return getattr(self.settings, 'db_verbose', False)
            if hasattr(self.settings, 'postgres_verbose'):
                return getattr(self.settings, 'postgres_verbose', False)
        return os.getenv('DB_VERBOSE', 'false') in ['true', 'True', '1']
        # return cast(bool, os.getenv('DB_VERBOSE', 'false'))
    
    @property
    def retries(self) -> int:
        """
        Returns the retries from the settings
        """
        if self.settings:
            return getattr(self.settings, 'postgres_retry_limit', 5)
        return int(os.getenv('DB_RETRIES', '5'))
    
    @property
    def retry_interval(self) -> float:
        """
        Returns the retry_interval from the settings
        """
        if self.settings:
            return getattr(self.settings, 'postgres_retry_interval', 5.0)
        return float(os.getenv('DB_RETRY_INTERVAL', '5.0'))
        # return cast(float, os.getenv('DB_RETRY_INTERVAL', '5.0'))

    @lazyproperty
    def has_pooler(self) -> bool:
        """
        Returns whether the uri has a pooler
        """
        return 'pooler' in self.uri
    
    @lazyproperty
    def uri_ro(self) -> PostgresDsn:
        """
        Returns the read-only uri
        """
        return uri_builder(self.uri.replace('pooler-rw', 'pooler-ro'))

    @lazyproperty
    def async_uri(self) -> PostgresDsn:
        """
        Returns the async uri
        """
        return uri_builder(self.uri, scheme=self.async_scheme)
    
    @lazyproperty
    def async_uri_ro(self) -> PostgresDsn:
        """
        Returns the async read-only uri
        """
        return uri_builder(self.uri_ro, scheme=self.async_scheme)

    @lazyproperty
    def has_ro(self) -> bool:
        """
        Returns whether there is a RO connection available
        """
        return self.uri != self.uri_ro

    def reset(self):
        """
        Resets the connections
        """
        self.eng = None
        self.eng_ro = None

        self.aeng = None
        self.aeng_ro = None
        
        self.sess = None
        self.sess_ro = None

        self.asess = None
        self.asess_ro = None

    @property
    def engine(self) -> Engine:
        """
        Returns the engine
        """
        if self.eng is None:
            self.eng = create_engine(
                self.uri,
                future = self.config.get('future', True),
                echo = self.config.get('echo', self.is_verbose),
                pool_pre_ping = self.config.get('pool_pre_ping', True),
                **self.config.get('engine_args', {}),
        )
        return self.eng

    @property
    def engine_ro(self) -> Engine:
        """
        Returns the read-only engine
        """
        if self.eng_ro is None and self.has_ro:
            eng_args = self.config.get('engine_ro_args', {})
            self.eng_ro = create_engine(
                self.uri_ro,
                echo = get_nested_arg(eng_args, self.config, 'echo', self.is_verbose),
                future = get_nested_arg(eng_args, self.config, 'future', True),
                pool_pre_ping = get_nested_arg(eng_args, self.config, 'pool_pre_ping', True),
                **eng_args,
        )
        return self.eng_ro
    
    @property
    def async_engine(self) -> AsyncEngine:
        """
        Returns the async engine
        """
        
        if self.aeng is None:
            eng_args = self.config.get('async_engine_args', {})
            self.aeng = create_async_engine(
                self.async_uri,
                echo = get_nested_arg(eng_args, self.config, 'echo', self.is_verbose),
                # future = get_nested_arg(eng_args, self.config, 'future', True),
                # pool_pre_ping = get_nested_arg(eng_args, self.config, 'pool_pre_ping', True),
                json_serializer = get_nested_arg(eng_args, self.config, 'json_serializer', Json.dumps),
                pool_size = get_nested_arg(eng_args, self.config, 'pool_size', 50),
                **eng_args,
        )
        return self.aeng

    @property
    def async_engine_ro(self) -> AsyncEngine:
        """
        Returns the read-only async engine
        """
        if self.aeng_ro is None and self.has_ro:
            eng_args = self.config.get('async_engine_ro_args', {})
            self.aeng_ro = create_async_engine(
                self.async_uri_ro,
                echo = get_nested_arg(eng_args, self.config, 'echo', self.is_verbose),
                # future = get_nested_arg(eng_args, self.config, 'future', True),
                # pool_pre_ping = get_nested_arg(eng_args, self.config, 'pool_pre_ping', True),
                json_serializer = get_nested_arg(eng_args, self.config, 'json_serializer', Json.dumps),
                pool_size = get_nested_arg(eng_args, self.config, 'pool_size', 50),
                execution_options = get_nested_arg(eng_args, self.config, 'execution_options', 
                    {
                        "isolation_level": "READ COMMITTED",
                        "postgresql_readonly": True,
                        "postgresql_deferrable": True,
                    }
                ),
                **eng_args,
        )
        return self.aeng_ro
    
    @property
    def session(self) -> Session:
        """
        Returns the session
        """
        if self.sess is None:
            sess_args = self.config.get('session_args', {})
            self.sess = sessionmaker(
                bind = self.engine,
                autoflush = get_nested_arg(sess_args, self.config, 'autoflush', True),
                expire_on_commit = get_nested_arg(sess_args, self.config, 'expire_on_commit', False),
                class_ = Session,
            )
        return self.sess
    
    @property
    def session_ro(self) -> Optional[Session]:
        """
        Returns the read-only session
        """
        if self.sess_ro is None and self.has_ro:
            sess_args = self.config.get('session_ro_args', {})
            self.sess_ro = sessionmaker(
                bind = self.engine_ro,
                autoflush = get_nested_arg(sess_args, self.config, 'autoflush', True),
                expire_on_commit = get_nested_arg(sess_args, self.config, 'expire_on_commit', False),
                class_ = Session,
            )
        return self.sess_ro if self.sess_ro is not None else None
    
    def get_sess(self, ro: Optional[bool] = False, **kwargs) -> Session:
        """
        Returns a session
        """
        if ro and self.has_ro:
            return self.session_ro(**kwargs)
        return self.session(**kwargs)
    
    def get_async_sess(self, ro: Optional[bool] = False, **kwargs) -> AsyncSession:
        """
        Returns an async session
        """
        if ro and self.has_ro:
            return self.async_session_ro(**kwargs)
        return self.async_session(**kwargs)

    
    @property
    def async_session(self) -> AsyncSession:
        """
        Returns the async session
        """
        if self.asess is None:
            sess_args = self.config.get('async_session_args', {})
            self.asess = sessionmaker(
                bind = self.async_engine,
                autoflush = get_nested_arg(sess_args, self.config, 'autoflush', True),
                expire_on_commit = get_nested_arg(sess_args, self.config, 'expire_on_commit', False),
                class_ = AsyncSession,
            )
        return self.asess
    
    @property
    def async_session_ro(self) -> Optional[AsyncSession]:
        """
        Returns the read-only async session
        """
        if self.asess_ro is None and self.has_ro:
            sess_args = self.config.get('async_session_ro_args', {})
            self.asess_ro = sessionmaker(
                bind = self.async_engine_ro,
                autoflush = get_nested_arg(sess_args, self.config, 'autoflush', True),
                expire_on_commit = get_nested_arg(sess_args, self.config, 'expire_on_commit', False),
                class_ = AsyncSession,
            )
        return self.asess_ro if self.asess_ro is not None else None
    
    @classmethod
    def from_uri(
        cls,
        uri: str,
        scheme: Optional[str] = 'postgresql+psycopg2',
        async_scheme: Optional[str] = 'postgresql+asyncpg',
        settings: Optional[SettingsT] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> 'Context':
        """
        Configures the connection
        """
        uri = uri_builder(uri, scheme=scheme)
        if config is None: config = {}
        if kwargs: config.update(kwargs)
        return cls(uri = uri, async_scheme=async_scheme, settings=settings, config=config)


    @contextlib.contextmanager
    def get_session(self, ro: Optional[bool] = False, future: bool = True, **kwargs) -> Generator[Session, None, None]:
        """
        Context manager for database session
        """
        sess: Session = self.get_sess(ro = ro, future = future, **kwargs)
        try:
            yield sess
        finally:
            if sess is not None:
                if self.debug_enabled:
                    logger.debug('Closing Session')
                sess.close()
    
    @contextlib.asynccontextmanager
    async def get_async_session(
        self, 
        ro: Optional[bool] = False, 
        retries: Optional[int] = None,
        retry_interval: Optional[float] = None,
        **kwargs
    ) -> Generator[AsyncSession, None, None]:
        """
        Async context manager for database session
        """
        # sess: AsyncSession = None
        
        retries = retries or self.retries
        retry_interval = retry_interval or self.retry_interval
        sess = self.get_async_sess(ro = ro, **kwargs)
        raw_dbapi_err: Exception = None
        try:
            for retry in range(retries):
                try:
                    async with sess:
                        yield sess
                    break
                except (exc.DisconnectionError, exc.OperationalError, exc.InterfaceError, exc.PendingRollbackError) as raw_dbapi_err:
                    await sess.rollback()
                    logger.error(f"Retrying Execute after error: {raw_dbapi_err.__class__.__name__}: {raw_dbapi_err}")
                    logger.warning(f"Attempt {retry}/{retries}")
                    if raw_dbapi_err.connection_invalidated:
                        logger.warning("Connection invalidated, resetting")
                        await sess.close()

                    await asyncio.sleep(retry_interval)

        finally:
            if sess is not None:
                if self.debug_enabled:
                    logger.debug('Closing Session')
                await sess.close()
                # await sess.dispose()
    

    def create_all(self, base: Optional[Any] = None):
        """
        Creates all tables
        """
        base = base or Base
        with self.engine.begin() as conn:
            conn.run_sync(base.metadata.create_all)
    
    def drop_all(self, base: Optional[Any] = None):
        """
        Drops all tables
        """
        base = base or Base
        with self.engine.begin() as conn:
            conn.run_sync(base.metadata.drop_all)
    
    async def async_create_all(self, base: Optional[Any] = None):
        """
        Creates all tables
        """
        base = base or Base
        async with self.async_engine.begin() as conn:
            await conn.run_sync(base.metadata.create_all)
    
    async def async_drop_all(self, base: Optional[Any] = None):
        """
        Drops all tables
        """
        base = base or Base
        async with self.async_engine.begin() as conn:
            await conn.run_sync(base.metadata.drop_all)

    
class PostgresDBMeta(type):

    _settings: Optional[SettingsT] = None
    _ctx: Optional[Context] = None
    _uri: Optional[str] = None
    _config: Optional[Dict[str, Any]] = None

    scheme: Optional[str] = 'postgresql+psycopg2'
    async_scheme: Optional[str] = 'postgresql+asyncpg'

    get_settings_callable: Optional[Callable] = None

    @property
    def settings(cls) -> SettingsT:
        """
        The settings for the database
        """
        if cls._settings is None:
            cls._settings = cls.get_settings()
            if cls._settings:
                if getattr(cls._settings, 'postgres_scheme', None):
                    cls.scheme = cls._settings.postgres_scheme
                if getattr(cls._settings, 'postgres_async_scheme', None):
                    cls.async_scheme = cls._settings.postgres_async_scheme
        return cls._settings
    
    def get_settings(cls, settings: Optional[SettingsT] = None) -> SettingsT:
        """
        Helper method to override and get/set the settings
        """
        if settings is not None:
            cls.set_settings(settings)
        elif cls.get_settings_callable is not None:
            cls.set_settings(cls.get_settings_callable())
        return cls._settings

    def set_settings(cls, settings: SettingsT):
        """
        Sets the settings
        """
        cls._settings = settings

    @property
    def uri(cls) -> Union[str, PostgresDsn]:
        """
        Returns the uri
        """
        if not cls._uri and cls.settings:
            if getattr(cls.settings, 'pg_uri', None):
                # This should be a PostgresDsn
                cls._uri = cls.settings.pg_uri
                # logger.dev(f"Using pg_uri: {cls._uri}")
            elif getattr(cls.settings, 'postgres_url', None):
                # This should be a string
                # logger.dev(f"Using postgres_url: {cls.settings.postgres_url}")
                cls._uri = uri_builder(cls.settings.postgres_url, scheme=cls.scheme)
            elif getattr(cls.settings, 'postgres_host', None):
                base_uri = f"{cls.settings.postgres_host}:{getattr(cls.settings, 'postgres_port', 5432)}/{getattr(cls.settings, 'postgres_db', 'postgres')}"
                if getattr(cls.settings, 'postgres_user', None):
                    base_uri = (
                        f"{cls.settings.postgres_user}:{cls.settings.postgres_password}@{base_uri}"
                        if getattr(cls.settings, 'postgres_password', None)
                        else f"{cls.settings.postgres_user}@{base_uri}"
                    )
                # logger.dev(f"Using postgres_host: {base_uri}")
                cls._uri = uri_builder(base_uri, scheme=cls.scheme)
        if not cls._uri:
            cls._uri = uri_builder(os.getenv('POSTGRES_URI', 'postgres@127.0.0.1:5432/postgres'), scheme=cls.scheme)
        return cls._uri
    
    @property
    def pg_admin_user(cls) -> str:
        """
        Returns the admin user
        """
        if admin_user := cls.config.get(
            'pg_admin_user', os.getenv('POSTGRES_USER'),
        ):
            return admin_user
        return cls.uri.user
    
    @property
    def pg_admin_password(cls) -> str:
        """
        Returns the admin password
        """
        if admin_password := cls.config.get(
            'pg_admin_password', os.getenv('POSTGRES_PASSWORD'),
        ):
            return admin_password
        return cls.uri.password
    
    @property
    def admin_uri(cls) -> PostgresDsn:
        """
        Returns the admin uri
        """
        uri = f'{cls.uri.host}:{cls.uri.port}/postgres'
        auth = f'{cls.pg_admin_user}'
        if cls.pg_admin_password:
            auth += f':{cls.pg_admin_password}'
        uri = f'{auth}@{uri}'
        return uri_builder(uri, scheme = cls.scheme)

    
    @property
    def config(cls) -> Dict[str, Any]:
        """
        Returns the config
        """
        if not cls._config:
            cls._config = {}
            if cls.settings:
                if getattr(cls.settings, 'pg_config', None):
                    cls._config = cls.settings.pg_config
                elif getattr(cls.settings, 'postgres_config', None):
                    cls._config = cls.settings.postgres_config
        return cls._config
    
    @property
    def ctx(cls) -> Context:
        """
        Returns the context
        """
        if not cls._ctx:
            cls._ctx = Context.from_uri(
                cls.uri, 
                settings = cls.settings, 
                config = cls.config, 
                scheme = cls.scheme, 
                async_scheme = cls.async_scheme
            )
        return cls._ctx

    @property
    def engine(cls) -> Engine:
        """
        Returns the read-write engine
        """
        return cls.ctx.engine
    
    @property
    def engine_ro(cls) -> Optional[Engine]:
        """
        Returns the read-only engine
        """
        return cls.ctx.engine_ro
    
    @property
    def async_engine(cls) -> AsyncEngine:
        """
        Returns the read-write async engine
        """
        return cls.ctx.async_engine
    
    @property
    def async_engine_ro(cls) -> Optional[AsyncEngine]:
        """
        Returns the read-only async engine
        """
        return cls.ctx.async_engine_ro
    
    # @property
    # def session(cls) -> Session:
    #     """
    #     Returns the read-write session
    #     """
    #     return cls.ctx.session
    
    # @property
    # def session_ro(cls) -> Optional[Session]:
    #     """
    #     Returns the read-only session
    #     """
    #     return cls.ctx.session_ro
    
    # @property
    # def async_session(cls) -> AsyncSession:
    #     """
    #     Returns the read-write async session
    #     """
    #     return cls.ctx.async_session
    
    # @property
    # def async_session_ro(cls) -> Optional[AsyncSession]:
    #     """
    #     Returns the read-only async session
    #     """
    #     return cls.ctx.async_session_ro
    
    def get_sess(cls, ro: Optional[bool] = False, future: bool = True, **kwargs) -> Session:
        """
        Returns a session
        """
        return cls.ctx.get_sess(ro=ro, future=future, **kwargs)
    
    def get_async_sess(cls, ro: Optional[bool] = False, **kwargs) -> AsyncSession:
        """
        Returns an async session
        """
        return cls.ctx.get_async_sess(ro=ro, **kwargs)
    

    @contextlib.contextmanager
    def session(
        cls, 
        ro: Optional[bool] = False, 
        future: bool = True, 
        session: Optional[Session] = None,
        **kwargs
    ) -> Generator[Session, None, None]:
        """
        Context manager for database session
        """
        if session is not None:
            yield session
        else:
            with cls.ctx.get_session(ro=ro, future=future, **kwargs) as sess:
                yield sess
    
    @contextlib.asynccontextmanager
    async def async_session(
        cls, 
        ro: Optional[bool] = False, 
        retries: Optional[int] = None,
        retry_interval: Optional[float] = None,
        session: Optional[AsyncSession] = None,
        **kwargs
    ) -> Generator[AsyncSession, None, None]:
        """
        Async context manager for database session
        """
        if session is not None:
            yield session
        else:
            async with cls.ctx.get_async_session(ro=ro, retries = retries, retry_interval = retry_interval, **kwargs) as sess:
                yield sess

    
    def create_all(cls, base: Optional[Any] = None):
        """
        Creates all tables
        """
        base = base or Base
        return cls.ctx.create_all(base=base)
    
    def drop_all(cls, base: Optional[Any] = None):
        """
        Drops all tables
        """
        base = base or Base
        return cls.ctx.drop_all(base=base)
    
    async def async_create_all(cls, base: Optional[Any] = None):
        """
        Creates all tables
        """
        base = base or Base
        return await cls.ctx.async_create_all(base=base)
    
    async def async_drop_all(cls, base: Optional[Any] = None):
        """
        Drops all tables
        """
        base = base or Base
        return await cls.ctx.async_drop_all(base=base)
    

if TYPE_CHECKING:
    from lazyops.libs.dbinit import Privilege

    
class PostgresDB(metaclass=PostgresDBMeta):
    """
    Postgres database
    """
    
    @classmethod
    def prepare_db(
        cls, 

        role_user: Optional[str] = None,
        role_password: Optional[str] = None,
        role_createdb: Optional[bool] = True,
        role_createrole: Optional[bool] = True,
        role_replication: Optional[bool] = True,
        role_bypassrls: Optional[bool] = True,
        role_login: Optional[bool] = None,
        role_options: Optional[Dict[str, Any]] = None,
        role_superuser: Optional[bool] = True,


        db_name: Optional[str] = None,
        db_owner: Optional[str] = None,
        db_grants: Optional[List[Tuple[str, Optional['Privilege']]]] = None,
        db_options: Optional[Dict[str, Any]] = None,

        db_admin_uri: Optional[Union[str, PostgresDsn]] = None,

        statements: Optional[List[str]] = None,
        grant_public_schema: Optional[bool] = True,
        verbose: Optional[bool] = True,
        **kwargs,

    ):  # sourcery skip: low-code-quality
        """
        Runs initialization for the DB
        """
        from lazyops.libs.dbinit import (
            Controller,
            GrantTo,
            Privilege,
            Database,
            Role,
        )

        pg_user = role_user or cls.ctx.uri.user
        pg_pass = role_password or cls.ctx.uri.password
        if role_login is None: role_login = bool(pg_pass)
        if not role_options: role_options = {}
        if not db_options: db_options = {}

        if pg_user == "postgres":
            role = Role(name = pg_user)
        else:
            role = Role(
                name = pg_user,
                createdb = role_createdb,
                createrole = role_createrole,
                replication = role_replication,
                bypassrls = role_bypassrls,
                login = role_login,
                password = pg_pass,
                superuser = role_superuser,
                **role_options
            )
        if verbose:
            logger.info(f"Creating Role {pg_user}: {role}")
        pg_db = db_name or cls.ctx.uri.path[1:]
        db_owner = role if db_owner is None else Role(name = db_owner)
        if not db_grants: 
            db_grants = [
                GrantTo(
                    privileges = [Privilege.ALL_PRIVILEGES], to = [role]
                )
            ]

        db = Database(
            name = pg_db,
            owner = db_owner,
            grants = db_grants,
            **db_options
        )
        if verbose: logger.info(f"Creating Database {pg_db}: {db}")
        db_admin_uri = db_admin_uri or cls.admin_uri
        Controller.run_all(engine = create_engine(url = db_admin_uri))

        engine = create_engine(url = cls.ctx.uri)
        if statements:
            for statement in statements:
                if verbose: logger.info(f"Executing statement: {statement}")
                engine.execute(statement = statement)
        
        if grant_public_schema:
            schema_statements = [
                f"GRANT ALL PRIVILEGES ON SCHEMA public TO {pg_user}",
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO {pg_user}",
                f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {pg_user}",
                f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {pg_user}",
            ]
            if statements: schema_statements = [statement for statement in schema_statements if statement not in statements]
            for statement in schema_statements:
                if verbose: logger.info(f"Executing statement: {statement}")
                engine.execute(statement = statement)

        if verbose: logger.info("Completed DB initialization")



    
    
