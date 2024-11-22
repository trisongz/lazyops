from __future__ import annotations

"""
The Base Extensible Client Class
"""

import abc
import contextlib
from lzl.logging import logger, null_logger, Logger
from lzl.types import eproperty
from typing import Optional, Type, TypeVar, Union, Set, List, Any, Dict, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from kvdb import KVDBSession
    from lzl.io import PersistentDict
    from lzl.pool import ThreadPool
    from lzo.registry.clients import RClientT
    from lzo.types.base import RegisteredSettings, BaseModel

    DataSchema = TypeVar('DataSchema', bound = BaseModel)
    ResultSchema = TypeVar('ResultSchema', bound = BaseModel)



class BaseClient(abc.ABC):
    """
    The Base Client Class
    """

    name: Optional[str] = None

    verbosity: Optional[int] = 0
    enable_registration: Optional[bool] = True
    schemas: Dict[str, Union[Type['DataSchema'], Type['ResultSchema'], str]] = {}

    cache_enabled: Optional[bool] = True
    cache_expiration: Optional[int] = 60 * 60 * 24 * 3 # 3 days
    cache_shared_global: Optional[bool] = False
    cachable_default: Optional[bool] = None # The default value for cache enabled
    
    serialization: Optional[str] = 'json'
    serialization_compression: Optional[str] = 'zstd'
    serialization_compression_level: Optional[int] = 19 # 6 for default (lz4, zlib) 19 for zstd

    data_expiration: Optional[int] = None
    data_shared_global: Optional[bool] = False
    
    _extra: Dict[str, Any] = {}

    def __init__(self, *args, **kwargs):
        """
        Initializes the BaseClient
        """
        self._kwargs = kwargs
        self.pre_init(**kwargs)
        self.cls_init(**kwargs)
        self.post_init(**kwargs)
        self.configure_schemas(**kwargs)
        self.finalize_init(**kwargs)
        if self.enable_registration:
            self._register_client(**kwargs)
    

    def pre_init(self, **kwargs):
        """
        Pre-Initializes the BaseClient
        """
        pass

    def post_init(self, **kwargs):
        """
        Post-Initializes the BaseClient
        """
        pass

    def configure_schemas(self, **kwargs):
        """
        Configures the schemas
        """
        for name, schema in self.schemas.items():
            if isinstance(schema, str):
                schema = self._import(schema)
            self.schemas[name] = schema
        return self

    def cls_init(self, **kwargs):
        """
        Initializes the BaseClient
        """
        pass
    
    def finalize_init(self, **kwargs):
        """
        Finalizes the BaseClient
        """
        pass


    @eproperty
    def logger(self) -> 'Logger':
        """
        Gets the logger
        """
        return logger
    
    @eproperty
    def null_logger(self) -> 'Logger':
        """
        Gets the null logger
        """
        return null_logger
    
    @property
    def autologger(self) -> 'Logger':
        """
        Gets the auto logger
        """
        return self.logger if (
            self.settings.is_development_env or 
            self.verbosity >= 2
        ) else self.null_logger
    
    @eproperty
    def settings(self) -> 'RegisteredSettings':
        """
        Returns the settings
        """
        from lzo.registry.settings import get_app_settings
        return get_app_settings(self.__module__.__name__)
    
    @eproperty
    def pooler(self) -> 'ThreadPool':
        """
        Returns the thread pool
        """
        from lzl.pool import ThreadPool
        return ThreadPool
    

    @eproperty
    def kdb(self) -> 'KVDBSession':
        """
        [JSON Serializer] Returns the KVDB Session
        """
        return self.settings.ctx.get_kdb(self.name)
    
    @eproperty
    def rkdb(self) -> 'KVDBSession':
        """
        [Raw] Returns the Raw KVDB Session
        """
        return self.settings.ctx.get_kdb(f'{self.name}-raw', serializer = None, decode_responses = True)


    def get_extra_ser_pdict_kwargs(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the extra serialization kwargs for the persistent dict
        """
        return {}

    @eproperty
    def data(self) -> 'PersistentDict':
        """
        Gets the Persistent Dict for data
        """
        serializer_kwargs = {
            'compression': self.serialization_compression,
            'compression_level': self.serialization_compression_level,
            'raise_errors': True,
            **self.get_extra_ser_pdict_kwargs('data'),
        }
        base_key = f'{self.settings.ctx.module_name}.{self.name}.data' if \
            self.data_shared_global else \
            f'{self.settings.ctx.module_name}.{self.settings.app_env.name}.{self.name}.data'
        return self.settings.ctx.get_pdict(
            base_key = base_key,
            expiration = self.data_expiration,
            serializer = self.serialization,
            serializer_kwargs = serializer_kwargs,
        )

    @eproperty
    def cache(self) -> 'PersistentDict[str, ResultSchema]':
        """
        Gets the Persistent Dict for cache
        """
        serializer_kwargs = {
            'compression': self.serialization_compression,
            'compression_level': self.serialization_compression_level,
            'raise_errors': True,
            **self.get_extra_ser_pdict_kwargs('cache'),
        }
        base_key = f'{self.settings.ctx.module_name}.{self.name}.cache' if \
            self.cache_shared_global else \
            f'{self.settings.ctx.module_name}.{self.settings.app_env.name}.{self.name}.cache'
        return self.settings.ctx.get_pdict(
            base_key = base_key,
            expiration = self.cache_expiration,
            serializer = self.serialization,
            serializer_kwargs = serializer_kwargs,
        )



    """
    Utilities
    """

    @contextlib.contextmanager
    def catch(self, exc: Type['Exception'], msg: Optional[str] = None, fatal: Optional[bool] = False):
        """
        Catches an exception
        """
        try:
            yield
        except Exception as e:
            log = self.logger.trace if fatal else self.autologger.trace
            log(f'Handling Error: {msg}', e, prefix = self.name)
            if fatal: raise exc(msg, error = e) from e



    def run(
        self,
        data: 'DataSchema',
        cachable: Optional[bool] = None,
        **kwargs,
    ) -> 'ResultSchema':
        """
        Runs the client
        """
        raise NotImplementedError("run must be implemented by the Client")
    
    async def arun(
        self,
        data: 'DataSchema',
        cachable: Optional[bool] = None,
        **kwargs,
    ) -> 'ResultSchema':
        """
        Runs the client
        """
        raise NotImplementedError("arun must be implemented by the Client")
    

    def __call__(
        self,
        data: 'DataSchema',
        cachable: Optional[bool] = None,
        is_async: Optional[bool] = True,
        **kwargs,
    ) -> 'ResultSchema':
        """
        Runs the Client
        """
        if cachable is None: cachable = self.cachable_default
        method = self.arun if is_async else self.run
        return method(data, cachable = cachable, **kwargs)


    """
    Helper Methods
    """
    
    def _import(self, name: str, **kwargs) -> Any:
        """
        Imports a module
        """
        from lzl.load import lazy_import
        return lazy_import(name, **kwargs)
    

    def _register_client(self, **kwargs):
        """
        Registers the client
        """
        self.settings.ctx.register_client(self, **kwargs)


    def _get_client(self, name: str, **kwargs) -> 'RClientT':
        """
        Gets a client
        """
        return self.settings.ctx.get_client(name, **kwargs)