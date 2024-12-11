from __future__ import annotations

import json
import pathlib
import contextlib
from lzl.api import aiohttpx
from lzl.types import BaseSettings, validator, eproperty, Field
from lzo.utils import create_unique_id
from typing import Optional, Dict, Union, Any, Type


class BaseProxySettings(BaseSettings):

    proxy_enabled: Optional[bool] = None
    proxy_endpoint: Optional[str] = None
    proxy_name: Optional[str] = None
    proxy_kind: Optional[str] = None
    proxy_env_name: Optional[str] = None
    proxy_app_name: Optional[str] = None
    proxy_endpoints: Optional[Dict[str, str]] = Field(default_factory = dict)
    proxy_apikeys: Optional[Dict[str, str]] = Field(default_factory = dict)


    @property
    def endpoint(self) -> Optional[str]:
        """
        Returns the Proxy Endpoint
        """
        return self.proxy_endpoint
    
    @property
    def enabled(self) -> Optional[bool]:
        """
        Returns whether the proxy is enabled
        """
        return self.proxy_enabled

    def get_proxy_endpoint(self) -> Optional[str]:
        """
        Returns the proxy endpoint
        """
        if self.proxy_name and self.proxy_endpoints.get(self.proxy_name):
            return self.proxy_endpoints[self.proxy_name]
        for name, endpoint in self.proxy_endpoints.items():
            with contextlib.suppress(Exception):
                resp = aiohttpx.get(endpoint, timeout = 2.0)
                # data = resp.json()
                # if data.get('error'):
                self.proxy_name = name
                return endpoint
        return None

    def init(self, config_path: Optional[pathlib.Path] = None):
        """
        Initializes the core settings
        """
        if config_path: self.load_proxy_config(config_path)
        if self.proxy_endpoint is None: 
            self.proxy_endpoint = self.get_proxy_endpoint()
            self.proxy_enabled = self.proxy_endpoint is not None

    def get_apikey(
        self, source: Optional[str] = None, 
    ) -> str:
        """
        Gets the appropriate API Key for the proxy
        """
        if source:
            source = source.lower()
            for k, v in self.proxy_apikeys.items():
                if k in source: return v
        return self.proxy_apikeys.get('default', None)
    
    def load_proxy_config(
        self,
        path: pathlib.Path,
    ):
        """
        Loads the Proxy Configuration from a File
        """
        if not path.exists(): return
        text = path.read_text()
        if 'env/' in text:
            from lzo.utils import parse_envvars_from_text
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
        for k, v in data.items():
            if v is None: continue
            if k in {'endpoint', 'enabled'}: k = f'proxy_{k}'
            if hasattr(self, k): setattr(self, k, v)
            elif hasattr(self, f'proxy_{k}'): setattr(self, f'proxy_{k}', v)
        self.proxy_endpoint = None
        self.proxy_enabled = None

    def update(
        self,
        **kwargs
    ) -> None:
        """
        Updates the Proxy Settings
        """
        for k, v in kwargs.items():
            if v is None: continue
            if k in {'endpoint', 'enabled'}: k = f'proxy_{k}'
            if hasattr(self, k): setattr(self, k, v)
            elif hasattr(self, f'proxy_{k}'): setattr(self, f'proxy_{k}', v)
        self.proxy_endpoint = None
        self.proxy_enabled = None

    def create_proxy_headers(
        self,
        headers: Optional[Dict[str, str]] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers for the Proxy Provider
        """
        headers = headers or {}
        return headers

    def configure_proxy_headers(
        self,
        headers: Optional[Dict[str, str]] = None,
        disable_cache: Optional[bool] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Configures the Proxy Headers for the Proxy Provider
        """
        return {}
    

    def configure_proxy_headers_for_function(
        self,
        headers: Optional[Dict[str, str]] = None,
        function_name: Optional[str] = None,
        disable_cache: Optional[bool] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Configures the Proxy Headers for the Proxy Provider
        """
        return {}
    
    def configure_proxy_headers_for_json_schema(
        self,
        headers: Optional[Dict[str, str]] = None,
        schema_name: Optional[str] = None,
        disable_cache: Optional[bool] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Configures the Proxy Headers for the Proxy Provider
        """
        return {}
    

    def disable_caching_headers(
        self,
        headers: Optional[Dict[str, str]] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Disables the Caching Headers
        """
        return headers
        
    class Config:
        # We use a different prefix here to avoid conflicts
        env_prefix = "OAI_"
        case_sensitive = False


class HeliconeProxySettings(BaseProxySettings):
    """
    The Helicone Proxy Settings
    """
    
    proxy_kind: Optional[str] = 'helicone'


    def create_proxy_headers(
        self,
        name: str,
        config: Dict[str, Any],
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers for Helicone
        """
        headers = {
            'Helicone-OpenAI-Api-Base': config.get('api_base', ''),
            'Helicone-Auth': f"Bearer {self.get_apikey(self.proxy_app_name)}",
            "Helicone-Property-ClientName": name,
            'Content-Type': 'application/json',
        }
        user_id = ''
        if self.proxy_app_name:
            headers['Helicone-Property-AppName'] = self.proxy_app_name
            user_id += self.proxy_app_name
        if self.proxy_env_name:
            headers['Helicone-Property-AppEnv'] = self.proxy_env_name
            if user_id and self.proxy_env_name not in user_id: user_id += f'-{self.proxy_env_name}'
        if user_id: headers['Helicone-User-Id'] = user_id
        if 'properties' in config: properties = config.pop('properties')
        if properties:
            for k, v in properties.items():
                if 'Helicone-Property-' not in k: k = f'Helicone-Property-{k}'
                headers[k] = str(v)
        return headers
    

    def configure_proxy_headers(
        self,
        headers: Optional[Dict[str, str]] = None,
        disable_cache: Optional[bool] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers for Helicone
        """
        headers = headers or {}
        return headers
    

    def configure_proxy_headers_for_function(
        self,
        headers: Optional[Dict[str, str]] = None,
        function_name: Optional[str] = None,
        disable_cache: Optional[bool] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Configures the Proxy Headers for the Proxy Provider
        """
        headers = headers or {}
        if function_name: headers['Helicone-Property-FunctionName'] = function_name
        if disable_cache: headers['Helicone-Cache-Seed'] = create_unique_id(length = 5)
        if properties:
            property_meta = {f'Helicone-Property-{k}': str(v) for k, v in properties.items()}
            headers.update(property_meta)
        return headers
    

    def configure_proxy_headers_for_json_schema(
        self,
        headers: Optional[Dict[str, str]] = None,
        schema_name: Optional[str] = None,
        disable_cache: Optional[bool] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Configures the Proxy Headers for the Proxy Provider
        """
        headers = headers or {}
        if schema_name: headers['Helicone-Property-SchemaName'] = schema_name
        if disable_cache: headers['Helicone-Cache-Seed'] = create_unique_id(length = 5)
        if properties:
            property_meta = {f'Helicone-Property-{k}': str(v) for k, v in properties.items()}
            headers.update(property_meta)
        return headers


    def disable_caching_headers(
        self,
        headers: Optional[Dict[str, str]] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Disables the Caching Headers
        """
        headers = headers or {}
        headers['Helicone-Cache-Seed'] = create_unique_id(length = 5)
        return headers


ProxyProviderSettings = Union[HeliconeProxySettings, BaseProxySettings]
ProxyProviders = {
    'helicone': HeliconeProxySettings,
}

# This is a proxy settings that passes it through to the downstream provider
class OpenAIProxySettings(BaseSettings):
    """
    The OpenAI Proxy Settings
    """

    proxy_provider: Optional[str] = None

    @eproperty
    def providers(self) -> Dict[str, ProxyProviderSettings]:
        """
        Returns the Proxy Providers
        """
        data = {}
        if self.proxy_provider:
            data[self.proxy_provider] = ProxyProviders[self.proxy_provider]()
        return data
    
    @property
    def current(self) -> Optional[str]:
        """
        Returns the Current Proxy Provider
        """
        return self._extra.get('current')
    
    @current.setter
    def current(self, value: str):
        """
        Sets the Current Proxy Provider
        """
        self.proxy_provider = value
        self._extra['current'] = value
        self.provider = self.get_provider(value)

    @eproperty
    def provider(self) -> Optional[ProxyProviderSettings]:
        """
        Returns the Current Proxy Provider
        """
        return self.providers.get(self.current)


    def register_provider(self, name: str, provider: Union[Type[ProxyProviderSettings], str]):
        """
        Registers a Proxy Provider
        """
        global ProxyProviders
        if isinstance(provider, str):
            from lzl.load import lazy_import
            provider = lazy_import(provider)
        ProxyProviders[name] = provider
    
    def get_provider(self, name: Optional[str] = None) -> ProxyProviderSettings:
        """
        Returns the Proxy Provider
        """
        if name is None: name = self.proxy_provider
        if name not in self.providers: 
            if name not in ProxyProviders: raise ValueError(f"Unsupported Proxy Kind: {name}")
            self.providers[name] = ProxyProviders[name]()
        return self.providers[name]
    
    def create_proxy_headers(
        self,
        name: str,
        config: Dict[str, Any],
        provider: Optional[str] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers
        """
        proxy = self.get_provider(name = provider)
        return proxy.create_proxy_headers(name, config, **properties)
    
    def configure_proxy_headers(
        self,
        headers: Optional[Dict[str, str]] = None,
        provider: Optional[str] = None,
        disable_cache: Optional[bool] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers
        """
        headers = headers or {}
        proxy = self.get_provider(name = provider)
        return proxy.configure_proxy_headers(headers, disable_cache = disable_cache, **properties)

    def configure_proxy_headers_for_function(
        self,
        headers: Optional[Dict[str, str]] = None,
        function_name: Optional[str] = None,
        disable_cache: Optional[bool] = None,
        provider: Optional[str] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers
        """
        headers = headers or {}
        proxy = self.get_provider(name = provider)
        return proxy.configure_proxy_headers_for_function(headers, function_name = function_name, disable_cache = disable_cache, **properties)


    def configure_proxy_headers_for_json_schema(
        self,
        headers: Optional[Dict[str, str]] = None,
        schema_name: Optional[str] = None,
        disable_cache: Optional[bool] = None,
        provider: Optional[str] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers
        """
        headers = headers or {}
        proxy = self.get_provider(name = provider)
        return proxy.configure_proxy_headers_for_json_schema(headers, schema_name = schema_name, disable_cache = disable_cache, **properties)



    def disable_caching_headers(
        self,
        headers: Optional[Dict[str, str]] = None,
        provider: Optional[str] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Disables the Caching Headers
        """
        headers = headers or {}
        proxy = self.get_provider(name = provider)
        return proxy.disable_caching_headers(headers, **properties)

    def load_config_file(
        self,
        path: pathlib.Path,
    ) -> Dict[str, Union[Dict[str, str], str]]:
        """
        Loads the Proxy Configuration from a File
        """
        if not path.exists(): return
        text = path.read_text()
        if 'env/' in text:
            from lzo.utils import parse_envvars_from_text
            text, _ = parse_envvars_from_text(text)
        
        assert path.suffix in {
            ".yaml", ".yml", ".json"
        }, f"The preset file must be a YAML or JSON file: {path}"
        
        if path.suffix == ".json":
            return json.loads(text)
        import yaml
        return yaml.safe_load(text)

    def load_proxy_config(
        self,
        path: pathlib.Path,
        provider: Optional[str] = None,
    ):
        """
        Loads the Proxy Configuration from a File
        """
        data = self.load_config_file(path = path)
        if not provider: provider = data.pop('proxy_provider')
        if not provider: raise ValueError("Proxy Provider must be provided")
        if provider_class := data.pop('provider_class', None):
            if isinstance(provider_class, str):
                from lzl.load import lazy_import
                provider_class = lazy_import(provider_class)
            self.register_provider(name = provider, provider = provider_class)
        proxy = self.get_provider(name = provider)
        proxy.update(**data)
        
        if not self.proxy_provider: self.current = provider
        # print(f'Proxy Config: {self.proxy_provider}: {self.current} -> {self.provider}')

    def update_proxy_config(
        self,
        provider: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Updates the Proxy Configuration
        """
        if not provider: provider = kwargs.pop('proxy_provider')
        if not provider: raise ValueError("Proxy Provider must be provided")
        proxy = self.get_provider(name = provider)
        proxy.update(**kwargs)
        if not self.proxy_provider: self.current = provider

    def init_proxy(self, provider: Optional[str] = None, config_path: Optional[pathlib.Path] = None):
        """
        Initializes the Proxy
        """
        if provider is None: provider = self.proxy_provider
        if provider is None: raise ValueError("Proxy Provider must be provided")
        self.get_provider(name = provider).init(config_path = config_path)

    @property
    def proxy_app_name(self) -> Optional[str]:
        """
        Returns the Proxy App Name
        """
        return self._extra.get('proxy_app_name', self.provider.proxy_app_name if self.provider else None)
    
    @proxy_app_name.setter
    def proxy_app_name(self, value: str):
        """
        Sets the Proxy App Name
        """
        if not self.provider: raise ValueError("Proxy Provider must be provided")
        self.provider.proxy_app_name = value
        self._extra['proxy_app_name'] = value

    @property
    def proxy_env_name(self) -> Optional[str]:
        """
        Returns the Proxy Env Name
        """
        return self._extra.get('proxy_env_name', self.provider.proxy_env_name if self.provider else None)
    
    @proxy_env_name.setter
    def proxy_env_name(self, value: str):
        """
        Sets the Proxy Env Name
        """
        if not self.provider: raise ValueError("Proxy Provider must be provided")
        self.provider.proxy_env_name = value
        self._extra['proxy_env_name'] = value

    @property
    def enabled(self) -> bool:
        """
        Returns whether the Proxy is Enabled
        """
        return self.provider.enabled if self.current else False

    @property
    def endpoint(self) -> Optional[str]:
        """
        Returns the Proxy Endpoint
        """
        return self.provider.endpoint if self.current else None
        

    class Config:
        # We use a different prefix here to avoid conflicts
        env_prefix = "OAI_"
        case_sensitive = False