from __future__ import annotations

"""
Pydantic Settings with additional helpers
"""
import os
import inspect
import pkg_resources
from pathlib import Path
from .base import (
    Field,
    BaseSettings as _BaseSettings,
    PYDANTIC_VERSION,
    get_pydantic_dict,
)
from .properties import eproperty
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if PYDANTIC_VERSION == 2:
    from pydantic import PrivateAttr

if TYPE_CHECKING:
    from lzo.types import AppEnv

class BaseSettings(_BaseSettings):
    """
    Base Settings
    """

    if PYDANTIC_VERSION == 2:
        _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)
    else:
        _extra: Dict[str, Any] = Field(default_factory = dict, exclude = True, hidden = True)

    
    class Config:
        env_prefix: str = ""
        case_sensitive: bool = False
        arbitrary_types_allowed: bool = True


    @eproperty
    def module_path(self) -> Path:
        """
        Gets the module root path

        https://stackoverflow.com/questions/25389095/python-get-path-of-root-project-structure
        """
        p = Path(pkg_resources.get_distribution(self.module_name).location)
        if 'src' in p.name and p.joinpath(self.module_name).exists():
            p = p.joinpath(self.module_name)
        elif p.joinpath('src').exists() and p.joinpath('src', self.module_name).exists():
            p = p.joinpath('src', self.module_name)
        return p
    
    @eproperty
    def module_config_path(self) -> Path:
        """
        Returns the config module path
        """
        return Path(inspect.getfile(self.__class__)).parent
    
    @eproperty
    def module_name(self) -> str:
        """
        Returns the module name
        """
        return self.__class__.__module__.split(".")[0]
    
    @eproperty
    def module_version(self) -> str:
        """
        Returns the module version
        """
        return pkg_resources.get_distribution(self.module_name).version
    
    @eproperty
    def module_pkg_name(self) -> str:
        """
        Returns the module pkg name
        
        {pkg}/src   -> src
        {pkg}/{pkg} -> {pkg}
        """
        config_path = self.module_config_path.as_posix()
        module_path = self.module_path.as_posix()
        return config_path.replace(module_path, "").strip().split("/", 2)[1]

    @eproperty
    def in_k8s(self) -> bool:
        """
        Returns whether the app is running in kubernetes
        """
        from lzo.utils.system import is_in_kubernetes
        return is_in_kubernetes()
    
    @eproperty
    def host_name(self) -> str:
        """
        Returns the hostname
        """
        from lzo.utils.system import get_host_name
        return get_host_name()

    def update_config(self, **kwargs):
        """
        Update the config for the other settings
        """
        for k, v in kwargs.items():
            if not hasattr(self, k): continue
            if isinstance(getattr(self, k), Path):
                setattr(self, k, Path(v))
            elif isinstance(getattr(self, k), self.__class__):
                val = getattr(self, k)
                if hasattr(val, 'update_config'):
                    val.update_config(**v)
                else: val = val.__class__(**v)
                setattr(self, k, val)
            else: 
                setattr(self, k, v)


    def set_envvars(self):
        """
        Update the Env variables for the current session
        """
        data = get_pydantic_dict(self, exclude_none=True)
        for k, v in data.items():
            if isinstance(v, BaseSettings):
                v.set_envvars()
            else:
                os.environ[self.Config.env_prefix + k.upper()] = str(v)
    

    def get(self, name, default: Any = None):
        """
        Get an attribute from the model
        """
        return getattr(self, name, default)


    @classmethod
    def _fetch_app_env(cls, module: Optional[str] = None) -> Optional['AppEnv']:
        """
        Fetches the App Env
        """
        if module is None: module = cls.__module__.split('.')[0]
        from lzo.types import AppEnv
        return AppEnv.from_module_name(module)
