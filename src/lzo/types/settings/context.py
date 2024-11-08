from __future__ import annotations

"""
Settings Context - Usually used for the App Settings
"""

import os
import abc
import contextlib
import multiprocessing
from pathlib import Path
from lzl.proxied import ProxyObject
from lzl.types import BaseModel, AppEnv, eproperty
from typing import Optional, Dict, Any, List, Union, Type, Callable, TypeVar, Literal, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from kvdb import KVDBSession
    from lzo.types.base import RegisteredSettings as BaseSettings
    from lzo.registry.clients import RClientT
    from lzl.io import TemporaryData, PersistentDict
    from .state import AppState


class AppContext(abc.ABC):
    """
    Contains the application context
    """

    _extra: Dict[str, Any] = {}

    def __init__(
        self,
        module_name: str,
        ingress_domain: Optional[str] = None,
        ingress_base: Optional[Union[str, bool]] = None,
        config_path: Optional[Path] = None,
        assets_dir: Optional[str] = 'assets',
        **kwargs,
    ):
        """
        Creates the app settings context
        """

        self.module_name = module_name
        self.app_env_var_name = self.module_name.replace(".", "-").replace("_", "-").lower()
        self.env_var_name = self.module_name.replace(".", "_").upper()
        self.is_app_module = '__main__' not in self.module_name
        if ingress_base is False:
            self.ingress_base = None
        else:
            self.ingress_base = ingress_base or self.module_name
        self.ingress_domain = ingress_domain
        if self.is_app_module:
            from lzo.utils.assets import get_module_assets_path
            from lzo.utils.assets import create_get_assets_wrapper, create_import_assets_wrapper
            if config_path is None:
                try:
                    config_path = get_module_assets_path(self.module_name, 'configs')
                except Exception as e:
                    config_path = Path.cwd()
            self.import_assets = create_import_assets_wrapper(self.module_name, assets_dir)
            self.get_assets = create_get_assets_wrapper(self.module_name, assets_dir)
        
        self.config_path = config_path

        self._kdbs: Dict[str, 'KVDBSession'] = {}
        self._pdicts: Dict[str, 'PersistentDict'] = {}
        self._pdict_aliases: Dict[str, str] = {}

    """
    App Environments and Ingress
    """

    @eproperty
    def app_env(self) -> AppEnv:
        """
        Retrieves the app environment
        """
        return self.get_app_env()
    
    @eproperty
    def temp_data(self) -> 'TemporaryData':
        """
        Retrieves the temporary data
        """
        from lzl.io.persistence import TemporaryData
        return TemporaryData.from_module(self.module_name)
    
    @eproperty
    def settings(self) -> 'BaseSettings':
        """
        Returns the settings
        """
        from lzo.registry.settings import get_app_settings
        return get_app_settings(self.module_name)

    @eproperty
    def state(self) -> 'AppState':
        """
        Returns the state
        """
        from .state import AppState
        _state = AppState()
        _state.bind_settings(self.settings)
        return _state
    
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
    

    def get_app_env(self, module_name: Optional[str] = None) -> AppEnv:
        """
        Retrieves the app environment
        """
        module_name = (module_name or self.env_var_name).upper()
        return AppEnv.from_module_name(module_name)

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
            if not self.ingress_base: return f"https://develop.{self.ingress_domain}"
            return f"https://{self.ingress_base}-develop.{self.ingress_domain}"
        if self.app_env == AppEnv.STAGING:
            if not self.ingress_base: return f"https://staging.{self.ingress_domain}"
            return f"https://{self.ingress_base}-staging.{self.ingress_domain}"
        if self.app_env == AppEnv.PRODUCTION:
            if not self.ingress_base: return f"https://{self.ingress_domain}"
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
            if env_path.exists(): 
                return env_path
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

    def load_app_env_file(
        self,
        name: Optional[str] = None, 
        required: Optional[bool] = False, 
        allow_default: Optional[bool] = True,
        configs_path: Optional[Path] = None,
        env_var: Optional[str] = None,

        override: Optional[bool] = True,
    ) -> Optional[Path]:
        """
        Retrieves the app environment file and loads the variables

        Only valid for local/dev environments
        """
        env_path = self.get_app_env_file(name = name, required = required, allow_default = allow_default, configs_path = configs_path, env_var = env_var)
        if env_path is None: return None
        import dotenv
        dotenv.load_dotenv(dotenv_path = env_path.as_posix(), override = override)
        return env_path
    
    def register_client(
        self,
        client: 'RClientT',
        **kwargs,
    ) -> None:
        """
        Registers a client
        """
        from lzo.registry.clients import register_client
        register_client(client, **kwargs)

    
    def get_client(
        self, 
        name: str,
        module: Optional[str] = None,
        **kwargs,
    ) -> 'RClientT':
        """
        Retrieves a client
        """
        module = module or self.module_name
        from lzo.registry.clients import get_app_client
        return get_app_client(name, module = module, **kwargs)


    def get_kdb(
        self,
        name: Optional[str] = None,
        serializer: Optional[str] = 'json',
        **kwargs,
    ) -> 'KVDBSession':
        """
        Retrieves or Initializes a KVDB Session
        """
        name = name or self.module_name
        if name not in self._kdbs:
            from kvdb import KVDBClient
            self._kdbs[name] = KVDBClient.get_session(
                name = name,
                serializer = serializer,
                **kwargs,
            )
        return self._kdbs[name]
    
    def get_pdict(
        self,
        base_key: str,
        expiration: Optional[int] = None,
        aliases: Optional[List[str]] = None,
        backend_type: Optional[str] = None,
        **kwargs,
    ) -> 'PersistentDict':
        """
        Lazily initializes a persistent dict
        """
        if base_key not in self._pdicts and base_key not in self._pdict_aliases:
            if backend_type is not None:
                from lzl.io.persistence import PersistentDict as PDict
                self._pdicts[base_key] = PDict(
                    base_key = base_key, 
                    backend_type = backend_type, 
                    **kwargs
                )
            else:
                url = kwargs.pop('url', None)
                session = self.get_kdb('persistence', serializer = None, url = url)
                self._pdicts[base_key] = session.create_persistence(
                    base_key = base_key,
                    expiration = expiration,
                    **kwargs,
                )
            if aliases:
                for alias in aliases:
                    self._pdict_aliases[alias] = base_key
        elif base_key in self._pdict_aliases:
            base_key = self._pdict_aliases[base_key]
        return self._pdicts[base_key]

class AppContextManagerObject(abc.ABC):
    """
    Manages application contexts
    """

    _extra: Dict[str, Any] = {}

    def __init__(self, *args, **kwargs):
        """
        Creates the context manager
        """
        self.ctxs: Dict[str, AppContext] = {}
        self._gctx: Optional[AppContext] = None

    def init_ctx(self, module_name: str, *args, **kwargs) -> AppContext:
        """
        Initializes the app context
        """
        if module_name not in self.ctxs:
            self.ctxs[module_name] = AppContext(module_name, *args, **kwargs)
        return self.ctxs[module_name]
    
    def get_ctx(self, module_name: str, *args, **kwargs) -> AppContext:
        """
        Retrieves the app context
        """
        if module_name not in self.ctxs:
            return self.init_ctx(module_name, *args, **kwargs)
        return self.ctxs[module_name]
    
    def __getitem__(self, module_name: str) -> AppContext:
        """
        Gets the app context
        """
        return self.get_ctx(module_name)


AppContextManager: AppContextManagerObject = ProxyObject(AppContextManagerObject)

