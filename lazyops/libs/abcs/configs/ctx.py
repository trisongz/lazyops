from __future__ import annotations

"""
Create the App Context
"""
import os
import abc
import contextlib
import multiprocessing
from pathlib import Path
from .types import AppEnv
from lazyops.libs.proxyobj import proxied
from typing import Optional, Dict, Any, List, Union, Type, Callable, TypeVar, Literal, overload, TYPE_CHECKING

if TYPE_CHECKING:
    import jinja2
    from pydantic import BaseModel
    from kvdb import KVDBSession, PersistentDict
    from kvdb.tasks.base import BaseTaskWorker, TaskWorkerT
    from lazyops.utils.logs import Logger
    from lazyops.libs.abcs.types.persistence import TemporaryData
    from lazyops.libs.abcs.types.state import AppState
    from lazyops.libs.abcs.state.metrics import AppStateMetrics
    from .base import AppSettings
    from ..clients import ClientTypes
    from ..sql.database.types import ObjectCRUD


    AppSettingsT = TypeVar('AppSettingsT', bound = AppSettings)
    ComponentSchemaT = TypeVar('ComponentSchemaT', BaseModel, ObjectCRUD)

class ApplicationContext(abc.ABC):
    """
    Contains the app context
    """

    def __init__(
        self,
        module_name: str,
        ingress_domain: Optional[str] = None,
        ingress_base: Optional[str] = None,
        config_path: Optional[Path] = None,
        assets_dir: Optional[str] = 'assets',
        **kwargs,
        # global_ctx: Optional['GlobalContextClass'] = None,
    ):
        """
        Creates the app context
        """
        self.module_name = module_name
        self.app_env_var_name = self.module_name.replace(".", "-").replace("_", "-").lower()
        self.env_var_name = self.module_name.replace(".", "_").upper()
        self.is_app_module = '__main__' not in self.module_name
        self.import_assets: Callable[..., Path] = None
        self.get_assets: Callable[..., Path] = None
        self.ingress_base = ingress_base or self.module_name
        self.ingress_domain = ingress_domain
        if self.is_app_module:
            from lazyops.utils.assets import get_module_assets_path
            from lazyops.utils.assets import create_get_assets_wrapper, create_import_assets_wrapper
            if config_path is None:
                try:
                    config_path = get_module_assets_path(self.module_name, 'configs')
                except Exception as e:
                    config_path = Path.cwd()
            self.import_assets = create_import_assets_wrapper(self.module_name, assets_dir)
            self.get_assets = create_get_assets_wrapper(self.module_name, assets_dir)

        self.config_path = config_path
        # self.global_ctx = global_ctx

        self._app_env: Optional[AppEnv] = None
        self._temp_data: Optional['TemporaryData'] = None
        self._settings: Optional['AppSettings'] = None
        self._state: Optional['AppState'] = None
        self._logger: Optional['Logger'] = None
        self.on_close_funcs: List[Callable] = []

        self._kdb_sessions: Dict[str, 'KVDBSession'] = {}
        self._persistent_dicts: Dict[str, 'PersistentDict'] = {}
        self._persistent_dict_aliases: Dict[str, str] = {}

        # Client Registration and Hooks
        self._global_clients: Dict[str, str] = {}
        self._local_clients: Dict[str, str] = {}

        # Component Registration
        self._component_schema_registry: Dict[str, Union[Dict, str, Type]] = {}
        self._component_client_registry: Dict[str, Union[Dict, str, Any]] = {}

        self.include_kind_in_client_name: Optional[bool] = True
        self.include_kind_in_component_name: Optional[bool] = True
        
        self.client_kwarg_function: Optional[Union[Callable[..., Dict[str, Any]], str]] = None
        self.client_hook_function: Optional[Union[Callable, str]] = None

        self.component_client_hook_function: Optional[Union[Callable, str]] = None

        # Jinja2 Contexts
        self.j2_ctxs: Dict[str, 'jinja2.Environment'] = {}
        self.j2_actxs: Dict[str, 'jinja2.Environment'] = {}
    
        # Temp State
        self.temp_state: Dict[str, Any] = {}

        self._extra: Dict[str, Any] = {}


    @property
    def disable_enforce_env(self) -> bool:
        """
        Returns whether to disable the enforce env
        """
        return os.getenv('DISABLE_ENFORCE_ENV', 'false').lower() in {'true', '1'}

    @property
    def app_env(self) -> AppEnv:
        """
        Retrieves the app environment
        """
        if self._app_env is None: self._app_env = self.get_app_env()
        return self._app_env

    @app_env.setter
    def app_env(self, value: AppEnv):
        """
        Sets the app environment
        """
        self._app_env = value
    
    @property
    def state_metrics(self) -> 'AppStateMetrics':
        """
        Retrieves the state metrics
        """
        if 'state_metrics' not in self._extra:
            from lazyops.libs.abcs.state.metrics import AppStateMetrics
            self._extra['state_metrics'] = AppStateMetrics(
                in_k8s = self.settings.in_k8s,
            )
        return self._extra['state_metrics']

    @property
    def temp_data(self) -> 'TemporaryData':
        """
        Retrieves the temporary data
        """
        if self._temp_data is None:
            from lazyops.libs.abcs.types.persistence import TemporaryData
            self._temp_data = TemporaryData.from_module(self.module_name)
        return self._temp_data
    
    @property
    def settings(self) -> 'AppSettings':
        """
        Returns the settings
        """
        if self._settings is None:
            from .lazy import get_module_settings
            self._settings = get_module_settings(self.module_name)
        return self._settings
    
    @property
    def state(self) -> 'AppState':
        """
        Returns the state
        """
        if self._state is None:
            from lazyops.libs.abcs.types.state import AppState
            self._state = AppState()
            self._state.bind_settings(self.settings)
        return self._state
    

    @property
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        if self._logger is None:
            from lazyops.utils.logs import logger as _logger
            self._logger = _logger
        return self._logger

    
    @property
    def is_leader_process(self) -> bool:
        """
        Returns if this is the leader process
        """
        return self.state.is_leader_process or multiprocessing.parent_process() is None
    
    @property
    def is_primary_server_process(self) -> bool:
        """
        Returns if this is the primary server process
        """
        return self.state.is_primary_server_process or multiprocessing.parent_process() is None
    

    def register_settings(self, settings: 'AppSettingsT') -> None:
        """
        Registers the settings
        """
        from .lazy import register_module_settings
        register_module_settings(self.module_name, settings)
        self._settings = settings

    """
    App Environments and Ingress
    """

    def get_app_env(self, module_name: Optional[str] = None) -> AppEnv:
        """
        Retrieves the app environment
        """
        module_name = (module_name or self.env_var_name).upper()
        for key in {
            "SERVER_ENV",
            f"{module_name}_ENV",
            "APP_ENV",
            "ENVIRONMENT",
        }:
            if env_value := os.getenv(key):
                return AppEnv.from_env(env_value)

        # self.logger.info(f'Using: {self.app_env_var_name}')

        from lazyops.utils.system import is_in_kubernetes, get_host_name
        if is_in_kubernetes():
            # Name should be
            # scout-<service>-<index>
            # or 
            # scout-<service>-<env>-<index>

            # if the app name has a - in it, need to handle it differently
            # my-app-server-<index>
            # my-app-server-<env>-<index>
            hn = get_host_name()
            src_hn = hn.replace(self.app_env_var_name, '').strip()
            # if hn.count('-') 
            try:
                parts = src_hn.split('-')
                return AppEnv.from_env(parts[1]) if len(parts) > 2 else AppEnv.PRODUCTION
            except Exception as e:
                # self.logger.error(f'Error getting app env from hostname: {e}')
                return AppEnv.from_hostname(hn)
                # parts = get_host_name().split("-")
                # return AppEnv.from_env(parts[2]) if len(parts) > 3 else AppEnv.PRODUCTION

        return AppEnv.LOCAL
    

    def get_app_ingress(
        self,
        app_host: Optional[str] = None,
        app_port: Optional[int] = None,
    ) -> str:
        """
        Retrieves the app ingress
        """
        if self.app_env.is_local or not self.ingress_domain:
            app_host = app_host or "localhost"
            app_port = app_port or 8080
            return f"http://{app_host}:{app_port}"
        if self.app_env == AppEnv.DEVELOPMENT:
            return f"https://{self.ingress_base}-develop.{self.ingress_domain}"
        if self.app_env == AppEnv.STAGING:
            return f"https://{self.ingress_base}-staging.{self.ingress_domain}"
        if self.app_env == AppEnv.PRODUCTION:
            return f"https://{self.ingress_base}.{self.ingress_domain}"
        raise ValueError(f"Invalid app environment: {self.app_env}")

    def get_app_env_file(
        self,
        name: Optional[str] = None, 
        required: Optional[bool] = False, 
        allow_default: Optional[bool] = True,
        configs_path: Optional[Path] = None,
        env_var: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Retrieves the app environment file

        Only valid for local/dev environments
        """
        if env_var is not None and (env_val := os.getenv(env_var)):
            env_path = Path(env_val)
            if env_path.exists(): return env_path
        app_env = self.get_app_env()
        is_local_env = app_env in [
            AppEnv.LOCAL,
            AppEnv.DEVELOPMENT,
            AppEnv.CICD,
            AppEnv.TEST,
        ] or os.environ.get('DISABLE_ENFORCE_ENV', 'false').lower() == 'true'
        configs_path = configs_path or self.config_path
        envs_path = configs_path.joinpath('envs')
        if name is not None:
            if envs_path.joinpath(f'{name}-{app_env.name}.env').exists():
                return envs_path.joinpath(f'{name}-{app_env.name}.env')
            if envs_path.joinpath(f'{name}.env').exists():
                return envs_path.joinpath(f'{name}.env')
            if required and not is_local_env: raise ValueError(f"Invalid app environment file: {name}")
        env_path = envs_path.joinpath(f'{app_env.name}.env')
        if env_path.exists(): return env_path
        if (is_local_env or not required) and allow_default:
            return envs_path.joinpath('default.env')
        return None


    def get_app_default_file(
        self,
        name: Optional[str] = None, 
        required: Optional[bool] = False, 
        suffix: Optional[str] = None,
        configs_path: Optional[Path] = None,
        env_var: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Retrieves the app environment file

        Only valid for local/dev environments
        """
        if env_var is not None and (env_val := os.getenv(env_var)):
            env_path = Path(env_val)
            if env_path.exists(): return env_path
        app_env = self.get_app_env()
        configs_path = configs_path or self.config_path
        defaults_path = configs_path.joinpath('defaults')
        suffix = suffix or 'json'
        suffix = suffix.lstrip('.')
        if name is not None:
            if defaults_path.joinpath(f'{name}-{app_env.name}.{suffix}').exists():
                return defaults_path.joinpath(f'{name}-{app_env.name}.{suffix}')
            if defaults_path.joinpath(f'{name}.{suffix}').exists():
                return defaults_path.joinpath(f'{name}.{suffix}')
            if required: raise ValueError(f"Invalid app environment file: {name}")
        env_path = defaults_path.joinpath(f'{app_env.name}.{suffix}')
        if env_path.exists(): return env_path
        default_path = defaults_path.joinpath(f'default.{suffix}')
        return default_path if default_path.exists() else None
    
    """
    Migrate from lazy utils
    """

    def get_kdb_session(
        self,
        name: Optional[str] = None,
        serializer: Optional[str] = 'json',
        **kwargs,
    ) -> 'KVDBSession':
        """
        Retrieves or Initializes a KVDB Session
        """
        name = name or self.module_name
        if name not in self._kdb_sessions:
            from kvdb import KVDBClient
            self._kdb_sessions[name] = KVDBClient.get_session(
                name = name,
                serializer = serializer,
                **kwargs,
            )
        return self._kdb_sessions[name]
    

    def get_persistent_dict(
        self,
        base_key: str,
        expiration: Optional[int] = None,
        aliases: Optional[List[str]] = None,
        **kwargs,
    ) -> 'PersistentDict':
        """
        Lazily initializes a persistent dict
        """
        if base_key not in self._persistent_dicts and base_key not in self._persistent_dict_aliases:
            url = kwargs.pop('url', None)
            session = self.get_kdb_session('persistence', serializer = None, url = url)
            self._persistent_dicts[base_key] = session.create_persistence(
                base_key = base_key,
                expiration = expiration,
                **kwargs,
            )
            if aliases:
                for alias in aliases:
                    self._persistent_dict_aliases[alias] = base_key
        elif base_key in self._persistent_dict_aliases:
            base_key = self._persistent_dict_aliases[base_key]
        return self._persistent_dicts[base_key]

    def update_client_registry(
        self,
        clients: Dict[str, str],
        kind: Optional[str] = 'client',
        state: Literal['global', 'local'] = 'global',
        include_kind: Optional[bool] = None,
    ) -> None:
        """
        Updates the client registry
        """
        from lazyops.libs.abcs.state.registry import update_client_registry_mapping
        include_kind = include_kind if include_kind is not None else self.include_kind_in_client_name
        if include_kind:
            prefix = f'{self.module_name}.{kind}' if kind else self.module_name
        else:
            prefix = self.module_name
        
        client_mapping = {
            (f'{prefix}.{k}' if prefix not in k else k): v for k, v in clients.items()
        }
        update_client_registry_mapping(client_mapping)
        if state == 'global':
            self._global_clients.update(clients)
        else:
            self._local_clients.update(clients)

    def get_client_registry_mapping(self) -> Dict[str, str]:
        """
        Retrieves the client registry mapping
        """
        return {
            **self._global_clients,
            **self._local_clients,
        }

    def register_client(
        self,
        client: 'ClientTypes',
        kind: Optional[str] = 'client',
        include_kind: Optional[bool] = None,
    ) -> None:
        """
        Registers a client
        """
        from lazyops.libs.abcs.state.registry import register_client
        include_kind = include_kind if include_kind is not None else self.include_kind_in_client_name
        if include_kind:
            kind = kind or getattr(client, 'kind', 'client')
            prefix = f'{self.module_name}.{kind}'
        else:
            prefix = self.module_name
        name = f'{prefix}.{client.name}'
        return register_client(client, name)
    

    def get_client(
        self, 
        name: str,
        state: Optional[Literal['global', 'local']] = None,
        kind: Optional[str] = 'client',
        include_kind: Optional[bool] = None,
        **kwargs,
    ) -> 'ClientTypes':
        """
        Retrieves a client
        """
        if state is None:
            state = 'global' if name in self._global_clients else 'local'
        
        from lazyops.libs.abcs.state.registry import (
            get_client as _get_client, 
            get_global_client as _get_global_client, 
        )
        method = _get_global_client if state == 'global' else _get_client
        include_kind = include_kind if include_kind is not None else self.include_kind_in_client_name
        if include_kind:
            prefix = f'{self.module_name}.{kind}' if kind else self.module_name
        else:
            prefix = self.module_name
        client_name = name
        if prefix not in client_name:
            client_name = f'{prefix}.{client_name}'
        if self.client_kwarg_function:
            if isinstance(self.client_kwarg_function, str):
                from lazyops.utils.lazy import lazy_import
                self.client_kwarg_function = lazy_import(self.client_kwarg_function)
            kwargs = self.client_kwarg_function(name, **kwargs)
        client = method(client_name, **kwargs)
        if self.client_hook_function:
            if isinstance(self.client_hook_function, str):
                from lazyops.utils.lazy import lazy_import
                self.client_hook_function = lazy_import(self.client_hook_function)
            self.client_hook_function(name, client)
        return client


    def update_component_client_registry(
        self,
        components: Dict[str, Union[str, Dict]],
        kind: Optional[str] = None,
        include_kind: Optional[bool] = None,
    ) -> None:
        """
        Updates the component client registry
        """
        from lazyops.libs.abcs.state.registry import update_client_registry_mapping
        from lazyops.libs.abcs.utils.helpers import flatten_dict_value 
        include_kind = include_kind if include_kind is not None else self.include_kind_in_component_name
        if include_kind:
            prefix = f'{self.module_name}.{kind}' if kind else self.module_name
        else:
            prefix = self.module_name

        mapping = flatten_dict_value(components, prefix)
        update_client_registry_mapping(mapping)
        self._component_client_registry.update(components)

    def get_component_client(
        self,
        name: str,
        *parts: str,
        kind: Optional[str] = None,
        include_kind: Optional[bool] = None,
    ) -> 'ClientTypes':
        """
        Gets a component client
        """
        from lazyops.libs.abcs.state.registry import get_client
        include_kind = include_kind if include_kind is not None else self.include_kind_in_component_name
        if include_kind: client_name = f'{self.module_name}.{kind}' if kind else self.module_name
        else: client_name = self.module_name
        if parts:
            parts = '.'.join(parts)
            client_name = f'{client_name}.{parts}'
        client_name = f'{client_name}.{name}'
        return get_client(client_name)
    
    def register_component_client(
        self,
        client: 'ClientTypes',
        *parts: str,
        kind: Optional[str] = None,
        include_kind: Optional[bool] = None,
    ):
        """
        Registers a component client
        """
        from lazyops.libs.abcs.state.registry import register_client
        include_kind = include_kind if include_kind is not None else self.include_kind_in_component_name
        kind = kind or getattr(client, 'kind', None)
        if include_kind: prefix = f'{self.module_name}.{kind}' if kind else self.module_name
        else: prefix = self.module_name
        if parts:
            parts = '.'.join(parts)
            prefix = f'{prefix}.{parts}'
        client_name = f'{prefix}.{client.name}'
        return register_client(client, client_name)
        
    def update_component_schema_registry(
        self,
        components: Dict[str, Union[str, Dict]],
        kind: Optional[str] = None,
        include_kind: Optional[bool] = None,
    ) -> None:
        """
        Updates the component schema registry
        """
        from lazyops.libs.abcs.utils.helpers import flatten_dict_value 
        include_kind = include_kind if include_kind is not None else self.include_kind_in_component_name
        if include_kind:
            prefix = f'{self.module_name}.{kind}' if kind else self.module_name
        else:
            prefix = self.module_name
        
        mapping = flatten_dict_value(components, prefix)
        self._component_schema_registry.update(mapping)

    def get_component_schema(
        self,
        name: str,
        *parts: str,
        kind: Optional[str] = None,
        include_kind: Optional[bool] = None,
    ) -> Type['ComponentSchemaT']:
        """
        Gets a component schema
        """
        include_kind = include_kind if include_kind is not None else self.include_kind_in_component_name
        if include_kind: schema_name = f'{self.module_name}.{kind}' if kind else self.module_name
        else: schema_name = self.module_name
        if parts:
            parts = '.'.join(parts)
            schema_name = f'{schema_name}.{parts}'
        schema_name = f'{schema_name}.{name}'
        if schema_name not in self._component_schema_registry:
            raise ValueError(f"Invalid component schema: {schema_name}")
        schema = self._component_schema_registry[schema_name]
        if isinstance(schema, str):
            from lazyops.utils.lazy import lazy_import
            schema = lazy_import(schema)
        return schema
    
    def get_worker(
        self,
        name: Optional[str] = 'worker',
        state: Optional[Literal['global', 'local']] = None,
        kind: Optional[str] = 'client',
        include_kind: Optional[bool] = None,
        **kwargs,
    ) -> 'TaskWorkerT':
        """
        Retrieves the Worker
        """
        return self.get_client(name, state = state, kind = kind, include_kind = include_kind, **kwargs)
        

    @overload
    def get_j2_ctx(
        self,
        path: Union[str, Path],
        name: Optional[str] = None,
        enable_async: Optional[bool] = False,
        comment_start_string: Optional[str] = None,
        comment_end_string: Optional[str] = None,
        **kwargs,
    ) -> 'jinja2.Environment':
        """
        Creates a jinja2 context

        path can be relative to the module_dir or absolute
        """
        ...


    def get_j2_ctx(
        self,
        
        path: Union[str, Path],
        name: Optional[str] = None,
        enable_async: Optional[bool] = False,
        **kwargs,
    ) -> 'jinja2.Environment':
        """
        Creates a jinja2 context

        path can be relative to the module_dir or absolute
        """
        base_ctx = self.j2_actxs if enable_async else self.j2_ctxs
        name = name or self.module_name
        if name not in base_ctx:
            import jinja2
            if isinstance(path, str):
                if path.startswith('/'):
                    path = Path(path)
                else:
                    path = self.settings.module_path.joinpath(path)
            self.logger.info(f"Jinja2 Path: {path} for {name}")
            base_ctx[name] = jinja2.Environment(
                loader = jinja2.FileSystemLoader(path),
                enable_async = enable_async,
                **kwargs,
            )
        return base_ctx[name]

    def lazy_import(self, dotted_path: str, **kwargs) -> Any:
        """
        Lazy imports a module
        """
        from lazyops.utils.lazy import lazy_import
        return lazy_import(dotted_path, **kwargs)


# class ApplicationContextManagerClass(abc.ABC):


@proxied
class ApplicationContextManager(abc.ABC):

    """
    The context manager for the app context
    """

    def __init__(self, *args, **kwargs):

        """
        Creates the context manager
        """
        self.ctxs: Dict[str, ApplicationContext] = {}
        self._global_ctx = None
    
    @property
    def global_ctx(self): # -> 'GlobalContextClass':
        """
        Returns the global context
        """
        if self._global_ctx is None:
            from ..state import GlobalContext
            self._global_ctx = GlobalContext
        return self._global_ctx

    def init_ctx(self, module_name: str, *args, **kwargs) -> ApplicationContext:
        """
        Initializes the app context
        """
        if module_name not in self.ctxs:
            self.ctxs[module_name] = ApplicationContext(module_name, *args, global_ctx = self.global_ctx, **kwargs)
        return self.ctxs[module_name]
    
    def get_ctx(self, module_name: str, *args, **kwargs) -> ApplicationContext:
        """
        Retrieves the app context
        """
        if module_name not in self.ctxs:
            return self.init_ctx(module_name, *args, **kwargs)
        return self.ctxs[module_name]
    
    def __getitem__(self, module_name: str) -> ApplicationContext:
        """
        Retrieves the app context
        """
        return self.get_ctx(module_name)
    


# ApplicationContextManager: 'ApplicationContextManagerClass' = ProxyObject(
#     ApplicationContextManagerClass
# )