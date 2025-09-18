from __future__ import annotations

"""Client registry utilities for the LazyOps orchestration layer."""

import typing as t

from .base import MRegistry, combine_parts

if t.TYPE_CHECKING:
    from .mixins import RegisteredClient

    RClientT = t.TypeVar('RClientT', bound='RegisteredClient')
else:
    RClientT = t.TypeVar('RClientT')

__all__ = [
    'get_app_client',
    'register_app_client',
    'register_app_clients',
    'register_client',
    'register_client_hook',
    'register_initialized_client',
]

_cregistry: MRegistry['RClientT'] = MRegistry('clients')


def register_initialized_client(client: 'RClientT', **kwargs: t.Any) -> None:
    """Record an already instantiated client in the registry.

    Args:
        client: Concrete instance created by the caller.
        **kwargs: Currently unused; retained for API compatibility.
    """

    if hasattr(client, '_rxtra'):
        _cregistry._register_initialized(client._rxtra['registry_name'], client)
        return
    cls_name = _cregistry.get_classname(client, is_type=False)
    cls_module = (
        client._rmodule
        if getattr(client, '_rmodule', None) is not None
        else client.__class__.__module__.split('.')[0]
    )
    cls_submodule = (
        client._rsubmodule if getattr(client, '_rsubmodule', None) is not None else None
    )
    client_name = client.name if getattr(client, 'name', None) is not None else cls_name

    registry_name = combine_parts(cls_module, cls_submodule, client_name)
    if registry_name in _cregistry.init_registry:
        return
    _cregistry._register_initialized(registry_name, client)


def register_client(client: t.Union[t.Type['RClientT'], 'RClientT'], **kwargs: t.Any) -> None:
    """Register a client class or instance for lazy lookup.

    Args:
        client: Client type or pre-instantiated object to register.
        **kwargs: Ignored but accepted for compatibility.
    """

    if not isinstance(client, type):
        register_initialized_client(client, **kwargs)
        return
    cls_name = _cregistry.get_classname(client, is_type=True)
    client_name = client.name if getattr(client, 'name', None) is not None else cls_name
    cls_module = (
        client._rmodule
        if getattr(client, '_rmodule', None) is not None
        else client.__module__.split('.')[0]
    )
    cls_submodule = client._rsubmodule if getattr(client, '_rsubmodule', None) is not None else None
    registry_name = combine_parts(cls_module, cls_submodule, client_name)
    if registry_name in _cregistry.mregistry:
        _cregistry.logger.warning(
            f'Client {client_name} already registered with `{registry_name}`'
        )
        return
    client._rxtra['module'] = cls_module
    client._rxtra['submodule'] = cls_submodule
    client._rxtra['cls_name'] = cls_name
    client._rxtra['client_name'] = client_name
    client._rxtra['registry_name'] = registry_name
    client._rxtra['module_path'] = _cregistry.get_module_path(client)
    client._rxtra['registered'] = True
    _cregistry[registry_name] = client


def register_app_client(
    client_name: str,
    client_path: str,
    module: t.Optional[str] = None,
    submodule: t.Optional[str] = None,
) -> None:
    """Register a lazily importable client path.

    Args:
        client_name: Friendly name used for lookup.
        client_path: Dotted import path to the client class.
        module: Optional module prefix used to namespacing entries.
        submodule: Additional namespace segment for nested registries.
    """

    registry_name = combine_parts(module, submodule, client_name)
    if registry_name in _cregistry.mregistry:
        return
    _cregistry.uninit_registry[registry_name] = client_path


def register_app_clients(
    clients: t.Mapping[str, str],
    module: t.Optional[str] = None,
    submodule: t.Optional[str] = None,
) -> None:
    """Bulk register lazily loaded client paths.

    Args:
        clients: Mapping of client names to dotted import paths.
        module: Optional module prefix shared across entries.
        submodule: Optional nested namespace for the group.
    """

    for client_name, client_path in clients.items():
        register_app_client(client_name, client_path, module=module, submodule=submodule)


def get_app_client(
    client_name: str,
    module: t.Optional[str] = None,
    submodule: t.Optional[str] = None,
    **kwargs: t.Any,
) -> 'RegisteredClient':
    """Retrieve a client by name, instantiating it if needed.

    Args:
        client_name: Identifier passed to :func:`register_client`.
        module: Optional module prefix used during registration.
        submodule: Optional nested namespace used during registration.
        **kwargs: Forwarded to the registered constructor when lazily importing.

    Returns:
        Registered client instance associated with ``client_name``.
    """

    registry_name = combine_parts(module, submodule, client_name)
    return _cregistry.get(registry_name, **kwargs)


def register_client_hook(
    client_name: str,
    func: t.Union[t.Callable[..., t.Any], str],
    kind: t.Literal['pre', 'post'] = 'post',
    module: t.Optional[str] = None,
    submodule: t.Optional[str] = None,
) -> None:
    """Attach a hook to a registered client.

    Args:
        client_name: Registry key that identifies the client.
        func: Callable or dotted import path executed as the hook.
        kind: Whether to run the hook before (``'pre'``) or after (``'post'``)
            instantiation.
        module: Optional module prefix used during registration.
        submodule: Optional nested namespace used during registration.
    """

    registry_name = combine_parts(module, submodule, client_name)
    _cregistry.register_hook(registry_name, func, kind=kind)
