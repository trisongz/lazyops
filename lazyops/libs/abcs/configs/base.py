from __future__ import annotations

"""
The Base Configuration Schema
"""

import os
import contextlib
from enum import Enum
from pathlib import Path

from pydantic import model_validator, PrivateAttr
from lazyops.utils.logs import Logger, null_logger
from lazyops.imports._pydantic import BaseAppSettings, BaseModel
from lazyops.libs.abcs.state import GlobalContext
from lazyops.libs.abcs.types.persistence import TemporaryData
from typing import List, Optional, Dict, Any, Callable, Union, Type, TYPE_CHECKING
from .types import AppEnv, get_app_env

if TYPE_CHECKING:
    from .ctx import ApplicationContext
    from lazyops.utils.logs import Logger


class AppSettings(BaseAppSettings):
    """
    App Settings
    """

    ingress_base: Optional[str] = None
    ingress_domain: Optional[str] = None
    debug_enabled: Optional[bool] = False
    app_env: Optional[AppEnv] = None

    # _extra: Dict[str, Any] = PrivateAttr(default_factory=dict)

    if TYPE_CHECKING:
        ctx: ApplicationContext
    else:
        ctx: Optional[Any] = None
    
    @model_validator(mode = 'after')
    def validate_app_settings(self):
        """
        Validates the app environment
        """
        from .ctx import ApplicationContextManager
        self.ctx = ApplicationContextManager.get_ctx(
            self.module_name,
            ingress_domain = self.ingress_domain,
            ingress_base = self.ingress_base,
        )
        self.app_env = self.ctx.app_env
        if self.__class__.__name__.lower() == f'{self.__module__}settings':
            self.ctx.register_settings(self)
            from .lazy import register_module_settings
            register_module_settings(self.__module__, self)
        return self
    
    # @property
    # def ctx(self) -> 'ApplicationContext':
    #     """
    #     Returns the application context
    #     """
    #     return self._extra.get('ctx')

    # @ctx.setter
    # def ctx(self, value: 'ApplicationContext'):
    #     """
    #     Sets the application context
    #     """
    #     self._extra['ctx'] = value


    @property
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        return self.ctx.logger
    
    @property
    def null_logger(self) -> 'Logger':
        """
        Returns the null logger
        """
        return null_logger
    
    @property
    def autologger(self) -> 'Logger':
        """
        Returns the auto logger
        """
        return self.logger if (self.is_development_env or self.debug_enabled) else self.null_logger
    
    @property
    def temp_data(self) -> 'TemporaryData':
        """
        Retrieves the temporary data
        """
        return self.ctx.temp_data
    
    @property
    def config_path(self) -> Path:
        """
        Retrieves the config path
        """
        return self.ctx.config_path

    @property
    def is_leader_process(self) -> bool:
        """
        Returns if this is the leader process
        """
        return self.ctx.is_leader_process
    

    @property
    def is_primary_server_process(self) -> bool:
        """
        Returns if this is the primary server process
        """
        return self.ctx.is_primary_server_process
    
    @property
    def is_primary_node(self) -> bool:
        """
        Returns whether or not this is the primary node
        """
        return self.host_name[-1] == '0' if self.in_k8s else True

    @property
    def is_local_env(self) -> bool:
        """
        Returns whether the environment is development
        """
        return self.app_env in [AppEnv.DEVELOPMENT, AppEnv.LOCAL] and not self.in_k8s
    
    @property
    def is_production_env(self) -> bool:
        """
        Returns whether the environment is production
        """
        return self.app_env == AppEnv.PRODUCTION and self.in_k8s

    @property
    def is_development_env(self) -> bool:
        """
        Returns whether the environment is development
        """
        return self.app_env in [AppEnv.DEVELOPMENT, AppEnv.LOCAL, AppEnv.CICD, AppEnv.STAGING, AppEnv.TEST]
    
    def set_app_env(self, env: AppEnv) -> None:
        """
        Sets the app environment
        """
        self.app_env = self.app_env.from_env(env)
        self.ctx._app_env = self.app_env

    def get_assets(
        self, 
        *path_parts,
        load_file: Optional[bool] = False,
        loader: Optional[Callable] = None,
        **kwargs
    ) -> Union[Path, Any, List[Path], List[Any], Dict[str, Path], Dict[str, Any]]:
        """
        Retrieves the assets

        args:
            path_parts: path parts to the assets directory (default: [])
            load_file: load the file (default: False)
            loader: loader function to use (default: None)
            **kwargs: additional arguments to pass to `get_module_assets`
        """
        return self.ctx.get_assets(*path_parts, load_file = load_file, loader = loader, **kwargs)
    
    def import_assets(
        self, 
        *path_parts,
        model: Optional[Type['BaseModel']] = None,
        load_file: Optional[bool] = False,
        **kwargs
    ) -> Union[Dict[str, Any], List[Any]]:
        """
        Import assets from a module.

        args:
            path_parts: path parts to the assets directory (default: [])
            model: model to parse the assets with (default: None)
            load_file: load the file (default: False)
            **kwargs: additional arguments to pass to import_module_assets
        """
        return self.ctx.import_assets(*path_parts, model = model, load_file = load_file, **kwargs)
    

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
        return self.ctx.get_app_env_file(
            name = name, 
            required = required, 
            allow_default = allow_default, 
            configs_path = configs_path,
            env_var = env_var,
        )
    

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
        return self.ctx.get_app_default_file(
            name = name, 
            required = required, 
            suffix = suffix, 
            configs_path = configs_path,
            env_var = env_var,
        )

        
    def get_app_ingress(
        self,
        app_host: Optional[str] = None,
        app_port: Optional[int] = None,
    ) -> str:
        """
        Retrieves the app ingress
        """
        return self.ctx.get_app_ingress(app_host = app_host, app_port = app_port)

    @property
    def global_ctx(self) -> GlobalContext:
        """
        Returns the global context
        """
        return GlobalContext
    
    def register_on_close(self, func: Callable, *args, **kwargs):
        """
        Registers a function to be called on close
        """
        self.global_ctx.register_on_close(func, *args, **kwargs)

    

