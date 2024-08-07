from __future__ import annotations

from typing import Dict, Any
from lzl.proxied import ProxyObject
from .openai import OpenAISettings, AzureOpenAISettings

settings: OpenAISettings = ProxyObject(OpenAISettings)

def get_settings(**kwargs) -> OpenAISettings:
    """
    Returns the OpenAI Settings
    """
    if kwargs: settings.configure(**kwargs)
    return settings

def get_default_headers() -> Dict[str, Any]:
    """
    Returns the Default Headers
    """
    return settings.get_headers()

def get_max_retries() -> int:
    """
    Returns the Max Retries
    """
    return settings.max_retries
