from __future__ import annotations

import json
import pathlib
import aiohttpx
import contextlib

from pydantic import PrivateAttr
from lzl.types import BaseSettings, validator, eproperty, Field
from lzl.proxied import proxied, ProxyObject
from typing import Optional, Dict, Union, Any


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


    def create_proxy_headers_for_provider(
        self,
        name: str,
        config: Dict[str, Any],
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers for Helicone
        """
        return {}

        
    class Config:
        # We use a different prefix here to avoid conflicts
        env_prefix = "OAI_"
        case_sensitive = False


class HeliconeProxySettings(BaseProxySettings):
    """
    The Helicone Proxy Settings
    """
    
    proxy_kind: Optional[str] = 'helicone'


    def create_proxy_headers_for_provider(
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
            headers['Helicone-Property-AppEnvironment'] = self.proxy_env_name
            if user_id: user_id += f'-{self.proxy_env_name}'
        if user_id: headers['Helicone-User-Id'] = user_id
        if 'properties' in config: properties = config.pop('properties')
        if properties:
            for k, v in properties.items():
                if 'Helicone-Property-' not in k: k = f'Helicone-Property-{k}'
                headers[k] = str(v)
        return headers


ProxyProviderSettings = Union[HeliconeProxySettings, BaseProxySettings]
ProxyProviders = {
    'helicone': HeliconeProxySettings,
}

# This is a proxy settings that passes it through to the downstream provider
class OpenAIProxySettings(BaseProxySettings):
    """
    The OpenAI Proxy Settings
    """
    
    proxy_kind: Optional[str] = 'helicone'

    @eproperty
    def proxy_providers(self) -> Dict[str, ProxyProviderSettings]:
        """
        Returns the Proxy Providers
        """
        return {}
    
    def create_proxy_headers(
        self,
        name: str,
        config: Dict[str, Any],
        kind: Optional[str] = None,
        **properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Creates the Proxy Headers
        """
        if kind is None: kind = self.proxy_kind
        if kind not in self.proxy_providers: 
            if kind not in ProxyProviders: raise ValueError(f"Unsupported Proxy Kind: {kind}")
            self.proxy_providers[kind] = ProxyProviders[kind]()
        return self.proxy_providers[kind].create_proxy_headers_for_provider(name, config, **properties)