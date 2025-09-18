"""Registry utilities shared across LazyOps modules."""

from .base import MRegistry, combine_parts
from .clients import (
    get_app_client,
    register_app_client,
    register_app_clients,
    register_client,
    register_client_hook,
    register_initialized_client,
)
from .settings import (
    get_app_settings,
    register_app_settings,
    register_initialized_settings,
    register_settings,
)

__all__ = [
    'MRegistry',
    'combine_parts',
    'get_app_client',
    'get_app_settings',
    'register_app_client',
    'register_app_clients',
    'register_app_settings',
    'register_client',
    'register_client_hook',
    'register_initialized_client',
    'register_initialized_settings',
    'register_settings',
]
