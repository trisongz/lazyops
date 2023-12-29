"""
The Base Configuration Schema
"""

import os
import functools
from enum import Enum
from pathlib import Path

from lazyops.types.models import BaseSettings, pre_root_validator, validator
from lazyops.imports._pydantic import BaseAppSettings, BaseModel
from lazyops.utils.system import is_in_kubernetes, get_host_name
from lazyops.utils.assets import create_get_assets_wrapper, create_import_assets_wrapper
from lazyops.libs.fastapi_utils import GlobalContext
from lazyops.libs.fastapi_utils.types.persistence import TemporaryData
from typing import List, Optional, Dict, Any, Callable, Union, Type, TYPE_CHECKING


_temp_datas: Dict[str, TemporaryData] = {}
_get_assets_wrappers: Dict[str, Callable[..., Union[Dict[str, Any], List[Any]]]] = {}
_import_assets_wrappers: Dict[str, Callable[..., Union[Path, Any, List[Path], List[Any], Dict[str, Path], Dict[str, Any]]]] = {}

def get_temp_data(name: str) -> TemporaryData:
    """
    Returns a temporary data object
    """
    global _temp_datas
    if name not in _temp_datas:
        _temp_datas[name] = TemporaryData.from_module(name)
    return _temp_datas[name]

def get_assets_func(module_name: str, asset_path: Optional[str] = "assets") -> Callable[..., Union[Dict[str, Any], List[Any]]]:
    """
    Returns the get assets function
    """
    global _get_assets_wrappers
    if module_name not in _get_assets_wrappers:
        _get_assets_wrappers[module_name] = create_get_assets_wrapper(module_name, asset_path)
    return _get_assets_wrappers[module_name]

def import_assets_func(module_name: str, asset_path: Optional[str] = "assets") -> Callable[..., Union[Path, Any, List[Path], List[Any], Dict[str, Path], Dict[str, Any]]]:
    """
    Returns the import assets function
    """
    global _import_assets_wrappers
    if module_name not in _import_assets_wrappers:
        _import_assets_wrappers[module_name] = create_import_assets_wrapper(module_name, asset_path)
    return _import_assets_wrappers[module_name]


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
        if "cicd" in env_value or "ci/cd" in env_value:
            return cls.CICD
        if "prod" in env_value:
            return cls.PRODUCTION
        if "dev" in env_value:
            return cls.DEVELOPMENT
        if "staging" in env_value:
            return cls.STAGING
        if "local" in env_value:
            return cls.LOCAL
        raise ValueError(f"Invalid app environment: {env_value} ({type(env_value)})")
    
    def __eq__(self, other: Any) -> bool:
        """
        Equality operator
        """
        if isinstance(other, str):
            return self.value == other.lower()
        return self.value == other.value if isinstance(other, AppEnv) else False

    @property
    def is_devel(self) -> bool:
        """
        Returns True if the app environment is development
        """
        return self in [
            AppEnv.LOCAL,
            AppEnv.CICD,
            AppEnv.DEVELOPMENT
        ]

    @property
    def is_local(self) -> bool:
        """
        Returns True if the app environment is local
        """
        return self in [
            AppEnv.LOCAL,
            AppEnv.CICD,
        ]

    @property
    def name(self) -> str:
        """
        Returns the name in lower
        """
        return self.value.lower()


def get_app_env(name: Optional[str] = None) -> AppEnv:
    """
    Retrieves the app environment
    """
    for key in {
        "SERVER_ENV",
        f"{name.upper()}_ENV" if name is not None else "APP_SERVER_ENV",
        "APP_ENV",
        "ENVIRONMENT",
    }:
        if env_value := os.getenv(key):
            return AppEnv.from_env(env_value)

    if is_in_kubernetes():
        parts = get_host_name().split("-")
        return AppEnv.from_env(parts[2]) if len(parts) > 3 else AppEnv.PRODUCTION
    return AppEnv.LOCAL

def get_app_ingress(
    module_name: str,
    base_domain: str,
    app_env: AppEnv,
    app_host: Optional[str] = None,
    app_port: Optional[int] = None,
    
) -> str:
    """
    Retrieves the app ingress
    """
    if app_env.is_local:
        app_host = app_host or "localhost"
        app_port = app_port or 8080
        return f"http://{app_host}:{app_port}"
    if app_env == AppEnv.DEVELOPMENT:
        return f"https://{module_name}-develop.{base_domain}"
    if app_env == AppEnv.STAGING:
        return f"https://{module_name}-staging.{base_domain}"
    if app_env == AppEnv.PRODUCTION:
        return f"https://{module_name}.{base_domain}"
    raise ValueError(f"Invalid app environment: {app_env}")



def get_app_env_file(
    configs_path: Path,
    name: Optional[str] = None, 
    required: Optional[bool] = False,
    module_name: Optional[str] = None,
) -> Optional[Path]:
    """
    Retrieves the app environment file

    Only valid for local/dev environments
    """
    app_env = get_app_env(module_name)
    is_local_env = app_env in [
        AppEnv.LOCAL,
        AppEnv.DEVELOPMENT,
        AppEnv.CICD,
    ]
    envs_path = configs_path.joinpath('envs')
    if name is not None:
        if envs_path.joinpath(f'{name}-{app_env.name}.env').exists():
            return envs_path.joinpath(f'{name}-{app_env.name}.env')
        if envs_path.joinpath(f'{name}.env').exists():
            return envs_path.joinpath(f'{name}.env')
        if required and not is_local_env: raise ValueError(f"Invalid app environment file: {name}")
    env_path = envs_path.joinpath(f'{app_env.name}.env')
    if env_path.exists(): return env_path
    if is_local_env or not required:
        return envs_path.joinpath('default.env')
    return None

def get_app_default_file(
    configs_path: Path,
    name: Optional[str] = None, 
    required: Optional[bool] = False, 
    suffix: Optional[str] = None,
    module_name: Optional[str] = None,
) -> Optional[Path]:
    """
    Retrieves the app environment file

    Only valid for local/dev environments
    """
    app_env = get_app_env(module_name)
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

def create_get_app_env_file(
    configs_path: Path,
    module_name: Optional[str] = None,
) -> Callable[[Optional[str], Optional[bool]], Optional[Path]]:
    """
    Creates a get_app_env_file wrapper
    """
    kwargs = {}
    if module_name is not None: kwargs["module_name"] = module_name
    return functools.partial(get_app_env_file, configs_path, **kwargs)

def create_get_app_default_file(
    configs_path: Path,
    module_name: Optional[str] = None,
) -> Callable[[Optional[str], Optional[bool], Optional[str]], Optional[Path]]:
    """
    Creates a get_app_default_file wrapper
    """
    kwargs = {}
    if module_name is not None: kwargs["module_name"] = module_name
    return functools.partial(get_app_default_file, configs_path, **kwargs)

def create_get_app_ingress(
    module_name: str,
    base_domain: str,
) -> Callable[[], str]:
    """
    Creates a get_app_ingress wrapper
    """
    return functools.partial(
        get_app_ingress,
        module_name,
        base_domain,
    )

def create_get_app_env(
    name: str,
) -> Callable[[], AppEnv]:
    """
    Creates a get_app_env wrapper
    """
    return functools.partial(
        get_app_env,
        name,
    )


class AppSettings(BaseAppSettings):
    """
    Custom App Settings
    """

    app_env: Optional[AppEnv] = None 

    @validator('app_env', pre=True)
    def validate_app_env(cls, value: Optional[Any]) -> Any:
        """
        Validates the app environment
        """
        if value is None:
            return get_app_env(cls.__module__.split(".")[0])
        return AppEnv.from_env(value) if isinstance(value, str) else value

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
        get_assets = get_assets_func(self.module_name, "assets")
        return get_assets(*path_parts, load_file = load_file, loader = loader, **kwargs)
    
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
        import_assets = import_assets_func(self.module_name, "assets")
        return import_assets(*path_parts, model = model, load_file = load_file, **kwargs)


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