from __future__ import annotations

"""
Stateful Registry

Migrated from lazyops.libs.fastapi_utils.state.registry
"""

from typing import Dict, TypeVar, Optional, Type, Union, TYPE_CHECKING
from lazyops.utils.lazy import lazy_import
from lazyops.utils.logs import logger

ClientT = TypeVar('ClientT')
ClientTypeT = Type[ClientT]

_registered_clients: Dict[str, Union[ClientT, ClientTypeT]] = {}
_client_registry_mapping: Dict[str, str] = None # A mapping of client names to module paths

def update_client_registry_mapping(
    mapping: Dict[str, str],
):
    """
    Updates the client registry mapping
    """
    global _client_registry_mapping
    if _client_registry_mapping is None:
        _client_registry_mapping = {}
    _client_registry_mapping.update(mapping)


def get_global_client(
    name: str,
) -> ClientTypeT:
    """
    Global Clients do not require initialization and are types
    """
    global _registered_clients
    if not _client_registry_mapping:
        raise ValueError('Client Registry Mapping not set')
    if name not in _registered_clients:
        if name not in _client_registry_mapping:
            raise ValueError(f'Client {name} not found in client registry mapping')
        _registered_clients[name] = lazy_import(_client_registry_mapping[name])
    return _registered_clients[name]


def get_client(
    name: str, 
    **kwargs,
) -> ClientT:
    """
    Clients require initialization
    """
    global _registered_clients
    if not _client_registry_mapping:
        raise ValueError('Client Registry Mapping not set')
    if name not in _registered_clients:
        if name not in _client_registry_mapping:
            raise ValueError(f'Client {name} not found in client registry mapping')
        client = lazy_import(_client_registry_mapping[name])
        _registered_clients[name] = client(**kwargs)
    return _registered_clients[name]

def register_client(
    client: Union[ClientT, ClientTypeT],
    name: str,
    verbose: Optional[bool] = False,
    **kwargs,
) -> bool:
    """
    Registers a client
    """
    global _registered_clients
    if name not in _registered_clients:
        _registered_clients[name] = client
        if verbose: logger.info(f'Client {name}', colored = True, prefix = "|g|Registered|e|")
        return True
    return False

