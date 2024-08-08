from __future__ import annotations

from typing import Dict, Any, Optional
from lzl.proxied import ProxyObject
from .openai import OpenAISettings, AzureOpenAISettings
from .external import ExternalProviderSettings
from .proxy import (
    OpenAIProxySettings, 
    BaseProxySettings, 
    HeliconeProxySettings,
)

_openai_settings: Optional['OpenAISettings'] = None

def get_settings(**kwargs) -> OpenAISettings:
    """
    Returns the OpenAI Settings
    """
    global _openai_settings
    if _openai_settings is None:
        _openai_settings = OpenAISettings()
    if kwargs: _openai_settings.configure(**kwargs)
    return _openai_settings

def get_default_headers() -> Dict[str, Any]:
    """
    Returns the Default Headers
    """
    return get_settings().get_headers()

def get_max_retries() -> int:
    """
    Returns the Max Retries
    """
    return get_settings().max_retries


settings: OpenAISettings = ProxyObject(
    obj_getter = get_settings
)
