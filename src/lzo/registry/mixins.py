from __future__ import annotations

"""
Registry Mixins
"""

import abc
import copy
from typing import Dict, Any, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from lzl.logging import Logger, NullLogger
    from pydantic import ConfigDict


def add_extra_meta(
    obj: Type['ExtraMeta'],
) -> None:
    """
    Adds extra metadata to the class
    """
    import inspect
    from pathlib import Path
    from lzl.logging import logger
    from lzl.io.ser import get_object_classname
    cls_name = get_object_classname(obj, is_type = True)
    cls_module = obj.__module__.split('.')[0]
    module_lib_path = Path(inspect.getfile(obj)).parent
    obj._rxtra['module'] = cls_module
    obj._rxtra['cls_name'] = cls_name
    obj._rxtra['module_lib_path'] = module_lib_path
    if '__main__' not in cls_module:
        # try to determine the module path
        # while preventing infinite loops
        p = module_lib_path
        m_path, iters = None, 0
        while p.name != cls_module and iters < 4:
            p = p.parent
            iters += 1
            if p.name == cls_module:
                m_path = p
                break
        if m_path is not None: obj._rxtra['module_path'] = m_path
    


class ExtraMeta(abc.ABC):
    """
    Adds extra metadata to the class
    """
    _rxtra: Dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs: Dict[str, Any]):
        add_extra_meta(cls)
        return super().__init_subclass__(**kwargs)

    @property
    def module_path(self) -> Path:
        """
        Gets the module root path
        """
        return self._rxtra.get('module_path')

    @property
    def module_lib_path(self) -> Path:
        """
        Returns the module lib path
        """
        return self._rxtra.get('module_lib_path')

    @property
    def module_name(self) -> str:
        """
        Returns the module name
        """
        return self._rxtra.get('module')
    
    @property
    def cls_name(self) -> str:
        """
        Returns the class name
        """
        return self._rxtra.get('cls_name')


class RegisteredClient(abc.ABC):
    """
    Registers this client with the registry
    """
    name: Optional[str] = None

    if TYPE_CHECKING:
        enable_registration: bool = None

    _rxtra: Dict[str, Any] = {}
    _rmodule: Optional[str] = None

    def __init_subclass__(cls, **kwargs: Dict[str, Any]):
        if not hasattr(cls, 'enable_registration') or cls.enable_registration is True:
            from lzo.registry.clients import register_client
            register_client(cls)
        return super().__init_subclass__(**kwargs)
    

    @classmethod
    def configure_registered(cls, **kwargs):
        """
        Configures the registered client
        """
        new = copy.deepcopy(cls)
        if kwargs.get('module'): new._rmodule = kwargs.pop('module')
        if kwargs.get('name'): new.name = kwargs.pop('name')
        if kwargs: new._rxtra.update(kwargs)
        return new

class RegisteredObject(abc.ABC):
    """
    Registers this object with the registry
    """
    name: Optional[str] = None
    kind: Optional[str] = None

    _rxtra: Dict[str, Any] = {}
    _rmodule: Optional[str] = None

    def __init_subclass__(cls, **kwargs: Dict[str, Any]):
        from lzo.registry.clients import register_client
        register_client(cls)
        return super().__init_subclass__(**kwargs)
    
    @classmethod
    def configure_registered(cls, **kwargs):
        """
        Configures the registered object
        """
        new = copy.deepcopy(cls)
        if kwargs.get('module'): new._rmodule = kwargs.pop('module')
        if kwargs.get('kind'): new.kind = kwargs.pop('kind')
        if kwargs.get('name'): new.name = kwargs.pop('name')
        if kwargs: new._rxtra.update(kwargs)
        return new
    


class RegisteredSettings(abc.ABC):
    """
    Registers this as the module settings
    """
    _rmodule: Optional[str] = None
    _rxtra: Dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs: 'ConfigDict'):
        from lzo.registry.settings import register_settings
        register_settings(cls)
        return super().__init_subclass__(**kwargs)
    
    @classmethod
    def configure_registered(cls, **kwargs):
        """
        Configures the registered settings
        """
        new = copy.deepcopy(cls)
        if kwargs.get('module'): new._rmodule = kwargs.pop('module')
        if kwargs: new._rxtra.update(kwargs)
        return new

    @property
    def _rverbose(self) -> bool:
        """
        Returns whether the object should be verbose
        """
        return self._rxtra.get('verbose', False)
    
    if TYPE_CHECKING:

        @property
        def module_path(self) -> Path:
            """
            Gets the module root path
            """
            ...

        @property
        def module_config_path(self) -> Path:
            """
            Returns the config module path
            """
            ...

        @property
        def module_name(self) -> str:
            """
            Returns the module name
            """
            ...


# class RegisteredWorkflow(abc.ABC):
#     """
#     Registers this workflow with the registry
#     """
#     name: Optional[str] = None

#     if TYPE_CHECKING:
#         enable_registration: bool = None

#     _rxtra: Dict[str, Any] = {}
#     _rmodule: Optional[str] = None

#     def __init_subclass__(cls, **kwargs: Dict[str, Any]):
#         if not hasattr(cls, 'enable_registration') or cls.enable_registration is True:
#             from lzo.registry.clients import register_client
#             register_client(cls)
#         return super().__init_subclass__(**kwargs)
    

#     @classmethod
#     def configure_registered(cls, **kwargs):
#         """
#         Configures the registered client
#         """
#         new = copy.deepcopy(cls)
#         if kwargs.get('module'): new._rmodule = kwargs.pop('module')
#         if kwargs.get('name'): new.name = kwargs.pop('name')
#         if kwargs: new._rxtra.update(kwargs)
#         return new
