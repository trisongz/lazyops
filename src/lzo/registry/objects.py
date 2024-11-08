from __future__ import annotations

"""
Registry of Singleton Objects that can be lazily loaded
"""
import abc
from typing import Dict, TypeVar, Optional, Type, Union, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .mixins import RegisteredObject

RObjectT = TypeVar('RObjectT', bound = 'RegisteredObject')

_module_object_registry: Dict[str, Type[RObjectT]] = {}
_init_module_object_registry: Dict[str, RObjectT] = {}
_uninit_module_object_registry: Dict[str, Dict[str, str]] = {}


"""
We can either implement a flattened dict or a nested dict

Flattened:
{
    'module.{obj.kind}.{obj.name}': object
}

"""

def register_object(
    obj: Type[RObjectT],
) -> None:
    """
    Registers the object with the registry
    """
    global _module_object_registry, _uninit_module_object_registry
    from lzl.logging import logger
    from lzl.io.ser import get_object_classname

    if hasattr(obj, '_rxtra') and obj._rxtra.get('registered'): 
        logger.warning(f'Object {obj._rxtra["obj_ref"]} already registered with {obj._rxtra["module"]}')
        return

    cls_name = get_object_classname(obj, is_type = True)
    cls_module = obj.__module__.split('.')[0]

    obj_ref = cls_module
    if hasattr(obj, 'kind'): obj_ref += f'.{obj.kind}'
    if hasattr(obj, 'name'): obj_ref += f'.{obj.name}'
    # if 
    




    if cls_module not in _module_object_registry:
        _module_object_registry[cls_module] = {}

    global _module_client_registry, _uninit_module_client_registry
    from lzl.logging import logger
    from lzl.io.ser import get_object_classname

    cls_name = get_object_classname(client, is_type = True)
    cls_module = client.__module__.split('.')[0]

    if cls_module not in _module_client_registry:
        _module_client_registry[cls_module] = {}
    
