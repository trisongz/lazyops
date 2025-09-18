from __future__ import annotations

"""
Base DB Backend Manager
"""

import abc
import pathlib
import contextlib
from lzl.logging import logger, null_logger, Logger
from lzl.types import eproperty
from .config import DatabaseConfig, BaseDBSettings, BackendType, DBConfigT, DBSettingsT
from .utils import SQLAlchemyUtilities
import typing as t

if t.TYPE_CHECKING:
    from .backend import (
        BackendClassT,
        ThreadPool,
        Connection,
        AsyncConnection,
        SMSession,
        SMAsyncSession,
        Engine,
        AsyncEngine,
        ConnectionPool,
        SessionMakerT,
        AsyncSessionMakerT,
        
        SessionT,
        SessionGetT,
        AsyncSessionT,
        AsyncSessionGetT,
        SessionGetterT,
        ScopedSessionMakerT,
        AsyncScopedSessionMakerT,
    )
    from lzl.db.backends import DATABASE_BACKEND_CLASSES


DBManagerT = t.TypeVar('DBManagerT', bound = 'DBBackendManager')

class DBBackendManager(abc.ABC):
    """
    DB Backend Manager
    """    
    _extra: t.Dict[str, t.Any] = {}
    default_backend: t.Optional[BackendType] = 'sqlalchemy'
    db_type: t.Optional[str] = None

    def __init__(
        self,
        default_backend: t.Optional[BackendType] = None,
        debug_enabled: t.Optional[bool] = None,
        settings: t.Optional[DBSettingsT] = None,
        config: t.Optional[DBConfigT] = None,
        error_callbacks: t.Optional[t.List[t.Callable]] = None,
        # These exceptions will be handled by the error callbacks
        handled_exceptions: t.Optional[t.List[t.Type[Exception]]] = None,
        **kwargs,
    ):
        """
        Initializes the DB Backend Manager
        """
        if default_backend: self.default_backend = default_backend
        self.debug_enabled = debug_enabled
        self.current: t.Optional[str] = None
        self.backends: t.Dict[str, 'DATABASE_BACKEND_CLASSES'] = {}
        self._on_failure_callbacks: t.List[t.Callable] = error_callbacks or []
        self._handled_exceptions: t.List[t.Type[Exception]] = handled_exceptions or []
        self.db_type_name = self.db_type.capitalize() if self.db_type else 'DB'
        self.post_init(**kwargs)
        if not self.current and (settings or config):
            self.configure_backend(
                settings = settings,
                config = config,
                **kwargs,
            )
    
    def add_error_callback(self, callback: t.Callable):
        """
        Adds an error callback
        """
        self._on_failure_callbacks.append(callback)

    def post_init(self, **kwargs):
        """
        Post Initialization
        """
        pass

    def initialize_backend(
        self,
        name: t.Optional[str] = None,
        backend: t.Optional[BackendType] = None,

        settings: t.Optional[DBSettingsT] = None,
        config: t.Optional[DBConfigT] = None,
        
        filepath: t.Optional[t.Union[str, pathlib.Path]] = None, 
        env_var: t.Optional[str] = None,

        settings_app_name: t.Optional[str] = None,
        settings_filepath: t.Optional[t.Union[str, pathlib.Path]] = None,
        settings_env_var: t.Optional[str] = None,

        overrides: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs,
    ) -> 'DATABASE_BACKEND_CLASSES':
        """
        Initializes the backend
        """
        if settings is None and (settings_filepath or settings_env_var):
            from lzl.db.configs import ADAPTER_TO_SETTINGS
            settings = ADAPTER_TO_SETTINGS[self.db_type](
                app_name = settings_app_name,
                env_var = settings_env_var,
                config_file = settings_filepath,
            )
        if settings and not config: 
            self.logger.info(f'Using Overrides: {overrides}', prefix = self.db_type_name, colored = True)
            config = settings.get_backend_config(
                filepath = filepath,
                env_var = env_var,
                **(overrides or {}),
            )
        assert config is not None, 'Config must be provided'
        name = name or config.name
        assert name not in self.backends, f'Backend {name} already exists'
        if backend is None: backend = config.backend or self.default_backend
        from lzl.db.backends import ADAPTER_TO_BACKENDS
        assert backend in ADAPTER_TO_BACKENDS[self.db_type], f'Invalid backend: {backend}'
        # assert backend in _BackendMapping, f'Invalid backend: {backend}'
        self.autologger.info(f'Initializing Backend |g|{name}|e| ({backend})', prefix = self.db_type_name, colored = True)
        backend_cls = ADAPTER_TO_BACKENDS[self.db_type][backend]
        # backend_cls = _BackendMapping[backend]
        return backend_cls(config = config, name = name, **kwargs)

    def configure_backend(
        self,
        name: t.Optional[str] = None,
        backend: t.Optional[BackendType] = None,
        settings: t.Optional[DBSettingsT] = None,
        config: t.Optional[DBConfigT] = None,
        
        filepath: t.Optional[t.Union[str, pathlib.Path]] = None, 
        env_var: t.Optional[str] = None,

        settings_app_name: t.Optional[str] = None,
        settings_filepath: t.Optional[t.Union[str, pathlib.Path]] = None,
        settings_env_var: t.Optional[str] = None,

        overrides: t.Optional[t.Dict[str, t.Any]] = None,
        set_as_current: t.Optional[bool] = None,
        **kwargs,
    ) -> 'DATABASE_BACKEND_CLASSES':
        """
        Configures the backend
        """
        bkend = self.initialize_backend(
            name = name,
            backend = backend,
            settings = settings,
            config = config,
            filepath = filepath,
            env_var = env_var,
            settings_app_name = settings_app_name,
            settings_filepath = settings_filepath,
            settings_env_var = settings_env_var,
            overrides = overrides,
            **kwargs,
        )
        self.backends[bkend.name] = bkend
        self.autologger.info(f'Configured Backend |g|{bkend.name}|e| ({bkend.backend})', prefix = 'PostgresDB', colored = True)
        if set_as_current or not self.current: 
            self.current = bkend.name
            self.autologger.info(f'Set Current Backend |g|{bkend.name}|e| ({bkend.backend})', prefix = 'PostgresDB', colored = True)
        return bkend

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
        return logger if self.debug_enabled else null_logger

    @eproperty
    def tpool(self) -> 'ThreadPool':
        """
        Returns the ThreadPool
        """
        from lzl.pool import ThreadPool
        return ThreadPool
    
    @eproperty
    def sql(self) -> 'SQLAlchemyUtilities':
        """
        Returns the SQLAlchemy Utilities
        """
        return SQLAlchemyUtilities()
    
    @property
    def bkend(self) -> 'DATABASE_BACKEND_CLASSES':
        """
        Returns the backend
        """
        return self.backends[self.current]


    def run_error_callbacks(
        self, 
        e: Exception,
        backend: 'BackendClassT',
        scoped: t.Optional[bool] = None,
        readonly: t.Optional[bool] = None,
    ):
        """
        Runs the error callbacks
        """
        import traceback
        tb = traceback.format_exc()
        partial_kws = {
            'error': e,
            'message': tb,
            'url': backend.url,
            'name': backend.name,
            'scoped': scoped,
            'readonly': readonly,
            'backend': backend.backend,
        }
        for cb in self._on_failure_callbacks:
            self.tpool.create_background_task(cb, **partial_kws)

    def _is_handled_exception(self, e: Exception) -> bool:
        # sourcery skip: use-any, use-next
        """
        Checks if the exception is handled
        """
        for cls in self._handled_exceptions:
            if isinstance(e, cls): return True
        return False
    
    @t.overload
    @contextlib.contextmanager
    def session(
        self, 
        readonly: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        scoped: t.Optional[bool] = None,
        ctx: t.Optional[str] = None,
        **kwargs,
    ) -> t.Generator['SMSession', None, None]:
        """
        Context Manager for the current session
        """
        ...

    @contextlib.contextmanager
    def session(
        self, 
        readonly: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        scoped: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        ctx: t.Optional[str] = None,
        **kwargs,
    ) -> t.Generator['SessionT', None, None]:
        """
        Context Manager for the current session
        """
        bkend = self.bkend
        ctx = ctx or self.current
        assert ctx is not None, 'Context must be set'
        assert ctx in self.backends, f'Invalid Context: {ctx} not in {list(self.backends.keys())}'
        sess_type, scoped = bkend._get_session(
            readonly = readonly,
            scoped = scoped,
            superuser = superuser,
            mode = 'sync',
        )
        sess: 'SessionT' = None
        try:
            sess: 'SessionT' = sess_type()
            yield sess
        except Exception as e:
            if not self._is_handled_exception(e):
                self.logger.trace(f'[{ctx} - {bkend.name}] Session error', e, depth = 5)
            self.run_error_callbacks(e, bkend, scoped, readonly)
            if auto_rollback is None: auto_rollback = bkend.config.auto_rollback_enabled
            if auto_rollback: 
                try:
                    sess.rollback()
                    self.logger.info('Session Rolled Back', prefix = f'{ctx} - {bkend.name}')
                except Exception as e:
                    self.logger.trace(f'[{ctx} - {bkend.name}] Session Rollback Error', e)
            if raise_errors: raise e
        finally:
            if auto_commit is None: auto_commit = bkend.config.autocommit_enabled
            if auto_commit:
                if scoped: sess_type.commit()
                else: sess.commit()
            if scoped: 
                sess_type.expire_all()
                sess_type.close()
                sess_type.remove()
            else:
                sess.close()

    @t.overload
    @contextlib.asynccontextmanager
    async def asession(
        self, 
        readonly: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        scoped: t.Optional[bool] = None,
        ctx: t.Optional[str] = None,
        **kwargs,
    ) -> t.AsyncGenerator['SMAsyncSession', None]:
        ...

    @contextlib.asynccontextmanager
    async def asession(
        self, 
        readonly: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        scoped: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        ctx: t.Optional[str] = None,
        **kwargs,
    ) -> t.AsyncGenerator['AsyncSessionGetT', None]:
        """
        Async Context Manager for the current session
        """
        if ctx is None: ctx = self.current
        assert ctx is not None, 'Context must be set'
        assert ctx in self.backends, f'Invalid Context: {ctx} not in {list(self.backends.keys())}'
        bkend = self.backends[ctx]
        sess_type, scoped = bkend._get_session(
            readonly = readonly,
            scoped = scoped,
            superuser = superuser,
            mode = 'async',
        )
        sess: 'AsyncSessionT' = None
        try:
            sess: 'AsyncSessionT' = sess_type()
            yield sess
        except Exception as e:
            if not self._is_handled_exception(e):
                self.logger.trace(f'[{ctx} - {bkend.name}] Session error', e, depth = 5)
            self.run_error_callbacks(e, bkend, scoped, readonly)
            if auto_rollback is None: auto_rollback = bkend.config.auto_rollback_enabled
            if auto_rollback: 
                try:
                    await sess.rollback()
                    self.logger.info('Session Rolled Back', prefix = f'{ctx} - {bkend.name}')
                except Exception as e:
                    self.logger.trace(f'[{ctx} - {bkend.name}] Session Rollback Error', e)
            if raise_errors: raise e
        finally:
            if auto_commit is None: auto_commit = bkend.config.autocommit_enabled
            if auto_commit:
                if scoped: await sess_type.commit()
                else: await sess.commit()
            if scoped: 
                sess_type.expire_all()
                await sess_type.close()
                await sess_type.remove()
            else:
                await sess.close()


    def database(
        self, 
        readonly: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        mode: t.Optional[t.Literal['sync', 'async']] = 'sync',
        ctx: t.Optional[str] = None,
        **kwargs,
    ) -> t.Callable[..., 'SessionGetT']:
        """
        Creates an inner dependency wrapper for the database session [FastAPI]
        """
        if mode == 'sync':
            def inner() -> t.Generator['SessionGetterT', None, None]:
                """
                Returns the database session
                """
                with self.session(readonly = readonly, auto_commit = auto_commit, raise_errors = raise_errors, auto_rollback = auto_rollback, superuser = superuser, ctx = ctx, **kwargs) as sess:
                    yield sess
        else:
            async def inner() -> t.AsyncGenerator['AsyncSessionGetT', None]:
                """
                Returns the database session
                """
                async with self.asession(readonly = readonly, auto_commit = auto_commit, raise_errors = raise_errors, auto_rollback = auto_rollback, superuser = superuser, ctx = ctx, **kwargs) as sess:
                    yield sess
        return inner

    def connection(
        self,
        readonly: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        url: t.Optional[str] = None,
        ctx: t.Optional[str] = None,
        **kwargs,
    ) -> t.Generator['Connection', None, None]:
        """
        Context Manager for the connection
        """
        if ctx is None: ctx = self.current
        assert ctx is not None, 'Context must be set'
        assert ctx in self.backends, f'Invalid Context: {ctx} not in {list(self.backends.keys())}'
        bkend = self.backends[ctx]
        return bkend.connection(
            readonly = readonly,
            raise_errors = raise_errors,
            auto_rollback = auto_rollback,
            auto_commit = auto_commit,
            superuser = superuser,
            execution_options = execution_options,
            url = url,
            **kwargs,
        )
    
    def aconnection(
        self,
        readonly: t.Optional[bool] = None,
        raise_errors: t.Optional[bool] = None,
        auto_rollback: t.Optional[bool] = None,
        auto_commit: t.Optional[bool] = None,
        superuser: t.Optional[bool] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        url: t.Optional[str] = None,
        ctx: t.Optional[str] = None,
        **kwargs,
    ) -> t.AsyncGenerator['AsyncConnection', None]:
        """
        Context Manager for the connection
        """
        if ctx is None: ctx = self.current
        assert ctx is not None, 'Context must be set'
        assert ctx in self.backends, f'Invalid Context: {ctx} not in {list(self.backends.keys())}'
        bkend = self.backends[ctx]
        return bkend.aconnection(
            readonly = readonly,
            raise_errors = raise_errors,
            auto_rollback = auto_rollback,
            auto_commit = auto_commit,
            superuser = superuser,
            execution_options = execution_options,
            url = url,
            **kwargs,
        )
    
    @t.overload
    @classmethod
    def default(
        cls: t.Type['DBManagerT'],
        name: t.Optional[str] = None,
        default_backend: t.Optional[BackendType] = None,
        debug_enabled: t.Optional[bool] = None,
        
        settings: t.Optional[DBSettingsT] = None,
        config: t.Optional[DBConfigT] = None,
        
        filepath: t.Optional[t.Union[str, pathlib.Path]] = None, 
        env_var: t.Optional[str] = None,

        settings_app_name: t.Optional[str] = None,
        settings_filepath: t.Optional[t.Union[str, pathlib.Path]] = None,
        settings_env_var: t.Optional[str] = None,

        overrides: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs,
    ) -> 'DBManagerT':
        """
        Returns the default backend manager
        
        Args:
            name (t.Optional[str], optional): 
                The name of the backend. Defaults to None.
                This should be a unique name for the backend.

            default_backend (t.Optional[BackendType], optional): 
                The default backend type. Defaults to None.

            debug_enabled (t.Optional[bool], optional): 
                Whether to enable debug mode. Defaults to None.
            
            settings (t.Optional['DBSettingsT'], optional): 
                The settings object. Defaults to None.
            
            config (t.Optional['DBConfigT'], optional): 
                The config object. Defaults to None.
            
            filepath (t.Optional[t.Union[str, pathlib.Path]], optional): 
                The config file path. Defaults to None.
            
            env_var (t.Optional[str], optional): 
                The config env var. Defaults to None.
            
            settings_app_name (t.Optional[str], optional):
                The settings app name. Defaults to None.

            settings_filepath (t.Optional[t.Union[str, pathlib.Path]], optional):
                The settings config file path. Defaults to None.

            settings_env_var (t.Optional[str], optional):
                The settings config env var. Defaults to None.

            overrides (t.Optional[t.Dict[str, t.Any]], optional): 
                The config overrides. Defaults to None.
                This is used to override the config values.
        """
        ...


    @classmethod
    def default(
        cls: t.Type['DBManagerT'],
        name: t.Optional[str] = None,
        default_backend: t.Optional[BackendType] = None,
        debug_enabled: t.Optional[bool] = None,
        settings: t.Optional[DBSettingsT] = None,
        config: t.Optional[DBConfigT] = None,
        overrides: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs,
    ) -> 'DBManagerT':
        """
        Returns the default backend manager
        """
        if not settings and not config:
            from lzl.db.configs import ADAPTER_TO_SETTINGS
            settings = ADAPTER_TO_SETTINGS[cls.db_type]()
        return cls(
            name = name,
            default_backend = default_backend,
            debug_enabled = debug_enabled,
            settings = settings,
            config = config,
            overrides = overrides,
            **kwargs,
        )
    
    def add_error_callback(self, *callbacks: t.Callable):
        """
        Adds an error callback
        """
        self._on_failure_callbacks.extend(callbacks)

    def add_handled_exception(self, *exceptions: t.Type[Exception]):
        """
        Adds an exception to the handled exceptions
        """
        self._handled_exceptions.extend(exceptions)
    
    def add_exception_callback(self, callback: t.Callable, *exceptions: t.Type[Exception]):
        """
        Adds an exception callback
        """
        self._on_failure_callbacks.append(callback)
        self._handled_exceptions.extend(exceptions)


    def __getattr__(self, name: str) -> t.Any:
        """
        Forward all unknown attributes to the backend
        """
        # logger.info(f'Forwarding Attribute: {name} to {self.current}', prefix = 'PGBackendManager', colored = True)
        if name in self.backends:
            return self.backends[name]
        return getattr(self.bkend, name)
    
    if t.TYPE_CHECKING:
        @property
        def engine(self) -> 'Engine':
            """
            Returns the engine
            """
            ...

        @property
        def engine_su(self) -> 'Engine':
            """
            Returns the superuser engine
            """

        @property
        def engine_ro(self) -> 'Engine':
            """
            Returns the readonly engine
            """

        @property
        def aengine(self) -> 'AsyncEngine':
            """
            [Async] Returns the engine
            """
            ...

        @property
        def aengine_su(self) -> 'AsyncEngine':
            """
            [Async] Returns the superuser engine
            """
        
        @property
        def aengine_ro(self) -> 'AsyncEngine':
            """
            [Async] Returns the readonly engine
            """

        @property
        def session_ro(self) -> 'SessionMakerT':
            """
            Returns the readonly session
            """
            ...

        @property
        def session_su(self) -> 'SessionMakerT':
            """
            Returns the superuser session
            """
        
        @property
        def asession_ro(self) -> 'AsyncSessionMakerT':
            """
            [Async] Returns the readonly session
            """
            ...

        @property
        def asession_su(self) -> 'AsyncSessionMakerT':
            """
            [Async] Returns the superuser session
            """
            ...

        @property
        def session_scoped(self) -> 'ScopedSessionMakerT':
            """
            Returns the Scoped Session 
            """
            ...
        
        @property
        def asession_scoped(self) -> 'AsyncScopedSessionMakerT':
            """
            [Async] Returns the Scoped Session
            """
            ...

            
        @property
        def pgpool(self) -> 'ConnectionPool':
            """
            Returns the Connection Pool
            """
        
        @property
        def pgpool_ro(self) -> 'ConnectionPool':
            """
            [Readonly] Returns the Connection Pool
            """
        
        @property
        def pgpool_su(self) -> 'ConnectionPool':
            """
            [Superuser] Returns the Connection Pool
            """
