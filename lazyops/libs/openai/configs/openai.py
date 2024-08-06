from __future__ import annotations

import json
import pathlib
from pydantic import Field, field_validator
from lazyops.libs.abcs.configs.types import AppEnv
from lazyops.libs.abcs.types.props import eproperty
from .base import BaseOpenAISettings, ApiType
from .proxy import BaseProxySettings
from typing import Optional, Dict, Union, Any


class OpenAIProxySettings(BaseProxySettings):
    """
    The OpenAI Proxy Settings
    """

    class Config:
        env_prefix = 'OAI_'
        case_sensitive = False


class AzureOpenAISettings(BaseOpenAISettings):
    """
    The Azure OpenAI Settings
    """

    api_type: Optional[ApiType] = ApiType.azure
    api_version: Optional[str] = "2023-12-01-preview"
    api_path: Optional[str] = None

    class Config:
        env_prefix = 'AZURE_OPENAI_'
        case_sensitive = False

    @property
    def is_valid(self) -> bool:
        """
        Returns whether the Azure Settings are Valid
        """
        return self.api_key is not None and (
            self.url is not None or self.api_base is not None
        )



class OpenAISettings(BaseOpenAISettings):
    """
    The OpenAI Settings
    """

    app_env: Optional[AppEnv] = None
    client_configurations: Optional[Dict[str, Dict[str, Any]]] = Field(default_factory = dict)
    auto_loadbalance_clients: Optional[bool] = True
    auto_healthcheck: Optional[bool] = True

    function_cache_enabled: Optional[bool] = True
    
    class Config:
        env_prefix = 'OPENAI_'
        case_sensitive = False


    @eproperty
    def azure(self) -> AzureOpenAISettings:
        """
        Returns the Azure Settings
        """
        return AzureOpenAISettings()
    
    @eproperty
    def proxy(self) -> OpenAIProxySettings:
        """
        Return the Proxy Settings
        """
        return OpenAIProxySettings()
    
    @property
    def has_valid_azure(self) -> bool:
        """
        Returns whether the Azure Settings are Valid
        """
        return self.azure.is_valid

    def load_client_configurations(
        self,
        path: pathlib.Path,
    ):
        """
        Loads the Client Configurations
        """
        if not path.exists(): return
        text = path.read_text()
        if 'env/' in text:
            from lazyops.libs.abcs.utils.envvars import parse_envvars_from_text
            text, _ = parse_envvars_from_text(text)
        assert path.suffix in {
            ".yaml", ".yml", ".json"
        }, f"The preset file must be a YAML or JSON file: {path}"
        
        data: Dict[str, Union[Dict[str, str], str]] = {}
        if path.suffix == ".json":
            data = json.loads(text)
        else:
            import yaml
            data = yaml.safe_load(text)
        self.client_configurations.update(data)

    def configure(
        self, 
        auto_healthcheck: Optional[bool] = None,
        auto_loadbalance_clients: Optional[bool] = None,
        proxy_app_name: Optional[str] = None,
        proxy_env_name: Optional[str] = None,
        proxy_config: Optional[Union[Dict[str, Any], pathlib.Path]] = None,
        client_configurations: Optional[Union[Dict[str, Dict[str, Any]], pathlib.Path]] = None,
        **kwargs
    ):
        """
        Allows Post-Init Configuration of the OpenAI Settings

        Usage:

        ```python
        >>> settings.configure(
        >>>    api_key = 'sk-...',
        >>>    organization = 'org-...',
        >>>    max_retries = 4,
        >>>    timeout = 60,
        >>> )
        ```

        :param url: The OpenAI API URL              | Env: [`OPENAI_API_URL`]
        :param scheme: The OpenAI API Scheme        | Env: [`OPENAI_API_SCHEME`]
        :param host: The OpenAI API Host            | Env: [`OPENAI_API_HOST`]
        :param port: The OpenAI API Port            | Env: [`OPENAI_API_PORT`]
        :param api_key: The OpenAI API Key          | Env: [`OPENAI_API_KEY`]
        :param api_path: The OpenAI API Path        | Env: [`OPENAI_API_PATH`]
        :param api_type: The OpenAI API Type        | Env: [`OPENAI_API_TYPE`]
        :param api_version: The OpenAI API Version  | Env: [`OPENAI_API_VERSION`]
        :param api_key_path: The API Key Path       | Env: [`OPENAI_API_KEY_PATH`]
        :param organization: Organization           | Env: [`OPENAI_ORGANIZATION`]
        :param proxies: The OpenAI Proxies          | Env: [`OPENAI_PROXIES`]
        :param timeout: Timeout in Seconds          | Env: [`OPENAI_TIMEOUT`]
        :param max_retries: The OpenAI Max Retries  | Env: [`OPENAI_MAX_RETRIES`]
        :param kwargs: Additional Keyword Arguments
        """
        if auto_healthcheck is not None: self.auto_healthcheck = auto_healthcheck
        if auto_loadbalance_clients is not None: self.auto_loadbalance_clients = auto_loadbalance_clients
        if proxy_config:
            if isinstance(proxy_config, pathlib.Path):
                self.proxy.load_proxy_config(proxy_config)
            else: self.proxy.update(**proxy_config)
            self.proxy.init()
        if proxy_app_name: self.proxy.proxy_app_name = proxy_app_name
        if proxy_env_name: self.proxy.proxy_name = proxy_env_name
        if client_configurations:
            if isinstance(client_configurations, pathlib.Path):
                self.load_client_configurations(client_configurations)
            else: self.client_configurations.update(client_configurations)

        # Parse apart the azure setting configurations
        az_kwargs, rm_keys = {}, []
        for k, v in kwargs.items():
            if k.startswith('azure_'):
                az_kwargs[k[6:]] = v
                rm_keys.append(k)
            
            elif k.startswith('az_'):
                az_kwargs[k[3:]] = v
                rm_keys.append(k)
        
        # Configure the Azure Settings
        if az_kwargs: self.azure.configure(**az_kwargs)
        for k in rm_keys: kwargs.pop(k, None)
        super().configure(**kwargs)

    
    @field_validator('app_env', mode = 'before')
    def validate_app_env(cls, value: Optional[Any]) -> Any:
        """
        Validates the app environment
        """
        if value is None:
            from lazyops.libs.abcs.configs.types import get_app_env
            return get_app_env('openai')
        return AppEnv.from_env(value) if isinstance(value, str) else value

    @property
    def in_k8s(self) -> bool:
        """
        Returns whether the app is running in kubernetes
        """
        from lazyops.utils.system import is_in_kubernetes
        return is_in_kubernetes()
    
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

