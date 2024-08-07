from __future__ import annotations

import json
import logging
import pathlib
import random
import aiohttpx
import contextlib

from lazyops.types import BaseSettings, validator, BaseModel, lazyproperty, Field
from lazyops.libs.proxyobj import ProxyObject
from lazyops.libs.abcs.configs.types import AppEnv
from lazyops.libs.openai.version import VERSION
from async_openai.types.options import ApiType
from typing import Optional, Dict, Union, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..configs.openai import OpenAISettings, AzureOpenAISettings
    from ..configs.external import ExternalProviderConfig
#     from ..configs

class OpenAIContext(BaseModel):
    """
    A context object for OpenAI
    """
    custom_headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def update_headers(self, headers: Dict[str, Any]):
        """
        Updates the custom headers
        """
        if self.custom_headers is None: self.custom_headers = {}
        for k,v in headers.items():
            if isinstance(v, str): continue
            if isinstance(v, bool):
                headers[k] = "true" if v else "false"
            if isinstance(v, (int, float, type(None))):
                headers[k] = str(v)
        self.custom_headers.update(headers)


class OpenAIAuth(aiohttpx.Auth):
    """
    Custom Authentication Wrapper for OpenAI Client
    """
    def __init__(
        self, 
        settings: Union['OpenAISettings', 'AzureOpenAISettings'],
        context: 'OpenAIContext',
        auth_key: Optional[str] = None,
        auth_value: Optional[str] = None,
        **kwargs,
    ):
        """
        Initializes the OpenAI Auth
        """
        self.settings = settings
        self.context = context
        self.auth_key = auth_key
        self.auth_value = auth_value
    
    def auth_flow(self, request: aiohttpx.Request):
        """
        Injects the API Key into the Request
        """
        # request.headers.update(self.settings.get_api_key_headers())
        if self.auth_key not in request.headers:
            request.headers[self.auth_key] = self.auth_value
        if custom_headers := self.context.custom_headers:
            request.headers.update(custom_headers)
        
        # if self.settings.custom_headers:
        #     request.headers.update(self.settings.custom_headers)
        yield request

    async def async_auth_flow(self, request: aiohttpx.Request):
        """
        Injects the API Key into the Request
        """
        if self.auth_key not in request.headers:
            request.headers[self.auth_key] = self.auth_value
        if custom_headers := self.context.custom_headers:
            request.headers.update(custom_headers)
        # request.headers.update(self.settings.get_api_key_headers())
        # request.headers[self.auth_key] = self.auth_value
        # if self.settings.custom_headers:
        #     request.headers.update(self.settings.custom_headers)
        yield request


class ExternalProviderAuth(aiohttpx.Auth):
    """
    Custom Authentication Wrapper for External OpenAI Clients
    """
    def __init__(
        self, 
        config: 'ExternalProviderConfig',
        is_proxied: Optional[bool] = None,
        **kwargs,
    ):
        """
        Initializes the External Provider Auth

        :TODO - add support for Proxy
        """
        self.config = config
        self.is_proxied = is_proxied

    def get_api_key(self) -> Optional[str]:
        """
        Returns the API Key
        """
        if self.config.has_api_keys:
            if len(self.config.api_keys) == 1:
                return self.config.api_keys_value[0]
            return random.choice(self.config.api_keys_value)
        return self.config.api_key_value
    
    @property
    def has_api_key(self) -> bool:
        """
        Returns whether the API Key is present
        """
        return self.config.has_api_key or self.config.has_api_keys

    def auth_flow(self, request: aiohttpx.Request):
        """
        Injects the API Key into the Request
        """
        if self.has_api_key and self.config.api_key_header not in request.headers:
            request.headers[self.config.api_key_header] = self.get_api_key()
        if self.config.custom_headers:
            request.headers.update(self.config.custom_headers)
        if self.is_proxied and self.config.proxy_headers:
            request.headers.update(self.config.proxy_headers)
        yield request

    async def async_auth_flow(self, request: aiohttpx.Request):
        """
        Injects the API Key into the Request
        """
        if self.has_api_key and self.config.api_key_header not in request.headers:
            request.headers[self.config.api_key_header] = self.get_api_key()
        if self.config.custom_headers:
            request.headers.update(self.config.custom_headers)
        if self.is_proxied and self.config.proxy_headers:
            request.headers.update(self.config.proxy_headers)
        yield request
        
        