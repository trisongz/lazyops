from __future__ import annotations

from abc import ABC
from typing import TypeVar, Dict, Callable, Any, Union, Tuple, List, Optional

RT = TypeVar('RT')

# Misc Helpers
LazyDictValue = Union[RT, Callable[[], RT], Tuple[str, Dict[str, Any]], Any]

class LazyDict(ABC):
    """
    This Dict object is different in that 
    it takes str objects and converts them
    to the appropriate type through lazy importing
    """
    _dict: Dict[str, Union[LazyDictValue, Dict[str, LazyDictValue]]] = {}
    excluded_attrs: List[str] = []
    initialize_objects: bool = False

    def __init__(self, *args, **kwargs):
        # Allow initialization by passing keyword arguments or a dictionary
        if len(args) == 1 and not kwargs and isinstance(args[0], dict):
            self._dict = args[0]
        else:
            self._dict = dict(*args, **kwargs)

    def get_or_init(self, name: str, default: Optional[RT] = None) -> RT:
        """
        Get an attribute from the dictionary
        If it does not exist, set it to the default value
        """
        if name not in self._dict:
            if default:
                self._dict[name] = default
            else:
                raise ValueError(f"Default value for {name} is None")
        from lazyops.utils.lazy import lazy_import
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
        return self._dict[name]

    def __getattr__(self, name: str) -> RT:
        """
        Get an attribute from the dictionary        
        """
        if name.startswith('__') and name.endswith('__') or name in self.excluded_attrs:
            return getattr(self, name)
        return self.get_or_init(name, None)

    def __getitem__(self, name: str) -> RT:
        """
        Get an attribute from the dictionary        
        """
        return self.get_or_init(name, None)
    
    def __setitem__(self, name: str, value: RT) -> None:
        """
        Set an attribute in the dictionary        
        """
        self._dict[name] = value
    
    def __contains__(self, name: str) -> bool:
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
    
    def get(self, name: str, default: Optional[RT] = None) -> RT:
        """
        Get an attribute from the dictionary
        If it does not exist, set it to the default value
        """
        return self.get_or_init(name, default)
    

LazyDict.register(dict)