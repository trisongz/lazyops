from __future__ import annotations

"""
Common Types
"""
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
from typing import Optional, Dict, Any, List, TYPE_CHECKING
if TYPE_CHECKING:
    from lzl.logging import Logger, NullLogger

class BaseSettings(_BaseSettings):
    """
    Base Settings with additional helpers
    """

    app_env: Optional[AppEnv] = None
    debug_enabled: Optional[bool] = None

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