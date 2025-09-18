from __future__ import annotations

"""
Base Database Configuration
"""

import os
import copy
import pathlib
from lzl import load
from lzl.logging import logger
from lzl.types import BaseModel, BaseSettings, eproperty, model_validator, AppEnv
from lzo.types import RBaseModel, Field, PrivateAttr
from pydantic.networks import PostgresDsn, MultiHostUrl, UrlConstraints, Annotated, AnyUrl
from .utils import parse_db_config
import typing as t

if t.TYPE_CHECKING:
    from lzl.io import TemporaryData, SerT

SqliteDsn = Annotated[
    MultiHostUrl,
    UrlConstraints(
        host_required=True,
        allowed_schemes=[
            'sqlite',
            'sqlite+aiosqlite',
            'sqlite+asyncio',
            'sqlite+aiosqlite3',
            'sqlite+aiosqlite3-asyncio',
            'sqlite+aiosqlite3-aiofiles',
            'sqlite+aiosqlite3-fastopen',
            'sqlite+pysqlite3',

            # Support rqlite
        ],
    ),
]

DatabaseDsn = t.Union[PostgresDsn, SqliteDsn, AnyUrl]

AdapterToDsn: t.Dict[str, t.Type[DatabaseDsn]] = {
    'postgresql': PostgresDsn,
    'sqlite': SqliteDsn,
}

class BaseDBConfig(RBaseModel):
    """
    The DB Config
    """
    url: t.Optional[DatabaseDsn] = None
    readonly_url: t.Optional[DatabaseDsn] = None
    superuser_url: t.Optional[DatabaseDsn] = None

    @eproperty
    def temp_data(self) -> 'TemporaryData':
        """
        Returns the Temporary Data
        """
        from lzl.io.persistence import TemporaryData
        return TemporaryData(
            filepath = f'{self.module_name}.{self.adapter_prefix.lower()}.cache',
            filedir = self.module_path.joinpath('data'),
        )
    

    """
    Properties that can be used to get the config
    """

    @classmethod
    def get_adapter_prefix(cls) -> str:
        """
        Returns the adapter prefix
        """
        return 'postgres'

    @eproperty
    def adapter_prefix(self) -> str:
        """
        Returns the adapter prefix
        """
        return self.get_adapter_prefix()

    @classmethod
    def get_default_adapter(cls) -> str:
        """
        Returns the default adapter
        """
        return _default_adapters[cls.get_adapter_prefix()]['async']
        # return 'postgresql+asyncpg'

    @eproperty
    def env_prefix_value(self) -> str:
        """
        Returns the env prefix value
        """
        return self.adapter_prefix.upper()

    @eproperty
    def username(self) -> t.Optional[str]:
        """
        The Username for the Default URL
        """
        return self.url.hosts()[0]['username']
    
    @eproperty
    def password(self) -> t.Optional[str]:
        """
        The Password for the Default URL
        """
        return self.url.hosts()[0]['password']
    
    @eproperty
    def superuser_username(self) -> t.Optional[str]:
        """
        The Username for the Superuser URL
        """
        if not self.superuser_url: return None
        return self.superuser_url.hosts()[0]['username']
    
    @eproperty
    def superuser_password(self) -> t.Optional[str]:
        """
        The Password for the Superuser URL
        """
        if not self.superuser_url: return None
        return self.superuser_url.hosts()[0]['password']
    
    @eproperty
    def safe_url(self) -> t.Optional[str]:
        """
        The Safe URL
        """
        return str(self.url).replace(self.password, '********') if self.url else None
    
    @eproperty
    def safe_superuser_url(self) -> t.Optional[str]:
        """
        The Safe Superuser URL
        """
        return str(self.superuser_url).replace(self.superuser_password, '********') if self.superuser_url else None
    
    @eproperty
    def adapterless_url(self) -> str:
        """
        Returns the plain url with only [adapter|postgres|sqlite]://
        """
        return f'{self.adapter_prefix}://' + str(self.url).split('://', 1)[-1].strip()
    
    @eproperty
    def adapterless_ro_url(self) -> t.Optional[str]:
        """
        Returns the plain url with only [adapter|postgres|sqlite]://
        """
        return f'{self.adapter_prefix}://' + str(self.readonly_url).split('://', 1)[-1].strip() if self.readonly_url else None
    
    @eproperty
    def adapterless_superuser_url(self) -> str:
        """
        Returns the plain url with only [adapter|postgres|sqlite]://
        """
        return f'{self.adapter_prefix}://' + str(self.superuser_url).split('://', 1)[-1].strip()
    
    @eproperty
    def has_diff_readonly_url(self) -> bool:
        """
        Checks if the url is different
        """
        return self.readonly_url and str(self.url) != str(self.readonly_url)

    @eproperty
    def has_pooler_in_url(self) -> bool:
        """
        Checks if the url has a pooler in it
        """
        return 'pooler' in str(self.url)
    
    @eproperty
    def in_cluster(self) -> bool:
        """
        Checks if the url is in a cluster
        """
        return 'svc.cluster.local' in str(self.url)
    

    @eproperty
    def cli_connect_string(self) -> str:
        """
        Returns the cli connect string

        export PGPASSWORD=<password> psql -h <host> -p <port> -U <user> -d <database>
        """
        raise NotImplementedError
    

    def get_cli_connect_string(
        self,
        superuser: t.Optional[bool] = None,
        readonly: t.Optional[bool] = None,
        database: t.Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Returns the cli connect string
        """
        raise NotImplementedError
    
    def get_cli_debug_args(self) -> str:
        """
        Returns the cli debug args
        """
        return ''
    
    def get_cli_safe_cmd(self, cmd: str) -> str:
        """
        Returns the cli safe cmd
        """
        raise NotImplementedError


    def has_logged_msg(self, msg: str) -> bool:
        """
        Checks if the message has been logged
        """
        return self.temp_data.has_logged(msg)
    
    def log_readonly_warning(self, verbose: t.Optional[bool] = True):
        """
        Logs the readonly warning
        """
        if not verbose: return
        if not self.has_logged_msg(f'{self.env_prefix_value}_readonly_warning'):
            safe_url = str(self.url).replace(self.password, '********')  if self.password else str(self.url)
            logger.info(f'|y|Readonly URL not set|e|, using default URL: {safe_url}', colored = True, prefix = f'{self.adapter_prefix.capitalize()}DB')

    def log_db_url(self, verbose: t.Optional[bool] = True):
        """
        Logs the Database URL
        """
        if not verbose: return
        if not self.has_logged_msg(f'{self.env_prefix_value}_url'):
            safe_url = str(self.url).replace(self.password, '********')  if self.password else str(self.url)
            logger.info(f'Using URL: |g|{safe_url}|e|', colored = True, prefix = f'{self.adapter_prefix.capitalize()}DB')


if t.TYPE_CHECKING:
    from lzl.db.configs import DATABASE_CONFIG_CLASSES

class BaseDBSettings(BaseDBConfig, BaseSettings):
    """
    The Base DB Settings
    """
    
    if t.TYPE_CHECKING:
        migration_env: t.Optional[t.Union[AppEnv, str]] = None
        target_env: t.Optional[t.Union[AppEnv, str]] = None
    else:
        migration_env: t.Optional[t.Union[str, t.Any]] = None
        target_env: t.Optional[t.Union[str, t.Any]] = None

    class Config:
        env_prefix = "DB_"


    @eproperty
    def env_prefix_value(self) -> str:
        """
        Returns the env prefix value
        """
        return self.Config.env_prefix.lower().rstrip('_')
    
    @eproperty
    def config_class(self) -> t.Type['DATABASE_CONFIG_CLASSES']:
        """
        Returns the config class
        """
        from lzl.db.configs import ADAPTER_TO_CONFIG
        return ADAPTER_TO_CONFIG[self.adapter_prefix]
        # return BaseDBConfig

    @eproperty
    def dsn_class(self) -> t.Type[DatabaseDsn]:
        """
        Returns the DSN class
        """
        return AdapterToDsn[self.adapter_prefix]
    
    @classmethod
    def get_config_file_envvar(cls, values: t.Optional[t.Dict[str, t.Any]] = None, **kwargs) -> str:
        """
        Returns the DB Config File Environment Variable
        """
        return values.pop('env_var') if values and values.get('env_var') else None
    
    @classmethod
    def get_config_file_app_name(cls, values: t.Optional[t.Dict[str, t.Any]] = None, **kwargs) -> str:
        """
        Returns the DB App Name
        """
        return values.pop('app_name') if values and values.get('app_name') else None
    
    @classmethod
    def get_config_file_env_name(cls, values: t.Optional[t.Dict[str, t.Any]] = None, **kwargs) -> t.Optional[t.Union[str, 'AppEnv']]:
        """
        Returns the DB Config File Environment Name
        """
        if values and values.get('target_env'): return values['target_env']
        return cls._fetch_app_env(cls.get_config_file_app_name())
    
    @classmethod
    def fetch_from_config_file(
        cls, 
        env_name: t.Optional[t.Union[str, 'AppEnv']] = None, 
        app_name: t.Optional[str] = None,
        config_file: t.Optional[t.Union[str, pathlib.Path]] = None,
        config_file_env_var: t.Optional[str] = None,
        in_cluster: t.Optional[bool] = None,
        from_init: t.Optional[bool] = None,
        **kwargs,
    ) -> t.Optional[t.Dict[str, t.Any]]:
        """
        Fetches the config from the config file

        Args:
            env_name (t.Optional[t.Union[str, AppEnv]], optional): The environment name. Defaults to None.
            app_name (t.Optional[str], optional): The app name. Defaults to None.
            config_file (t.Optional[t.Union[str, pathlib.Path]], optional): The config file. Defaults to None.
            config_file_env_var (t.Optional[str], optional): The config file environment variable. Defaults to None.
        """
        if not config_file:
            if not config_file_env_var: 
                if not from_init: logger.warning('No Config File Environment Variable Provided')
                return
            config_file = os.getenv(config_file_env_var)
        config_file = pathlib.Path(config_file)
        if not config_file.exists(): 
            logger.warning(f'Config File Does Not Exist: {config_file}')
            return
        import yaml
        if not from_init: logger.info(f'Using {cls.get_adapter_prefix().capitalize()} Config File: {config_file}', colored = True, prefix = f'{app_name} - {env_name}')
        config_data: t.Dict[str, t.Dict[str, t.Dict[str, str]]] = yaml.safe_load(config_file.read_text())
        if app_name and not config_data.get(app_name): 
            if not from_init: logger.warning(f'Config File Does Not Contain App: {app_name}')
            return
        return parse_db_config(
            config_data.get(app_name) if app_name else config_data,
            env_name = env_name,
            in_cluster = in_cluster,
            default_adapter = cls.get_default_adapter(),
            **kwargs,
        )

    @model_validator(mode = 'before')
    def check_for_config_file(cls, values: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        """
        Checks for a config file
        """
        config = cls.fetch_from_config_file(
            app_name = cls.get_config_file_app_name(values),
            env_name = cls.get_config_file_env_name(values),
            config_file = values.pop('config_file', None),
            config_file_env_var = cls.get_config_file_envvar(values),
            from_init = True,
        )
        if not config: return values
        for key in ('url', 'superuser_url', 'readonly_url'):
            if config.get(key): values[key] = config[key]
        if config.get('migration_env'): values['migration_env'] = config['migration_env']
        return values

    @model_validator(mode = 'after')
    def post_init_validate(self):
        """
        Validate after
        """
        if not self.superuser_url: self.superuser_url = self.url
        if self.target_env and not hasattr(self.target_env, 'value'):
            from lzl.types import AppEnv
            self.target_env = AppEnv.from_env(self.target_env)
        return self
    
    def reconfigure(self, app_env: t.Optional[t.Union[str, 'AppEnv']] = None):
        """
        Reconfigures the DB Settings
        """
        app_env = app_env or self.migration_env
        if app_env is None: return
        logger.info(f'Reconfiguring {self.adapter_prefix.capitalize()} Settings for |g|{app_env}|e|', prefix = f'{self.adapter_prefix.capitalize()}DB - {self.get_config_file_app_name()}', colored = True)
        config = self.fetch_from_config_file(
            app_name = self.get_config_file_app_name(),
            env_name = app_env,
            config_file_env_var = self.get_config_file_envvar(),
        )
        if config is None: return
        self.url = self.dsn_class(config['url'])
        if config.get('superuser_url'): self.superuser_url = self.dsn_class(config['superuser_url'])
        else: self.superuser_url = self.url
        if config.get('readonly_url'): self.readonly_url = self.dsn_class(config['readonly_url'])
        self._extra.clear()
        self.log_db_url()

    def get_backend_config(
        self, 
        filepath: t.Optional[t.Union[str, pathlib.Path]] = None, 
        env_var: t.Optional[str] = None,
        **overrides: t.Any
    ) -> 'DBConfigT':
        """
        Returns the backend config
        """
        if filepath or env_var: return self.config_class.from_config_file(filepath = filepath, env_var = env_var, settings = self, **overrides)
        return self.config_class.from_settings(self, **overrides)


_default_pool_classes: t.Dict[str, str] = {
    'default': {
        'sync': 'sqlalchemy.pool.QueuePool',
        'async': 'sqlalchemy.pool.AsyncAdaptedQueuePool',
    },
    'pooled': 'sqlalchemy.pool.NullPool',
    'static': 'sqlalchemy.pool.StaticPool',
}

_default_adapters: t.Dict[str, t.Dict[str, str]] = {
    'postgresql': {
        'sync': 'psycopg2',
        'async': 'asyncpg',
    },
    'postgres': {
        'sync': 'psycopg2',
        'async': 'asyncpg',
    },
    'sqlite': {
        'sync': 'pysqlite',
        'async': 'aiosqlite',
    },
}


_default_session_kwargs: t.Dict[str, t.Dict[str, t.Any]] = {
    'kwargs': {
        'sync': {},
        'async': {
            'pool_pre_ping': True,
        },
    },
}

if t.TYPE_CHECKING:
    from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool, StaticPool, QueuePool

    ConnPoolT = t.Union[QueuePool, AsyncAdaptedQueuePool, NullPool, StaticPool]

class EngineConfig(BaseModel):
    """
    The SQL Engine Config
    """
    
    if t.TYPE_CHECKING:
        poolclass: t.Optional[t.Union[str, t.Type[ConnPoolT]]] = None
    else:
        poolclass: t.Optional[t.Union[str, t.Type]] = None
    
    adapter: t.Optional[str] = None
    serializer: t.Optional[t.Union[t.Callable, str]] = 'json'
    deserializer: t.Optional[t.Union[t.Callable, str]] = 'json'
    kwargs: t.Optional[t.Dict[str, t.Any]] = Field(default_factory = dict)
    rw_kwargs: t.Optional[t.Dict[str, t.Any]] = Field(default_factory = dict)
    ro_kwargs: t.Optional[t.Dict[str, t.Any]] = Field(default_factory = dict)
    mode: t.Optional[t.Literal['sync', 'async']] = 'sync'

    db_type: t.Optional[str] = None

    def configure_serializers(
        self,
        serializer: t.Optional[t.Union[t.Callable, str]] = None,
        deserializer: t.Optional[t.Union[t.Callable, str]] = None,
    ):
        """
        Configures the engine serializers
        """
        valid_ser, valid_deser = True, True
        if serializer is not None:
            if isinstance(serializer, str) and '.' not in serializer:
                from lzl.io.ser import get_serializer
                ser = get_serializer(serializer = serializer)
                ser.enforce_string_value = True
                if deserializer is None or deserializer == serializer:
                    deserializer = ser.loads
                serializer = ser.dumps
            else:
                try:
                    serializer = load.lazy_import(serializer)
                    if callable(serializer):
                        serializer = serializer
                    elif hasattr(serializer, 'dumps'):
                        serializer = getattr(serializer, 'dumps')
                except Exception as e:
                    valid_ser = False
                    logger.error(f'Failed to import the serializer: {e}')
        
        if deserializer is not None and isinstance(deserializer, str):
            if '.' not in deserializer:
                from lzl.io.ser import get_serializer
                ser = get_serializer(serializer = deserializer)
                ser.enforce_string_value = True
                if serializer is None or serializer == deserializer:
                    serializer = ser.dumps
                deserializer = ser.loads
            else:
                try:
                    deserializer = load.lazy_import(deserializer)
                    if callable(deserializer):
                        deserializer = deserializer
                    elif hasattr(deserializer, 'loads'):
                        deserializer = getattr(deserializer, 'loads')
                except Exception as e:
                    valid_deser = False
                    logger.error(f'Failed to import the deserializer: {e}')
        
        if valid_ser: self.serializer = serializer
        if valid_deser: self.deserializer = deserializer


    @model_validator(mode = 'after')
    def validate_engine_config(self):
        """
        Validates the engine config
        """
        if self.poolclass is None:
            self.poolclass = _default_pool_classes['default'][self.mode]
        
        if isinstance(self.poolclass, str):
            if self.poolclass in _default_pool_classes:
                self.poolclass = _default_pool_classes[self.poolclass][self.mode]
            self.poolclass = load.lazy_import(self.poolclass)

        if self.adapter is None: self.adapter = _default_adapters[self.db_type][self.mode]
        if not self.kwargs and _default_session_kwargs.get('kwargs') and _default_session_kwargs['kwargs'].get(self.mode):
            self.kwargs.update(_default_session_kwargs['kwargs'][self.mode])
        if not self.rw_kwargs and _default_session_kwargs.get('rw_kwargs') and _default_session_kwargs['rw_kwargs'].get(self.mode):
            self.rw_kwargs.update(_default_session_kwargs['rw_kwargs'][self.mode])
        if not self.ro_kwargs and _default_session_kwargs.get('ro_kwargs') and _default_session_kwargs['ro_kwargs'].get(self.mode):
            self.ro_kwargs.update(_default_session_kwargs['ro_kwargs'][self.mode])
        # Load the serializers
        self.configure_serializers(
            serializer = self.serializer,
            deserializer = self.deserializer,
        )
        return self
        
class AsyncEngineConfig(EngineConfig):
    """
    The Async Engine Config
    """
    mode: t.Literal['async'] = 'async'


_default_session_kwargs: t.Dict[str, t.Dict[str, t.Any]] = {
    'rw_kwargs': {
        'sync': {},
        'async': {},
    },
    'ro_kwargs': {
        'sync': {},
        'async': {},
    },
}

_session_class_mapping = {
    'default': {
        'sync': 'sqlalchemy.orm.session.Session',
        'async': 'sqlalchemy.ext.asyncio.session.AsyncSession',
    },
    'sqlmodel': {
        'sync': 'sqlmodel.orm.session.Session',
        'async': 'sqlmodel.ext.asyncio.session.AsyncSession',
    },
}
if t.TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlmodel import Session as SMSession
    from sqlmodel.ext.asyncio.session import AsyncSession as SMAsyncSession

    SessionT = t.Union[Session, SMSession, AsyncSession, SMAsyncSession]


class SessionConfig(BaseModel):
    """
    The Session Config
    """
    scoped: t.Optional[bool] = None
    
    if t.TYPE_CHECKING:
        session_class: t.Optional[t.Union[str, t.Type[SessionT]]] = None
    else:
        session_class: t.Optional[t.Union[str, t.Type]] = None
    
    kwargs: t.Optional[t.Dict[str, t.Any]] = Field(default_factory = dict)
    ro_kwargs: t.Optional[t.Dict[str, t.Any]] = Field(default_factory = dict)
    rw_kwargs: t.Optional[t.Dict[str, t.Any]] = Field(default_factory = dict)
    mode: t.Optional[t.Literal['sync', 'async']] = 'sync'
    
    db_type: t.Optional[str] = None

    def get_session_class(
        self,
        session_class: t.Optional[t.Union[str, t.Type['SessionT']]] = None,
        **kwargs
    ) -> t.Type['SessionT']:
        """
        Get the session class
        """
        if session_class is None: 
            session_class = _session_class_mapping['default'][self.mode]
        if isinstance(session_class, str):
            if session_class in _session_class_mapping:
                session_class = _session_class_mapping[session_class][self.mode]
            session_class = load.lazy_import(session_class)
        return session_class

    def configure_session_class(
        self,
        session_class: t.Optional[t.Union[str, t.Type['SessionT']]] = None,
        **kwargs
    ):
        """
        Configures the session class
        """
        self.session_class = self.get_session_class(session_class = session_class, **kwargs)

    @model_validator(mode = 'after')
    def validate_session_config(self):
        """
        Validates the session config
        """
        if not self.kwargs and _default_session_kwargs.get('kwargs') and _default_session_kwargs['kwargs'].get(self.mode):
            self.kwargs.update(_default_session_kwargs['kwargs'][self.mode])
        if not self.rw_kwargs and _default_session_kwargs.get('rw_kwargs') and _default_session_kwargs['rw_kwargs'].get(self.mode):
            self.rw_kwargs.update(_default_session_kwargs['rw_kwargs'][self.mode])
        if not self.ro_kwargs and _default_session_kwargs.get('ro_kwargs') and _default_session_kwargs['ro_kwargs'].get(self.mode):
            self.ro_kwargs.update(_default_session_kwargs['ro_kwargs'][self.mode])
        self.configure_session_class(session_class = self.session_class)
        return self


class AsyncSessionConfig(SessionConfig):
    """
    The Async Session Config
    """
    mode: t.Literal['async'] = 'async'


"""
Restructure the DBConfig to the following:

name: default
connpool:
  max_db_pool_size: 5

engine:
  poolclass: 
  serializer: 
  deserializer: 
  kwargs: {}
  rw_kwargs: {}
  ro_kwargs: 
    execution_options:
      isolation_level: READ COMMITTED
  
 
aengine:
  poolclass: 
  serializer: 
  deserializer: 

  kwargs: {}
  rw_kwargs: {}
  ro_kwargs: {}

session:
  scoped: bool
  session_class:
  kwargs: {}
  ro_kwargs: {}
  rw_kwargs: {}

asession:
  scoped: bool
  session_class:
  kwargs: {}
  ro_kwargs: {}
  rw_kwargs: {}  
"""


class ConnectionPoolConfig(BaseModel):
    max_db_pool_size: t.Optional[int] = 5
    db_type: t.Optional[str] = None


BackendType = t.Literal['sqlalchemy', 'sqlmodel']
DBSettingsT = t.TypeVar('DBSettingsT', bound = BaseDBSettings)


class DatabaseConfig(BaseDBConfig):
    """
    The Database Config
    """
    name: t.Optional[str] = 'default'
    backend: t.Optional[BackendType] = None
    engine: t.Optional[EngineConfig] = None
    aengine: t.Optional[AsyncEngineConfig] = None
    session: t.Optional[SessionConfig] = None
    asession: t.Optional[AsyncSessionConfig] = None
    connpool: t.Optional[ConnectionPoolConfig] = None
    
    debug_enabled: t.Optional[bool] = None
    autocommit_enabled: t.Optional[bool] = None
    auto_rollback_enabled: t.Optional[bool] = True

    @classmethod
    def from_settings(cls, settings: DBSettingsT, **overrides) -> 'DBConfigT':
        """
        Creates the Database Config from the Settings
        """
        if not overrides: return cls.model_validate(settings, from_attributes = True)
        data = settings.model_dump()
        data.update(overrides)
        return cls.model_validate(data)
    
    def merge_settings(self, settings: DBSettingsT) -> 'DBConfigT':
        """
        Merges the settings into the config
        """
        for key in {'url', 'superuser_url', 'readonly_url'}:
            if getattr(settings, key): setattr(self, key, getattr(settings, key))
        return self
    
    @model_validator(mode = 'after')
    def validate_db_config(self):
        """
        Validates the db Config
        """
        if self.engine is None: self.engine = EngineConfig(db_type = self.adapter_prefix)
        if self.aengine is None: self.aengine = AsyncEngineConfig(db_type = self.adapter_prefix)
        if self.session is None: self.session = SessionConfig(db_type = self.adapter_prefix)
        if self.asession is None: self.asession = AsyncSessionConfig(db_type = self.adapter_prefix)
        if self.connpool is None: self.connpool = ConnectionPoolConfig(db_type = self.adapter_prefix)
        if self.backend is not None:
            self.session.configure_session_class(session_class = self.backend)
            self.asession.configure_session_class(session_class = self.backend)
        return self

    @classmethod
    def from_config_file(
        cls,
        filepath: t.Optional[t.Union[str, pathlib.Path]] = None,
        env_var: t.Optional[str] = None,
        settings: t.Optional[DBSettingsT] = None,
        **overrides: t.Any,
    ) -> 'DBConfigT':
        """
        Creates the Postgres Config from a Config File
        """
        if not filepath and not env_var:
            raise ValueError('Either `filepath` or `env_var` must be provided')
        if not filepath: filepath = os.getenv(env_var)
        if not filepath or not filepath.exists(): return cls()
        import yaml
        config_data: t.Dict[str, t.Dict[str, t.Dict[str, str]]] = yaml.safe_load(filepath.read_text())
        if overrides:
            from lzo.utils.helpers import update_dict
            config_data = update_dict(config_data, overrides)
        new = cls.model_validate(config_data)
        if settings: new.merge_settings(settings)
        return new

    def get_engine_kwargs(
        self,
        readonly: t.Optional[bool] = False, 
        verbose: t.Optional[bool] = False, 
        superuser: t.Optional[bool] = None,
        adapter: t.Optional[str] = None,
        mode: t.Optional[t.Literal['sync', 'async']] = 'sync',
        **engine_kwargs
    ) -> t.Dict[str, t.Any]:
        """
        Get the Engine KWargs
        """
        from lzo.utils.helpers import update_dict
        engine = self.engine if mode == 'sync' else self.aengine
        kwargs = copy.deepcopy(engine.kwargs) if engine.kwargs else {}
        if engine_kwargs: kwargs = update_dict(kwargs, engine_kwargs)
        kwargs = (
            update_dict(kwargs, engine.ro_kwargs)
            if readonly
            else update_dict(kwargs, engine.rw_kwargs)
        )
        self.log_readonly_warning(verbose) if readonly else self.log_db_url(verbose)
        if not kwargs.get('url'):
            if superuser and self.superuser_url: kwargs['url'] = str(self.superuser_url)
            else: kwargs['url'] = str((self.readonly_url or self.url) if readonly else self.url)
        
        adapter = adapter or engine.adapter
        if adapter and adapter not in kwargs['url']:
            kwargs['url'] = f'{self.adapter_prefix}+{adapter}://' + kwargs['url'].split('://', 1)[-1]
        if engine.serializer and 'json_serializer' not in kwargs:
            kwargs['json_serializer'] = engine.serializer
        if engine.deserializer and 'json_deserializer' not in kwargs:
            kwargs['json_deserializer'] = engine.deserializer
        if engine.poolclass and 'poolclass' not in kwargs:
            kwargs['poolclass'] = engine.poolclass
        return kwargs


    def get_session_kwargs(
        self, 
        readonly: t.Optional[bool] = False, 
        backend: t.Optional[BackendType] = None,
        mode: t.Optional[t.Literal['sync', 'async']] = 'sync',
        **session_kwargs
    ) -> t.Dict[str, t.Any]:
        """
        Get the Session KWargs
        """
        from lzo.utils.helpers import update_dict
        session = self.session if mode == 'sync' else self.asession
        kwargs = session.kwargs or {}
        if session_kwargs: kwargs = update_dict(kwargs, session_kwargs)
        kwargs = (
            update_dict(kwargs, session.ro_kwargs)
            if readonly
            else update_dict(kwargs, session.rw_kwargs)
        )
        if backend and backend != self.backend:
            session_cls = session.get_session_class(session_class = backend)
            kwargs['class_'] = session_cls
        else:
            kwargs['class_'] = session.session_class
        return kwargs
    
DBConfigT = t.TypeVar('DBConfigT', bound = DatabaseConfig)
