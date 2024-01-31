"""
The Base Configuration Schema
"""

import os
import contextlib
from enum import Enum
from pathlib import Path

from pydantic import model_validator
from lazyops.imports._pydantic import BaseAppSettings, BaseModel
from lazyops.libs.fastapi_utils import GlobalContext
from lazyops.libs.fastapi_utils.types.persistence import TemporaryData
from typing import List, Optional, Dict, Any, Callable, Union, Type, TYPE_CHECKING

class AppEnv(str, Enum):
    CICD = "cicd"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"

    @classmethod
    def from_env(cls, env_value: str) -> "AppEnv":
        """
        Get the app environment from the environment variables
        """
        env_value = env_value.lower()
        if "cicd" in env_value or "ci/cd" in env_value: return cls.CICD
        if "prod" in env_value: return cls.PRODUCTION
        if "dev" in env_value: return cls.DEVELOPMENT
        if "staging" in env_value: return cls.STAGING
        if "local" in env_value: return cls.LOCAL
        raise ValueError(f"Invalid app environment: {env_value} ({type(env_value)})")
    
    def __eq__(self, other: Any) -> bool:
        """
        Equality operator
        """
        if isinstance(other, str): return self.value == other.lower()
        return self.value == other.value if isinstance(other, AppEnv) else False

    @property
    def is_devel(self) -> bool:
        """
        Returns True if the app environment is development
        """
        return self in [AppEnv.LOCAL, AppEnv.CICD, AppEnv.DEVELOPMENT]

    @property
    def is_local(self) -> bool:
        """
        Returns True if the app environment is local
        """
        return self in [AppEnv.LOCAL, AppEnv.CICD]

    @property
    def name(self) -> str:
        """
        Returns the name in lower
        """
        return self.value.lower()
    


def get_app_env(
    module_name: str,
) -> AppEnv:
    """
    Retrieves the app environment
    """
    module_name = module_name.replace(".", "_").upper()
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



class AppSettings(BaseAppSettings):
    """
    App Settings
    """

    app_env: Optional[AppEnv] = None
    temp_data: Optional[TemporaryData] = None
    get_assets_func: Optional[Callable] = None
    import_assets_func: Optional[Callable] = None
    config_path: Optional[Path] = None

    
    @model_validator(mode = 'after')
    def validate_app_env(self):
        """
        Validates the app environment
        """
        from lazyops.utils.assets import create_get_assets_wrapper, create_import_assets_wrapper, get_module_assets_path
        if self.app_env is None: self.app_env = get_app_env(self.__module__)
        if self.config_path is None: 
            try:
                self.config_path = get_module_assets_path(self.__module__, 'configs')
            except Exception as e:
                self.config_path = Path.cwd()
        if self.get_assets_func is None:
            with contextlib.suppress(Exception):
                self.get_assets_func = create_get_assets_wrapper(self.__module__, 'assets')
        if self.import_assets_func is None:
            with contextlib.suppress(Exception):
                self.import_assets_func = create_import_assets_wrapper(self.__module__, 'assets')
        if self.temp_data is None: 
            with contextlib.suppress(Exception):
                self.temp_data = TemporaryData.from_module(self.__module__)
        if self.__class__.__name__.lower() == f'{self.__module__}settings':
            from .lazy import register_module_settings
            register_module_settings(self.__module__, self)
        return self

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
        return self.get_assets_func(*path_parts, load_file = load_file, loader = loader, **kwargs)
    
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
        return self.import_assets_func(*path_parts, model = model, load_file = load_file, **kwargs)


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
        return self.app_env in [AppEnv.DEVELOPMENT, AppEnv.LOCAL, AppEnv.CICD]