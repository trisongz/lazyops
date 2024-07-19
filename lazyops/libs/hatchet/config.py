from __future__ import annotations

import os
from pydantic import model_validator, Field, PrivateAttr
from lazyops.libs.proxyobj import ProxyObject
from lazyops.libs.abcs.configs.base import BaseAppSettings
from lazyops.libs.abcs.configs.types import AppEnv

from lazyops.libs.abcs.types.persistence import TemporaryData
from lazyops.libs.logging import logger, null_logger
from typing import Dict, Union, Optional, Any, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from lazyops.utils.logs import Logger
    from hatchet_sdk.loader import ClientConfig

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
    base_name: Optional[str] = 'lazyops'
    api_endpoint: Optional[str] = None
    grpc_endpoint: Optional[str] = None
    endpoints: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    app_env: Optional[AppEnv] = None
    debug_enabled: Optional[bool] = None
    workflow_concurrency_limit: Optional[int] = 250
    config_lib_path: Optional[str] = None

    include_instance_name_in_workflow: Optional[bool] = False

    _extra: Optional[Dict[str, Any]] = PrivateAttr(default_factory=dict)

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

    def configure_client_endpoints(self, config: 'ClientConfig') -> None:
        """
        Configure the client endpoints based on the environment variables
        """
        if self.api_endpoint and self.grpc_endpoint:
            config.server_url = self.api_endpoint
            config.host_port = self.grpc_endpoint
        elif self.grpc_endpoint:
            config.host_port = self.grpc_endpoint
        elif self.endpoints:
            ref = 'develop' if self.is_development_env else 'prod' 
            from lazyops.libs.abcs.utils.http import validate_website_with_socket
            if self.in_k8s and self.endpoints.get('api', {}).get(ref, {}).get('cluster') and \
                validate_website_with_socket(
                self.endpoints['api'][ref]['cluster'],
            ):
                config.server_url = self.endpoints['api'][ref]['cluster']
                config.host_port = self.endpoints['grpc'][ref]['cluster']
            elif self.endpoints.get('grpc', {}).get(ref, {}).get('external'):
                config.host_port = self.endpoints['grpc'][ref]['external']
            
        return config


    def configure_session_endpoints(
        self, 
        config: 'ClientConfig',
        instance: str = 'default',
        api_endpoint: Optional[str] = None,
        grpc_endpoint: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Configure the session endpoints based on the environment variables
        """
        # If no endpoints are provided, then we use the endpoints from the config
        if not api_endpoint and os.getenv(f'HATCHET_API_ENDPOINT_{instance.upper()}'):
            api_endpoint = os.getenv(f'HATCHET_API_ENDPOINT_{instance.upper()}')
        
        if not grpc_endpoint and os.getenv(f'HATCHET_GRPC_ENDPOINT_{instance.upper()}'):
            grpc_endpoint = os.getenv(f'HATCHET_GRPC_ENDPOINT_{instance.upper()}')

        if not api_endpoint and not grpc_endpoint and (
            not self.endpoints or not \
            self.endpoints.get(instance)
        ):
            return self.configure_client_endpoints(config)
        if api_endpoint and grpc_endpoint:
            config.server_url = api_endpoint
            config.host_port = grpc_endpoint
        elif grpc_endpoint:
            config.host_port = grpc_endpoint
        elif self.endpoints.get(instance):
            endpoints = self.endpoints[instance]
            ref = 'develop' if self.is_development_env else 'prod' 
            from lazyops.libs.abcs.utils.http import validate_website_with_socket
            if self.in_k8s and endpoints.get('api', {}).get(ref, {}).get('cluster') and \
                validate_website_with_socket(
                endpoints['api'][ref]['cluster'],
            ):
                config.server_url = endpoints['api'][ref]['cluster']
                config.host_port = endpoints['grpc'][ref]['cluster']
            elif endpoints.get('grpc', {}).get(ref, {}).get('external'):
                config.host_port = endpoints['grpc'][ref]['external']
        return config


    @property
    def logger(self) -> 'Logger':
        """
        Gets the logger
        """
        return logger
    
    @property
    def null_logger(self) -> 'Logger':
        """
        Gets the null logger
        """
        return null_logger
    
    @property
    def autologger(self) -> 'Logger':
        """
        Automatic Logger that is enabled in devel mode
        """
        return logger if (self.is_development_env or self.debug_enabled) else null_logger
    
    @property
    def version(self) -> str:
        """
        Returns the hatchet sdk version
        """
        if 'version' not in self._extra:
            from importlib.metadata import version
            self._extra['version'] = version('hatchet-sdk')
        return self._extra['version']

    def configure(self, **kwargs):
        """
        Configures the Hatchet Settings
        """
        for k,v in kwargs.items():
            if k == 'app_env':
                if isinstance(v, str): v = AppEnv(v)
            if hasattr(self, k): setattr(self, k, v)
        return self
        

# settings: HatchetSettings = ProxyObject(
#     obj_getter = 'lazyops.libs.hatchet.utils.get_hatchet_settings'
# )