from __future__ import annotations

from pydantic import model_validator, Field
from lazyops.libs.proxyobj import ProxyObject
from lazyops.libs.abcs.configs.base import BaseAppSettings
from lazyops.libs.abcs.configs.types import AppEnv
from lazyops.libs.abcs.types.persistence import TemporaryData

from typing import Dict, Union, Optional
from pathlib import Path

lib_path = Path(__file__).parent

_temp_data: Optional[TemporaryData] = None

def get_temp_data() -> TemporaryData:
    """
    Retrieves the temporary data
    """
    global _temp_data
    if _temp_data is None:
        _temp_data = TemporaryData(lib_path.joinpath('data'))
    return _temp_data

class HatchetSettings(BaseAppSettings):
    """
    Hatchet Settings
    """
    endpoints: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    app_env: Optional[AppEnv] = None


    @property
    def temp_data(self) -> 'TemporaryData':
        """
        Retrieves the temporary data
        """
        return get_temp_data()

    class Config:
        env_prefix = "HATCHET_"

    
    @model_validator(mode = 'after')
    def validate_hatchet_settings(self):
        """
        Validates the HatchetSettings
        """
        if self.app_env is None:
            self.app_env = AppEnv.from_module_name('HATCHET')
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
        return self.app_env in [AppEnv.DEVELOPMENT, AppEnv.LOCAL, AppEnv.CICD, AppEnv.STAGING, AppEnv.TEST]
    
    def set_app_env(self, env: AppEnv) -> None:
        """
        Sets the app environment
        """
        self.app_env = self.app_env.from_env(env)



settings: HatchetSettings = ProxyObject(
    obj_getter = 'lazyops.libs.hatchet.utils.get_hatchet_settings'
)