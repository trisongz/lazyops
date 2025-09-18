from __future__ import annotations

"""Registry helpers for configuration settings objects."""

import inspect
from pathlib import Path
import typing as t

from .base import MRegistry, combine_parts

if t.TYPE_CHECKING:
    from lzo.types.base import RegisteredSettings

    RSettingT = t.TypeVar('RSettingT', bound='RegisteredSettings')
else:
    RSettingT = t.TypeVar('RSettingT')

__all__ = [
    'get_app_settings',
    'register_app_settings',
    'register_initialized_settings',
    'register_settings',
]

_sregistry: MRegistry['RSettingT'] = MRegistry('settings')


def register_initialized_settings(settings: 'RSettingT') -> None:
    """Cache an already constructed settings object.

    Args:
        settings: Instance of a :class:`RegisteredSettings` subclass.

    Raises:
        ValueError: If another settings instance is already registered for the
            same module/submodule combination.
    """

    if hasattr(settings, '_rxtra'):
        _sregistry._register_initialized(settings._rxtra['registry_name'], settings)
        return
    cls_module = (
        settings._rmodule
        if getattr(settings, '_rmodule', None) is not None
        else settings.__module__.split('.')[0]
    )
    cls_submodule = settings._rsubmodule if getattr(settings, '_rsubmodule', None) is not None else None
    registry_name = combine_parts(cls_module, cls_submodule)
    if registry_name in _sregistry.init_registry:
        raise ValueError(f'Module {registry_name} already has registered settings')
    _sregistry._register_initialized(registry_name, settings)


def register_settings(settings: t.Union[t.Type['RSettingT'], 'RSettingT']) -> None:
    """Register settings for lazy instantiation and discovery.

    Args:
        settings: Settings class or instance to register. Classes are stored for
            lazy creation; instances are cached immediately.
    """

    if not isinstance(settings, type):
        register_initialized_settings(settings)
        return
    cls_name = _sregistry.get_classname(settings, is_type=True)
    cls_module = (
        settings._rmodule
        if getattr(settings, '_rmodule', None) is not None
        else settings.__module__.split('.')[0]
    )
    cls_submodule = settings._rsubmodule
    registry_name = combine_parts(cls_module, cls_submodule)
    if registry_name in _sregistry.mregistry:
        _sregistry.logger.warning(
            f'Settings {registry_name} already registered with {cls_module}'
        )
        return

    module_config_path = Path(inspect.getfile(settings)).parent
    settings._rxtra['module'] = cls_module
    settings._rxtra['submodule'] = cls_submodule
    settings._rxtra['cls_name'] = cls_name
    settings._rxtra['module_config_path'] = module_config_path
    settings._rxtra['registry_name'] = registry_name
    settings._rxtra['registered'] = True

    if '__main__' not in cls_module:
        p = module_config_path
        m_path, iters = None, 0
        while p.name != cls_module and iters < 4:
            p = p.parent
            iters += 1
            if p.name == cls_module:
                m_path = p
                break
        if m_path is not None:
            settings._rxtra['module_path'] = m_path

    _sregistry[cls_module] = settings


def register_app_settings(
    module: str,
    settings_path: str,
    submodule: t.Optional[str] = None,
) -> None:
    """Register a lazily importable settings object.

    Args:
        module: Top-level package name used for lookup.
        settings_path: Dotted path to the settings class.
        submodule: Optional nested namespace for the settings class.
    """

    registry_name = combine_parts(module, submodule)
    if registry_name in _sregistry.mregistry:
        return
    _sregistry.uninit_registry[registry_name] = settings_path


def get_app_settings(
    module: str,
    submodule: t.Optional[str] = None,
    **kwargs: t.Any,
) -> 'RegisteredSettings':
    """Fetch settings for ``module`` (and optional ``submodule``).

    Args:
        module: Top-level package name used during registration.
        submodule: Optional namespace component for nested settings.
        **kwargs: Forwarded to the ``RegisteredSettings`` constructor when
            instantiation is required.

    Returns:
        Lazily constructed settings instance, cached for future retrievals.
    """

    registry_name = combine_parts(module, submodule)
    return _sregistry.get(registry_name, **kwargs)
