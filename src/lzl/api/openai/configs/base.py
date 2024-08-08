from __future__ import annotations

import json
import logging
import pathlib
import aiohttpx
import contextlib

from pydantic import PrivateAttr
from lzl.types import BaseSettings, validator, eproperty, Field, field_validator
from lzl.proxied import proxied, ProxyObject
from lzo.types import AppEnv
from lzl.api.openai.version import VERSION, DEFAULT_AZURE_VERSION
from lzl.api.openai.types.auth import OpenAIAuth, OpenAIContext
from lzl.api.openai.types.base import ApiType
from lzl.api.openai.configs.proxy import OpenAIProxySettings
from typing import Optional, Dict, Union, Any



class BaseOpenAISettings(BaseSettings):
    url: Optional[str] = None
    scheme: Optional[str] = 'http://'
    host: Optional[str] = None
    port: Optional[int] = 8080
    
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    api_path: Optional[str] = '/v1'
    api_type: Optional[ApiType] = ApiType.openai
    api_version: Optional[str] = None
    api_key_path: Optional[pathlib.Path] = None
    
    organization: Optional[str] = None
    proxies: Optional[Union[Dict, str]] = None
    app_info: Optional[Dict[str, str]] = None
    debug_enabled: Optional[bool] = False
    ignore_errors: Optional[bool] = False
    disable_retries: Optional[bool] = False # Allows users to customize the retry behavior

    timeout: Optional[int] = 600
    max_retries: Optional[int] = 3

    # Additional Configuration
    ## Request Pool Configuration
    max_connections: Optional[int] = 250
    max_keepalive_connections: Optional[int] = 150
    keepalive_expiry: Optional[int] = 60

    custom_headers: Optional[Dict[str, str]] = None
    limit_monitor_enabled: Optional[bool] = True

    _extra: Dict[str, Any] = PrivateAttr(default_factory = dict)

    @validator("api_type")
    def validate_api_type(cls, v):
        """
        Validates the API Type
        """
        if v is None: return ApiType.openai
        return ApiType.parse(v) if isinstance(v, str) else v
    
    @validator("api_key")
    def validate_api_key(cls, v, values: Dict[str, Union[str, int, bool, pathlib.Path, Any]]):
        """
        Validates the API Key
        """
        if v is None and values.get('api_key_path') is not None:
            return values['api_key_path'].read_text()
        return v
    
    @eproperty
    def ctx(self) -> OpenAIContext:
        """
        Returns the context
        """
        return OpenAIContext(
            custom_headers = self.custom_headers or {},
        )

    @eproperty
    def api_url(self) -> str:
        """
        Returns the API URL
        """
        if self.api_base: return self.api_base
        if self.url: return self.url
        if self.host:
            url = f"{self.scheme}{self.host}"
            if self.port: url += f":{self.port}"
            return url
        
        # Return the official Open API URL
        return "https://api.openai.com"
    
    @eproperty
    def api_client_limits(self) -> aiohttpx.Limits:
        """
        Returns the API Client Limits
        """
        return aiohttpx.Limits(
            max_connections = self.max_connections,
            max_keepalive_connections = self.max_keepalive_connections,
            keepalive_expiry = self.keepalive_expiry,
        )
    

    @eproperty
    def base_url(self) -> str:
        """
        Returns the Base URL
        """
        if self.api_path:
            from urllib.parse import urljoin
            return urljoin(self.api_url, self.api_path)
        return self.api_url
    
    @eproperty
    def base_headers(self) -> Dict[str, str]:
        """
        Returns the Base Headers
        """
        if 'app_headers' not in self.ctx.data:
            import platform
            ua = f"OpenAI/v1 async_openai/{VERSION}"
            if self.app_info:
                t = ""
                if "name" in self.app_info:
                    t += self.app_info["name"]
                if "version" in self.app_info:
                    t += f"/{self.app_info['version']}"
                if "url" in self.app_info:
                    t += f" ({self.app_info['url']})"
                ua += f" {t}"
            uname_without_node = " ".join(
                v for k, v in platform.uname()._asdict().items() if k != "node"
            )
            data = {
                "bindings_version": VERSION,
                "httplib": "httpx",
                "lang": "python",
                "lang_version": platform.python_version(),
                "platform": platform.platform(),
                "publisher": "trisongz",
                "uname": uname_without_node,
            }
            if self.app_info: data["application"] = self.app_info
            self.ctx.data['app_headers'] = {"X-OpenAI-Client-User-Agent": json.dumps(data), "User-Agent": ua}
        return self.ctx.data['app_headers']
    
    # Deprecated
    def get_api_key_headers(
        self,
        api_key: Optional[str] = None, 
        api_type: Optional[Union[ApiType, str]] = None
    ) -> Dict[str, str]:
        """
        Returns the API Key Headers
        """
        if api_key is None: api_key = self.api_key
        if api_type is None: api_type = self.api_type
        api_type = api_type.value if isinstance(api_type, ApiType) else api_type
        if api_type in {"openai", "azure_ad"}:
            return {"Authorization": f"Bearer {api_key}"}
        return {"api-key": api_key}

    def get_api_client_auth(
        self,
        api_key: Optional[str] = None, 
        api_type: Optional[Union[ApiType, str]] = None,
        **kwargs
    ) -> OpenAIAuth:
        """
        Returns the API Client Auth
        """
        if api_key is None: api_key = self.api_key
        if api_type is None: api_type = self.api_type
        api_type = api_type.value if isinstance(api_type, ApiType) else api_type
        if api_type in {"openai", "azure_ad"}:
            return OpenAIAuth(
                settings = self, context = self.ctx, auth_key = "Authorization", auth_value = f"Bearer {api_key}",
            )
        return OpenAIAuth(
            settings = self, context = self.ctx, auth_key = "api-key", auth_value = api_key,
        )

    def get_headers(
        self, 
        # api_key: Optional[str] = None, 
        api_version: Optional[str] = None,
        api_type: Optional[Union[ApiType, str]] = None,
        organization: Optional[str] = None,
        app_info: Optional[str] = None,
        **kwargs
    ) -> Dict[str, str]:
        """
        Gets the Headers
        """
        # print(api_key, api_version, api_type, organization, kwargs)
        # headers = self.headers.copy()
        headers = self.base_headers.copy()
        if kwargs: headers.update(**kwargs)
        if app_info is not None: headers['application'] = app_info
        # headers.update(self.get_api_key_headers(api_key = api_key, api_type = api_type))
        if organization is None: organization = self.organization
        if api_version is None: api_version = self.api_version
        if organization:
            headers["OpenAI-Organization"] = organization
        if api_version is not None and api_type.value == 'open_ai':
            headers["OpenAI-Version"] = api_version
        if self.debug_enabled:
            headers["OpenAI-Debug"] = "true"
        headers['Content-Type'] = 'application/json'
        return headers

    def get_api_url(
        self, 
        host: Optional[str] = None, 
        port: Optional[int] = None, 
        scheme: Optional[str] = None, 
        url: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Returns the API URL
        """
        if api_base: return api_base
        if url: return url
        if host:
            url = f"{scheme or self.scheme}{host}"
            if port: url += f":{port}"
            return url
        return self.api_url

    def get_base_api_url(
        self, 
        host: Optional[str] = None, 
        port: Optional[int] = None, 
        scheme: Optional[str] = None, 
        url: Optional[str] = None,
        api_path: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Returns the Base API URL
        """
        api_url = self.get_api_url(
            host=host,
            port=port,
            scheme=scheme,
            url=url,
            api_base=api_base,
        )
        api_path = api_path or self.api_path
        if api_path:
            from urllib.parse import urljoin
            return urljoin(api_url, api_path)
        return api_url


    def configure(
        self, 
        url: Optional[str] = None,
        scheme: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        api_path: Optional[str] = None,
        api_type: Optional[ApiType] = None,
        api_version: Optional[str] = None,
        api_key_path: Optional[pathlib.Path] = None,

        organization: Optional[str] = None,
        proxies: Optional[Union[str, Dict]] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        app_info: Optional[Dict[str, str]] = None,
        debug_enabled: Optional[bool] = None,
        ignore_errors: Optional[bool] = None,
        disable_retries: Optional[bool] = None,

        max_connections: Optional[int] = None,
        max_keepalive_connections: Optional[int] = None,
        keepalive_expiry: Optional[int] = None,
        custom_headers: Optional[Dict[str, str]] = None,

        **kwargs
    ):  # sourcery skip: low-code-quality
        """
        Allows Post-Init Configuration of the OpenAI Settings
        """
        if url is not None: self.url = url
        if api_base is not None: self.api_base = api_base
        if scheme is not None: self.scheme = scheme
        if host is not None: self.host = host
        if port is not None: self.port = port
        if api_key is not None: self.api_key = api_key
        if api_path is not None: self.api_path = api_path
        if api_key_path is not None: 
            self.api_key_path = api_key_path if isinstance(api_key_path, pathlib.Path) else pathlib.Path(api_key_path)
            self.api_key = self.api_key_path.read_text().strip()
        
        if api_type is not None: 
            self.api_type = ApiType(api_type) if isinstance(api_type, str) else api_type
        
        if api_version is None: 
            self.api_version = self.api_type.get_version(api_version)
        else:
            self.api_version = api_version
        if organization is not None: self.organization = organization
        if proxies is not None: self.proxies = proxies
        if timeout is not None: self.timeout = timeout
        if max_retries is not None: self.max_retries = max_retries
        if app_info is not None: self.app_info = app_info
        if debug_enabled is not None: self.debug_enabled = debug_enabled
        if ignore_errors is not None: self.ignore_errors = ignore_errors
        if disable_retries is not None: self.disable_retries = disable_retries

        if max_connections is not None: self.max_connections = max_connections
        if max_keepalive_connections is not None: self.max_keepalive_connections = max_keepalive_connections
        if keepalive_expiry is not None: self.keepalive_expiry = keepalive_expiry
        if custom_headers is not None: self.ctx.update_headers(custom_headers)

    def disable_httpx_logger(self):
        """
        Disables the HTTPX Logger
        """
        from ..utils.logs import configure_httpx_logger
        configure_httpx_logger(logging.ERROR)
    
    def enable_httpx_logger(self):
        """
        Enables the HTTPX Logger
        """
        from ..utils.logs import configure_httpx_logger
        configure_httpx_logger(logging.INFO)


    @eproperty
    def proxy(self) -> OpenAIProxySettings:
        """
        Return the Proxy Settings
        """
        return OpenAIProxySettings()