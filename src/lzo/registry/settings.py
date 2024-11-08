from __future__ import annotations

"""
Registry of BaseSettings
"""

import inspect
from pathlib import Path
from .base import MRegistry
from typing import Optional, Dict, Any, List, Union, TypeVar, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from lzo.types import BaseSettings
    from lzo.types.base import RegisteredSettings

    RSettingT = TypeVar('RSettingT', bound = RegisteredSettings)

# V2 Implementation of Registry
_sregistry: MRegistry['RSettingT'] = MRegistry('settings')

def register_initialized_settings(
    settings: 'RSettingT',
) -> None:
    """
    Registers an initialized settings
    """
    if hasattr(settings, '_rxtra'):
        return _sregistry._register_initialized(settings._rxtra['module'], settings)    
    cls_module = settings._rmodule \
        if getattr(settings, '_rmodule', None) is not None else \
        settings.__module__.split('.')[0]
    
    if cls_module in _sregistry.init_registry:
        raise ValueError(f'Module {cls_module} already has registered settings')
    return _sregistry._register_initialized(cls_module, settings)


def register_settings(
    settings: Union[Type['RSettingT'], 'RSettingT'],
) -> None:
    """
    Registers the module settings
    """
    if not isinstance(settings, type):
        return register_initialized_settings(settings)
    cls_name = _sregistry.get_classname(settings, is_type = True)
    cls_module = settings._rmodule \
        if getattr(settings, '_rmodule', None) is not None else \
        settings.__module__.split('.')[0]
    
    if cls_module in _sregistry.mregistry:
        _sregistry.logger.warning(f'Settings {cls_name} already registered with {cls_module}')
        return

    module_config_path = Path(inspect.getfile(settings)).parent
    settings._rxtra['module'] = cls_module
    settings._rxtra['cls_name'] = cls_name
    settings._rxtra['module_config_path'] = module_config_path
    settings._rxtra['registered'] = True
    
    if '__main__' not in cls_module:
        # try to determine the module path
        # while preventing infinite loops
        p = module_config_path
        m_path, iters = None, 0
        while p.name != cls_module and iters < 4:
            p = p.parent
            iters += 1
            if p.name == cls_module:
                m_path = p
                break
        if m_path is not None: settings._rxtra['module_path'] = m_path
    
    _sregistry[cls_module] = settings

    # _module_settings_registry[cls_module] = settings
    # if cls_module in _uninit_module_settings_registry:
    #     _uninit_module_settings_registry.pop(cls_module)
    # logger.info(f'Registered: {cls_name}', colored = True, prefix = cls_module)


def register_app_settings(
    module: str,
    settings_path: str,
):
    """
    Registers the app settings for lazily loading
    """
    if module in _sregistry.mregistry: return
    _sregistry.uninit_registry[module] = settings_path


def get_app_settings(
    module: str,
    **kwargs,
) -> 'RegisteredSettings':  # sourcery skip: extract-method
    """
    Gets the app settings
    """
    return _sregistry.get(module, **kwargs)
