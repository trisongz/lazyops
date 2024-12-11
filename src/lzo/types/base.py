from __future__ import annotations
from typing_extensions import Unpack

"""
Common Types
"""
import abc
import inspect
from pathlib import Path
from pydantic import PrivateAttr
from lzl.types import (
    BaseSettings as _BaseSettings, 
    BaseModel as _BaseModel,
    Field,
    validator,
    root_validator,
    pre_root_validator,
    Field,
    ConfigDict,
    model_validator,
    field_validator,
    get_schema_extra,
    get_pydantic_field_names,
    ByteSize,
    eproperty,
    PYDANTIC_VERSION,
)
from .common.appenv import AppEnv, get_app_env
from typing import Optional, Dict, Any, List, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from lzl.logging import Logger, NullLogger
    from lzo.types.settings.context import AppContext
    # from pydantic.main import Model

Model = TypeVar('Model', bound='BaseModel')
    
class Registered(abc.ABC):
    """
    Registers this as the module settings
    """
    _rmodule: Optional[str] = None
    _rsubmodule: Optional[str] = None
    _rxtra: Dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs: ConfigDict):
        from lzo.registry.settings import register_settings
        register_settings(cls)
        return super().__init_subclass__(**kwargs)
    
    if TYPE_CHECKING:

        @property
        def module_path(self) -> Path:
            """
            Gets the module root path
            """
            ...

        @property
        def module_config_path(self) -> Path:
            """
            Returns the config module path
            """
            ...

        @property
        def module_name(self) -> str:
            """
            Returns the module name
            """
            ...

class BaseSettings(_BaseSettings):
    """
    Base Settings with additional helpers
    """

    app_env: Optional[AppEnv] = None
    debug_enabled: Optional[bool] = None

    if TYPE_CHECKING:
        _rxtra: Dict[str, Any] = {}

    @eproperty
    def _is_registered(self) -> bool:
        """
        Returns whether the settings are registered
        """
        return hasattr(self, '_rxtra')

    @eproperty
    def module_path(self) -> Path:
        """
        Gets the module root path
        """
        if self._is_registered and self._rxtra.get('module_path'):
            return self._rxtra['module_path']
        return super().module_path
    
    @eproperty
    def module_config_path(self) -> Path:
        """
        Returns the config module path
        """
        if self._is_registered and self._rxtra.get('module_config_path'):
            return self._rxtra['module_config_path']
        return super().module_config_path
    
    @eproperty
    def module_name(self) -> str:
        """
        Returns the module name
        """
        if self._is_registered and self._rxtra.get('module'):
            return self._rxtra['module']
        return super().module_name
    
    @eproperty
    def logger(self) -> 'Logger':
        """
        Returns the logger
        """
        from lzl.logging import logger
        return logger
    
    @eproperty
    def null_logger(self) -> 'NullLogger':
        """
        Returns the null logger
        """
        from lzl.logging import null_logger
        return null_logger
    
    @eproperty
    def autologger(self) -> Logger:
        """
        Returns the autologger
        """
        return self.logger if (self.debug_enabled or self.is_development_env) else self.null_logger
    
    @eproperty
    def app_module_name(self) -> Optional[str]:
        """
        Returns the app module name
        """
        return self._extra.get('app_module_name')
    
    @eproperty
    def ctx(self) -> Optional['AppContext']:
        """
        Returns the app context

        - Only if this is a registered settings
        """
        if not self._is_registered: return None
        from lzo.types.settings.context import AppContextManager
        return AppContextManager.get_ctx(self.module_name)


    @model_validator(mode = 'after')
    def validate_app_env(self):
        """
        Validates the app environment
        """
        if self.app_env is None:
            try:
                if self.app_module_name:
                    self.app_env = AppEnv.from_module_name(self.app_module_name)
                elif self.Config.env_prefix:
                    self.app_env = get_app_env(self.Config.env_prefix.rstrip('_'))
                else:
                    self.app_env = get_app_env(self.app_module_name or self.module_name)
            except Exception as e:
                self.app_env = get_app_env('lzo')
        elif isinstance(self.app_env, str):
            self.app_env = AppEnv.from_env(self.app_env)
        return self

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
    

    def set_app_env(self, env: AppEnv) -> None:
        """
        Sets the app environment
        """
        self.app_env = self.app_env.from_env(env)


class BaseModel(_BaseModel):
    """
    Base Model
    """
    if PYDANTIC_VERSION == 2:
        _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    else:
        _extra: Dict[str, Any] = Field(default_factory = dict, exclude = True, hidden = True)
        
        class Config:
            extra = 'allow'
            arbitrary_types_allowed = True
        
    def get(self, name, default: Any = None):
        """
        Get an attribute from the model
        """
        return getattr(self, name, default)

    @classmethod
    def model_validate_batch(
        cls: type['Model'],
        items: List[Any], 
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
        **kwargs
    ) -> List['Model']:
        """
        Validates the items
        """
        return [cls.model_validate(item, strict = strict, from_attributes = from_attributes, context = context) for item in items]


class RBaseModel(BaseModel):
    """
    Base Model with Module Properties
    """
    
    @eproperty
    def module_path(self) -> Path:
        """
        Gets the module root path

        https://stackoverflow.com/questions/25389095/python-get-path-of-root-project-structure
        """
        import pkg_resources
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
        import pkg_resources
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
    

if TYPE_CHECKING:

    from .settings.context import AppContext

    class RegisteredSettings(BaseSettings, Registered):
        """
        Registered Settings
        """
        ctx: AppContext
