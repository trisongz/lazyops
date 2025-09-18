from __future__ import annotations

"""Registry of singleton-like objects for lazy loading.

.. important::
   This module mirrors legacy behaviour and is intentionally left mostly
   untouched.  Several sections are incomplete (see
   ``docs/future-updates.md``) and should be revisited in a future refactor.
"""

import typing as t

if t.TYPE_CHECKING:
    from .mixins import RegisteredObject

RObjectT = t.TypeVar('RObjectT', bound='RegisteredObject')

_module_object_registry: t.Dict[str, t.Type['RObjectT']] = {}
_init_module_object_registry: t.Dict[str, 'RObjectT'] = {}
_uninit_module_object_registry: t.Dict[str, t.Dict[str, str]] = {}


def register_object(obj: t.Type['RObjectT']) -> None:
    """Register a lazily loadable object.

    Note:
        The implementation mirrors the legacy version and still contains
        unresolved TODOs.
    """

    global _module_object_registry, _uninit_module_object_registry
    from lzl.io.ser import get_object_classname
    from lzl.logging import logger

    if hasattr(obj, '_rxtra') and obj._rxtra.get('registered'):
        logger.warning(
            'Object %s already registered with %s',
            obj._rxtra['obj_ref'],
            obj._rxtra['module'],
        )
        return

    cls_name = get_object_classname(obj, is_type=True)
    cls_module = obj.__module__.split('.')[0]

    obj_ref = cls_module
    if hasattr(obj, 'kind'):
        obj_ref += f'.{obj.kind}'
    if hasattr(obj, 'name'):
        obj_ref += f'.{obj.name}'

    if cls_module not in _module_object_registry:
        _module_object_registry[cls_module] = {}

    global _module_client_registry, _uninit_module_client_registry  # type: ignore[name-defined]
    from lzl.io.ser import get_object_classname
    from lzl.logging import logger

    cls_name = get_object_classname(client, is_type=True)  # type: ignore[name-defined]
    cls_module = client.__module__.split('.')[0]  # type: ignore[name-defined]

    if cls_module not in _module_client_registry:
        _module_client_registry[cls_module] = {}
