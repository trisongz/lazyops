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
from lazyops.libs.proxyobj import ProxyObject
from typing import Optional, Dict, Any, List, Union, Type, Callable, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger
    from lazyops.libs.fastapi_utils.types.persistence import TemporaryData
    from lazyops.libs.fastapi_utils.types.state import AppState
    from ..state import GlobalContext, GlobalContextClass
    from .base import AppSettings
    # from lazyops.libs.fastapi_utils import GlobalContext


AppSettingsT = TypeVar('AppSettingsT', bound='AppSettings')

class ApplicationContext(abc.ABC):
    """
    Contains the app context
    """

    def __init__(
        self,
        module_name: str,
        ingress_domain: str,
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
        self._settings: Optional['AppSettingsT'] = None
        self._state: Optional['AppState'] = None
        self._logger: Optional['Logger'] = None
        self.on_close_funcs: List[Callable] = []


    @property
    def app_env(self) -> AppEnv:
        """
        Retrieves the app environment
        """
        if self._app_env is None: self._app_env = self.get_app_env()
        return self._app_env
    
    @property
    def temp_data(self) -> 'TemporaryData':
        """
        Retrieves the temporary data
        """
        if self._temp_data is None:
            from lazyops.libs.fastapi_utils.types.persistence import TemporaryData
            self._temp_data = TemporaryData.from_module(self.module_name)
        return self._temp_data
    
    @property
    def settings(self) -> AppSettingsT:
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
            from lazyops.libs.fastapi_utils.types.state import AppState
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
    

    def register_settings(self, settings: AppSettingsT) -> None:
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
        module_name = module_name or self.env_var_name
        for key in {
            "SERVER_ENV",
            f"{module_name}_ENV",
            "APP_ENV",
            "ENVIRONMENT",
        }:
            if env_value := os.getenv(key):
                return AppEnv.from_env(env_value)

        from lazyops.utils.system import is_in_kubernetes, get_host_name
        if is_in_kubernetes():
            # Name should be
            # scout-<service>-<index>
            # or 
            # scout-<service>-<env>-<index>
            parts = get_host_name().split("-")
            return AppEnv.from_env(parts[2]) if len(parts) > 3 else AppEnv.PRODUCTION
        
        return AppEnv.LOCAL
    

    def get_app_ingress(
        self,
        app_host: Optional[str] = None,
        app_port: Optional[int] = None,
    ) -> str:
        """
        Retrieves the app ingress
        """
        if self.app_env.is_local:
            app_host = app_host or "localhost"
            app_port = app_port or 8085
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
    ) -> Optional[Path]:
        """
        Retrieves the app environment file

        Only valid for local/dev environments
        """
        app_env = self.get_app_env()
        is_local_env = app_env in [
            AppEnv.LOCAL,
            AppEnv.DEVELOPMENT,
            AppEnv.CICD,
        ]
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
    ) -> Optional[Path]:
        """
        Retrieves the app environment file

        Only valid for local/dev environments
        """
        app_env = self.get_app_env()
        configs_path = configs_path or self.config_path
        defaults_path = configs_path.joinpath('defaults')
        suffix = suffix or 'json'
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



class ApplicationContextManagerClass(abc.ABC):

    """
    The context manager for the app context
    """

    def __init__(self, *args, **kwargs):

        """
        Creates the context manager
        """
        self.ctxs: Dict[str, ApplicationContext] = {}
        self._global_ctx: Optional['GlobalContextClass'] = None
    
    @property
    def global_ctx(self) -> 'GlobalContextClass':
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
    


ApplicationContextManager: 'ApplicationContextManagerClass' = ProxyObject(
    ApplicationContextManagerClass
)