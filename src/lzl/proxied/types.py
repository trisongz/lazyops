from __future__ import annotations

"""
Proxied Types
"""

import collections.abc
# from lzl.logging import logger
from typing import Any, Dict, Optional, Union, Iterable, List, Type, Set, Callable, Mapping, MutableMapping, Tuple, TypeVar


KT = TypeVar('KT')
VT = TypeVar('VT')
DictValue = Union[VT, Callable[[], VT], Tuple[str, Dict[str, Any]], str, Any]

class ProxyDict(collections.abc.MutableMapping, MutableMapping[KT, VT]):
    """
    Proxied Dictionary that can lazily initialize the values
    """
    _dict: Dict[KT, DictValue] = {}
    _initialized: Dict[KT, bool] = {} 
    # _rxtra: Dict[str, Any] = {}
    _excluded_attrs: Set[str] = set()
    _pdict_attrs: Set[str] = {
        'get_or_init',
        'keys',
        'values',
        'items',
        'get',
        'clear',
        'pop',
        'popitem',
        'setdefault',
        'initialize_objects',
        'update',
        'post_init',
        'pre_init',
        'cls_init',
        'cls_post_init',
        'proxy_schema',
        'module',
        'components',
        '_init_component',
        '_prevalidate_component',
        '_init_default',
        # '_rxtra',
    }

    module: Optional[str] = None
    components: Optional[List[str]] = None
    proxy_schema: Optional[Dict[str, str]] = {}
    initialize_objects: bool = False

    def __init__(
        self,
        initialize_objects: Optional[bool] = None,
        module: Optional[str] = None,
        components: Optional[List[str]] = None,
        proxy_schema: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """
        Initializes the Proxy Dict
        """
        # self._dict.clear()
        # self._initialized.clear()
        
        self.cls_init(**kwargs)
        if initialize_objects is not None: self.initialize_objects = initialize_objects
        if module is not None: self.module = module
        if components is not None: self.components = components
        if proxy_schema is not None: self.proxy_schema = proxy_schema
        self.cls_post_init(**kwargs)
        # self.proxy_schema = proxy_schema if proxy_schema is not None else {}
        self.pre_init(**kwargs)
        self.post_init(**kwargs)
        # logger.info(f'Initialized ProxyDict: {self.module} - {self.proxy_schema}')

    def cls_init(self, **kwargs):
        """
        Class Initialization
        """
        pass
        
    def cls_post_init(self, **kwargs):
        """
        Class Post Initialization
        """
        pass
        
    def pre_init(self, **kwargs):
        """
        Pre Initialization
        """
        # logger.info(f'Initializing ProxyDict: {self.module}')
        if self.components:
            for component in self.components:
                if component not in self.proxy_schema:
                    ref_name = f'{self.module}.{component}' if self.module else component
                    self.proxy_schema[component] = ref_name
        return self

    def post_init(self, **kwargs):
        """
        Post Initialization
        """
        pass
    
    def __init_subclass__(cls: Type['ProxyDict']) -> None:
        """
        Subclass Hook to add defined attributes to the excluded list
        """
        # from lzl.logging import logger
        # print(f'Clearing ProxyDict: {cls.__name__} - {cls._dict} - {cls._initialized}')
        cls._dict = {}
        cls._initialized = {}
        for attr in dir(cls):
            # if attr in cls._excluded_attrs or attr in cls._pdict_attrs: continue
            if attr in cls._pdict_attrs: continue
            if attr.startswith('_'): continue
            # logger.info(f'Excluding ProxyDict Attribute: {attr}')
            cls._pdict_attrs.add(attr)
        return super().__init_subclass__()
    
    def _init_component(self, name: KT, default: Optional[VT] = None) -> None:
        """
        Initializes a component
        """
        pass

    def _prevalidate_component(self, name: KT) -> None:
        """
        Validates the component
        """
        pass

    def _init_default(self, name: KT) -> None:
        """
        Initializes a default value
        """
        # logger.info(f'Initializing Attribute: {name}')
        from lzl.load import lazy_import
        if isinstance(self._dict[name], str):
            self._dict[name] = lazy_import(self._dict[name])
            if self.initialize_objects:
                self._dict[name] = self._dict[name]()
        elif isinstance(self._dict[name], tuple):
            obj_class, kwargs = self._dict[name]
            if isinstance(obj_class, str):
                obj_class = lazy_import(obj_class)
            for k,v in kwargs.items():
                if callable(v): kwargs[k] = v()
            self._dict[name] = obj_class(**kwargs)
        elif isinstance(self._dict[name], dict):
            self._dict[name] = type(self)(self._dict[name])
        elif isinstance(self._dict[name], type):
            self._dict[name] = self._dict[name]()
        self._initialized[name] = True

    def get_or_init(self, name: KT, default: Optional[VT] = None) -> VT:
        """
        Get an attribute from the dictionary
        If it does not exist, set it to the default value
        """
        # logger.info(f'Getting or Initializing Attribute: {name}')
        if name not in self._dict:
            self._prevalidate_component(name)
            if name in self.proxy_schema:
                self._init_component(name, default)
                self._initialized[name] = True
            elif default:
                self._dict[name] = default
            else:
                raise ValueError(f"Default value for {name} is None")
        if name not in self._initialized:
            self._init_default(name)
        return self._dict[name]
    
    def __getattr__(self, name: str) -> VT:
        """
        Get an attribute from the dictionary        
        """
        if (name.startswith('__') and name.endswith('__')) or \
            name.startswith('_r') or \
            name in self._excluded_attrs or \
            name in self._pdict_attrs:
            # print(f'Getting Attribute: {name}')
            # return getattr(self, name)
            # try:
            return super().__getattr__(name)
            # except AttributeError:
            #     return getattr(self, name)
            # return getattr(self, name)
        return self.get_or_init(name, None)
    
    def __setattr__(self, name: str, value: VT) -> None:
        """
        Set an attribute in the dictionary
        """
        if (name.startswith('__') and name.endswith('__')) or \
            name.startswith('_r') or \
            name in self._excluded_attrs or \
            name in self._pdict_attrs:
            # print(f'Setting Attribute: {name}: {value}')
            return super().__setattr__(name, value)
            # return setattr(self, name, value)
        self._dict[name] = value
        

    def __getitem__(self, name: KT) -> VT:
        """
        Get an attribute from the dictionary        
        """
        return self.get_or_init(name, None)
    
    def __setitem__(self, name: KT, value: VT) -> None:
        """
        Set an attribute in the dictionary        
        """
        self._dict[name] = value
    
    def __contains__(self, name: KT) -> bool:
        """
        Check if an attribute is in the dictionary        
        """
        return name in self._dict
    
    def __repr__(self) -> str:
        """
        Get a string representation of the dictionary
        """
        return repr(self._dict)
    
    def __str__(self) -> str:
        """
        Get a string representation of the dictionary
        """
        return str(self._dict)
    
    def __len__(self) -> int:
        """
        Get the length of the dictionary
        """
        return len(self._dict)
    
    def __iter__(self):
        """
        Iterate over the dictionary
        """
        return iter(self._dict)
    
    def __delitem__(self, key: Any) -> None:
        """
        Delete an item from the dictionary
        """
        del self._dict[key]
    
    def keys(self):
        """
        Get the keys of the dictionary
        """
        return self._dict.keys()
    
    def values(self):
        """
        Get the values of the dictionary
        """
        return self._dict.values()
    
    def items(self):
        """
        Get the items of the dictionary
        """
        return self._dict.items()
    
    def get(self, name: KT, default: Optional[VT] = None) -> VT:
        """
        Get an attribute from the dictionary
        If it does not exist, set it to the default value
        """
        return self.get_or_init(name, default)
    
