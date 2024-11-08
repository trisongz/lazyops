from __future__ import annotations

"""
Registry of Clients that can be lazily loaded
"""

from .base import MRegistry
from lzl.types import Literal
from typing import Dict, TypeVar, Optional, Type, Union, Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .mixins import RegisteredClient
    RClientT = TypeVar('RClientT', bound = RegisteredClient)

"""
We can either implement a flattened dict or a nested dict

Flattened:
{
    'module.client_name': client
}
"""

# V2 Implementation of Registry
_cregistry: MRegistry['RClientT'] = MRegistry('clients')

def register_initialized_client(
    client: 'RClientT',
    **kwargs,
) -> None:
    """
    Registers an initialized client
    """
    if hasattr(client, '_rxtra'):
        return _cregistry._register_initialized(client._rxtra['registry_name'], client)
    cls_name = _cregistry.get_classname(client, is_type = False)
    cls_module = client._rmodule \
        if getattr(client, '_rmodule', None) is not None else \
        client.__class__.__module__.split('.')[0]
    client_name = client.name if getattr(client, 'name', None) is not None else cls_name
    registry_name = f'{cls_module}.{client_name}'
    if registry_name in _cregistry.init_registry:
        raise ValueError(f'Client {registry_name} already has registered client')
    return _cregistry._register_initialized(registry_name, client)



def register_client(
    client: Union[Type['RClientT'], 'RClientT'],
    **kwargs,
) -> None:
    """
    Registers the client with the registry
    """
    if not isinstance(client, type):
        return register_initialized_client(client)
    cls_name = _cregistry.get_classname(client, is_type = True)
    client_name = client.name if getattr(client, 'name', None) is not None else cls_name
    cls_module = client._rmodule \
        if getattr(client, '_rmodule', None) is not None else \
        client.__module__.split('.')[0]
    registry_name = f'{cls_module}.{client_name}'
    if registry_name in _cregistry.mregistry:
        _cregistry.logger.warning(f'Client {client_name} already registered with `{registry_name}`')
        return
    client._rxtra['module'] = cls_module
    client._rxtra['cls_name'] = cls_name
    client._rxtra['client_name'] = client_name
    client._rxtra['registry_name'] = registry_name
    client._rxtra['module_path'] = _cregistry.get_module_path(client)
    client._rxtra['registered'] = True
    _cregistry[registry_name] = client

def register_app_client(
    client_name: str,
    client_path: str,
    module: Optional[str] = None,
):
    """
    Registers the app client for lazily loading
    """
    if module: client_name = f'{module}.{client_name}'
    if client_name in _cregistry.mregistry: return
    _cregistry.uninit_registry[client_name] = client_path

def register_app_clients(
    clients: Dict[str, str],
    module: Optional[str] = None,
):
    """
    Registers a Dictionary of app clients for lazily loading
    """
    for client_name, client_path in clients.items():
        register_app_client(client_name, client_path, module = module)
        
def get_app_client(
    client_name: str,
    module: Optional[str] = None,
    **kwargs,
) -> 'RegisteredClient':  # sourcery skip: extract-method
    """
    Gets the app client
    """
    if module: client_name = f'{module}.{client_name}'
    return _cregistry.get(client_name, **kwargs)

def register_client_hook(
    client_name: str,
    func: Union[Callable[..., Any], str],
    kind: Literal['pre', 'post'] = 'post',
    module: Optional[str] = None,
):
    """
    Registers a client hook
    """
    if module: client_name = f'{module}.{client_name}'
    _cregistry.register_hook(client_name, func, kind = kind)