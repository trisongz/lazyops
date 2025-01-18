from __future__ import annotations

"""
Base Registry Objects
"""
import os
import inspect
import collections.abc
from pathlib import Path
from lzl.types import Literal
from lzl.proxied import ProxyObject
from typing import Dict, TypeVar, Optional, Type, Union, Any, Generic, Callable, MutableMapping, TYPE_CHECKING

RT = TypeVar('RT')

def combine_parts(*parts: Optional[str], sep: Optional[str] = '.') -> str:
    """
    Combines the parts into a single string
    """
    return sep.join(p for p in parts if p)

class MRegistry(Generic[RT]):
    """
    A Mutable Mapping that can be used to store objects
    """

    mregistry: Dict[str, Type[RT]] = {}
    uninit_registry: Dict[str, str] = {}
    init_registry: Dict[str, RT] = {}

    prehooks: Dict[str, Callable[..., Any]] = {}
    posthooks: Dict[str, Callable[..., Any]] = {}

    def __init__(
        self,
        name: str,
        verbose: Optional[bool] = False,
        **kwargs,
    ):
        """
        Initializes the Registry
        """
        from lzl.logging import logger
        from lzl.io.ser import get_object_classname
        from lzl.load import lazy_import
        
        self.name = name
        self.logger = logger
        self.get_classname = get_object_classname
        self.lazy_import = lazy_import
        self.verbose = verbose
        self.idx: Dict[str, RT] = {}
        self._extra: Dict[str, Any] = {}

    def _register(self, key: str, value: RT) -> None:
        """
        Registers an item in the registry
        """
        self.mregistry[key] = value
        if key in self.uninit_registry:
            self.uninit_registry.pop(key)
        if os.getenv('MUTE_LZ_REGISTRY', 'false').lower() in {'true', '1'}: return
        if not isinstance(value, str) and getattr(value, '_rverbose', self.verbose):
            self.logger.info(f'Registered: {key}', colored = True, prefix = self.name)

    def __setitem__(self, key: str, value: RT) -> None:
        """
        Sets an item in the registry
        """
        return self._register(key, value)
    
    def register_prehook(self, key: str, func: Union[Callable[..., Any], str]):
        """
        Registers a prehook
        """
        self.prehooks[key] = func
    
    def register_posthook(self, key: str, func: Union[Callable[..., Any], str]):
        """
        Registers a posthook
        """
        self.posthooks[key] = func

    def register_hook(self, key: str, func: Union[Callable[..., Any], str], kind: Literal['pre', 'post'] = 'pre'):
        """
        Registers a hook
        """
        if kind == 'pre': self.register_prehook(key, func)
        elif kind == 'post': self.register_posthook(key, func)

    def run_obj_init(self, key: str, obj: Union[Type[RT], RT], **kwargs) -> RT:
        """
        Runs the object initialization
        """
        # Prehooks allow modification of the kwargs
        if key in self.prehooks:
            if isinstance(self.prehooks[key], str):
                self.prehooks[key] = self.lazy_import(self.prehooks[key])
            kwargs = self.prehooks[key](**kwargs)

        # This may potentially be a ProxyObject
        # and if so, we should skip the initialization
        if isinstance(obj, ProxyObject):
            if self.verbose: self.logger.info(f'Skipping Initialization for Proxy Object: {key}', colored = True, prefix = self.name)
        else:
            obj = obj(**kwargs)
        # Posthooks allow modification of the object
        if key in self.posthooks:
            if isinstance(self.posthooks[key], str):
                self.posthooks[key] = self.lazy_import(self.posthooks[key])
            obj = self.posthooks[key](obj)
        return obj

    def _register_initialized(self, key: str, value: RT) -> None:
        """
        Registers an initialized item in the registry
        """
        self.init_registry[key] = value

    def _get(self, key: str, _raise_error: Optional[bool] = True, **kwargs) -> RT:
        """
        Gets an item from the registry
        """
        if key in self.init_registry:
            # print(f'Getting init key: {key}: {self.init_registry[key]} {type(self.init_registry[key])}')
            return self.init_registry[key]
        
        if key in self.uninit_registry:
            # print(f'Getting uninit key: {key}')
            _path = self.uninit_registry[key]
            _obj = self.lazy_import(_path)
            self.init_registry[key] = self.run_obj_init(key, _obj, **kwargs)
            self.uninit_registry.pop(key, None)
            return self.init_registry[key]
        
        if key in self.mregistry:
            # print(f'Getting mregistry key: {key}')
            _obj = self.mregistry[key]
            self.init_registry[key] = self.run_obj_init(key, _obj, **kwargs)
            return self.init_registry[key]

        if not _raise_error: return None
        raise KeyError(f'Key {key} not found in {self.name}')
    
    def get(self, key: str, **kwargs) -> RT:
        """
        Gets an item from the registry
        """
        if key in self.idx: return self.idx[key]
        # print(f'Getting key: {key}')
        if (item := self._get(key, _raise_error = False, **kwargs)) is not None:
            self.idx[key] = item
            return item
        if possible_key := self.search_for_parent(key, raise_error = False):
            if possible_key in self.idx:
                self.idx[key] = self.idx[possible_key]
                return self.idx[key]
            if (item := self._get(possible_key, _raise_error = False, **kwargs)) is not None:
                self.idx[key] = item
                return item
        raise KeyError(f'Key {key} not found in {self.name}: init: `{list(self.init_registry.keys())}`, idx: `{list(self.idx.keys())}`')

    def get_module_path(self, obj: Type[RT]) -> Path:
        """
        Gets the module path
        """
        return Path(inspect.getfile(obj)).parent

    def search_for_parent(self, key: str, raise_error: Optional[bool] = True) -> Optional[str]:
        """
        Searches for the parent
        
        if 'b.c' is provided, it will search for 'x.b.c' and return 'a.b.c' if it exists
        """
        if self.init_registry:
            for k in self.init_registry:
                if k.endswith(key): return k
        
        if self.uninit_registry:
            for k in self.uninit_registry:
                if k.endswith(key): return k
        
        if self.mregistry:
            for k in self.mregistry:
                if k.endswith(key): return k
        
        if not raise_error: return None
        raise KeyError(f'Key {key} not found in {self.name}')

    def __getitem__(self, key: str) -> RT:
        """
        Gets an item from the registry
        """
        return self.get(key)