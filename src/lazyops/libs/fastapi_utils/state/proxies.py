"""
Proxied Types
"""

from typing import Dict, TypeVar, Optional, Union, Any, TYPE_CHECKING
from .registry import (
    get_global_client, 
    get_client, 
    register_client, 
    update_client_registry_mapping, 
    ClientT, 
    ClientTypeT
)
from lazyops.types.lazydict import LazyDict, RT

if TYPE_CHECKING:
    from aiokeydb import TaskQueue
    from lazyops.types.models import BaseSettings


class ClientProxyMetaClass(type):
    """
    A Custom Proxy that lazily defers initialization of a client until it is called
    """

    _clients: Dict[str, Union[ClientT, ClientTypeT]] = {}
    _module_name: str = None
    is_global: Optional[bool] = True

    @property
    def module_name(cls) -> str:
        """
        Returns the module name
        """
        if cls._module_name is None:
            cls._module_name = cls.__module__.split('.', 1)[0].strip()
        return cls._module_name

    def set_client_mapping(cls, mapping: Dict[str, str]):
        """
        Sets the client mapping
        """
        for key in mapping:
            if cls.module_name not in key:
                mapping[f'{cls.module_name}.{key}'] = mapping.pop(key)
        update_client_registry_mapping(mapping = mapping)

    def add_client_mapping(cls, name: str, module_path: str):
        """
        Adds a client mapping
        """
        if cls.module_name not in name:
            name = f'{cls.module_name}.{name}'
        update_client_registry_mapping(mapping = {name: module_path})

    def get_or_init(cls, name: str, **kwargs) -> Union[ClientT, ClientTypeT]:
        """
        Initializes the client if it is not already initialized
        """
        if name not in cls._clients:
            key = f'{cls.module_name}.{name}' if cls.module_name not in name else name
            if cls.is_global:
                cls._clients[name] = get_global_client(name = key)
            else:
                cls._clients[name] = get_client(name = key, **kwargs)
        return cls._clients[name]
    
    def register(cls, client: Union[ClientT, ClientTypeT], name: str):
        """
        Registers a client
        """
        key = f'{cls.module_name}.{name}' if cls.module_name not in name else name
        if register_client(client = client, name = key) or name not in cls._clients:
            cls._clients[name] = client
    
    def __getitem__(cls, name: str) -> Union[ClientT, ClientTypeT]:
        """
        Returns a client
        """
        return cls.get_or_init(name = name)
    
    def __len__(cls) -> int:
        """
        Returns the number of clients
        """
        return len(cls._clients)
    
    

class QueueManagerMetaClass(type):
    """
    Global Queue Manager
    """
    name: Optional[str] = 'queuemanager'
    _queues: Dict[str, 'TaskQueue'] = {}
    _queue_schemas: Dict[str, Dict[str, Dict[str, Any]]] = None
    
    _settings: Optional['BaseSettings'] = None
    _module_name: str = None

    @property
    def module_name(cls) -> str:
        """
        Returns the module name
        """
        if cls._module_name is None:
            cls._module_name = cls.__module__.split('.', 1)[0].strip()
        return cls._module_name

    def get_settings(cls) -> 'BaseSettings':
        """
        Returns the settings object

        - Should be overwritten by the subclass
        """
        raise NotImplementedError
    
    @property
    def settings(cls) -> 'BaseSettings':
        """
        Returns the settings object
        """
        if cls._settings is None:
            cls._settings = cls.get_settings()
            register_client(cls, name = f'{cls.module_name}.{cls.name}')
        return cls._settings
    
    def get_queue_schemas(cls) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Returns the queue schemas

        - Should be overwritten by the subclass
        """
        raise NotImplementedError
    
    @property
    def queue_schemas(cls) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Returns the queue schemas
        """
        if cls._queue_schemas is None:
            cls._queue_schemas = cls.get_queue_schemas()
        return cls._queue_schemas
    
    def get_task_queue(cls, name: str, kind: Optional[str] = None) -> 'TaskQueue':
        """
        Returns a Task Queue

        - Should be overwritten by the subclass
        """
        raise NotImplementedError
    
    def get_or_init_queue(cls, queue_name: str, kind: Optional[str] = None) -> 'TaskQueue':
        """
        Returns the queue object
        """
        if queue_name not in cls._queues:
            if kind is None:
                for k, v in cls.queue_schemas.items():
                    if queue_name in v:
                        kind = k
                        break
            try:
                q = cls.get_task_queue(
                    name = queue_name,
                    kind = kind,
                )
            except Exception as e:
                q = False
            cls._queues[queue_name] = q
        return cls._queues[queue_name]
    
    def get_queue(cls, queue_name: str, kind: Optional[str] = None) -> Optional['TaskQueue']:
        """
        Returns the queue object
        """
        return cls.get_or_init_queue(queue_name = queue_name, kind = kind)
    

    def __getitem__(cls, queue_name: str) -> Optional['TaskQueue']:
        """
        Returns the queue object
        """
        return cls.get_queue(queue_name = queue_name)
    

class ProxyDict(LazyDict):
    """
    A Proxy Dictionary that lazily defers initialization of a client until it is called

    These are non-global clients
    """
    initialize_objects: Optional[bool] = True
    exclude_schema_attrs: Optional[bool] = True
    proxy_schema: Optional[Dict[str, str]] = None

    def __init__(self, **kwargs):
        if self.proxy_schema is None:
            raise NotImplementedError('Proxy Schema not set')
        self._dict = self.proxy_schema
        if self.exclude_schema_attrs:
            self.excluded_attrs = list(self.proxy_schema.keys())
        self.post_init(**kwargs)
    
    def post_init(self, **kwargs):
        """
        Post Initialization to be overwritten by the subclass
        """
        pass

    def obj_initializer(self, name: str, obj: RT, **kwargs) -> RT:
        """
        Returns the object initializer

        - Can be overwritten by the subclass to modify the object initialization
        """
        return obj(**kwargs)
    
    def get_or_init(self, name: str, default: Optional[RT] = None) -> RT:
        """
        Get an attribute from the dictionary
        If it does not exist, set it to the default value
        """
        if name not in self._dict:
            if default: self._dict[name] = default
            else: raise ValueError(f"Default value for {name} is None")
        from lazyops.utils.lazy import lazy_import
        if isinstance(self._dict[name], str):
            self._dict[name] = lazy_import(self._dict[name])
            if self.initialize_objects:
                self._dict[name] = self.obj_initializer(name, self._dict[name])
        elif isinstance(self._dict[name], tuple):
            obj_class, kwargs = self._dict[name]
            if isinstance(obj_class, str):
                obj_class = lazy_import(obj_class)
            for k,v in kwargs.items():
                if callable(v): kwargs[k] = v()
            self._dict[name] = self.obj_initializer(name, obj_class, **kwargs)
        elif isinstance(self._dict[name], dict):
            self._dict[name] = self.obj_initializer(name, type(self), **self._dict[name])
        return self._dict[name]
