from __future__ import annotations

"""
Abstract Base Classes for Global Clients

- Requires `kvdb`
"""


import abc
import contextlib
from kvdb.io import cachify as _cachify
from typing import Optional, Type, TypeVar, Union, Set, List, Any, Dict, Literal, TYPE_CHECKING


if TYPE_CHECKING:
    from kvdb import KVDBSession, PersistentDict
    from lazyops.libs.logging import Logger
    from lazyops.libs.abcs.configs.base import AppSettings
    from lazyops.libs.abcs.types.api import BaseSchema
    from lazyops.libs.pooler import ThreadPool
    from lazyops.libs.abcs.clients import ClientTypes
    from lazyops.libs.abcs.configs.ctx import ComponentSchemaT

    ResultSchema = TypeVar('ResultSchema', bound = BaseSchema)

cachify = _cachify.create_context()

class BaseGlobalClient(abc.ABC):

    name: Optional[str] = None
    kind: Optional[str] = 'client'
    
    verbosity: Optional[int] = 0
    enable_registration: Optional[bool] = True

    extra_validators_enabled: Optional[bool] = False
    result_schema: Type['BaseSchema'] = None

    cache_enabled: Optional[bool] = True
    cachify_ttl: Optional[int] = None
    cachify_shared_global: Optional[bool] = False
    cachify_enabled: Optional[bool] = True
    
    serialization: Optional[str] = 'json'
    serialization_compression: Optional[str] = 'zstd'
    serialization_compression_level: Optional[int] = 19 # 6 for default (lz4, zlib) 19 for zstd
    data_expiration: Optional[int] = None
    data_shared_global: Optional[bool] = False
    
    cache_expiration: Optional[int] = 60 * 60 * 24 * 3 # 3 days
    cache_shared_global: Optional[bool] = False


    _logger: Optional['Logger'] = None
    _null_logger: Optional['Logger'] = None

    _settings: Optional['AppSettings'] = None
    _pooler: Optional['ThreadPool'] = None
    _kdb: Optional['KVDBSession'] = None

    _data: Optional['PersistentDict'] = None
    _cache: Optional['PersistentDict'] = None

    def __init__(self, *args, **kwargs):
        """
        Initializes the GlobalClient Object
        """
        self._kwargs = kwargs
        self.pre_init(**kwargs)
        self.cls_init(**kwargs)
        self.post_init(**kwargs)
        self.finalize_init(**kwargs)
        if self.enable_registration:
            self._register_client(*args, **kwargs)
    
    def pre_init(self, **kwargs):
        """
        Pre-Initializes the GlobalClient
        """
        pass

    def post_init(self, **kwargs):
        """
        Post-Initializes the GlobalClient
        """
        pass

    def cls_init(self, **kwargs):
        """
        Initializes the GlobalClient Class
        """
        pass
    
    def finalize_init(self, **kwargs):
        """
        Finalizes the GlobalClient Initialization
        """
        pass

    @property
    def logger(self) -> 'Logger':
        """
        Gets the logger
        """
        if self._logger is None:
            self._logger = self.settings.logger
        return self._logger
    
    @property
    def null_logger(self) -> 'Logger':
        """
        Gets the null logger
        """
        if self._null_logger is None:
            self._null_logger = self.settings.null_logger
        return self._null_logger
    

    @property
    def autologger(self) -> 'Logger':
        """
        Automatic Logger that is enabled in devel mode
        """
        return self.logger if (self.settings.is_development_env or self.verbosity >= 2) else self.null_logger

    
    @property
    def settings(self) -> 'AppSettings':
        """
        Gets the settings
        """
        if self._settings is None:
            from lazyops.libs.abcs.configs.lazy import get_module_settings
            self._settings = get_module_settings(self.__module__.__name__)
        return self._settings
    
    @property
    def pooler(self) -> 'ThreadPool':
        """
        Gets the pooler
        """
        if self._pooler is None:
            from lazyops.libs.pooler import ThreadPooler
            self._pooler = ThreadPooler
        return self._pooler
    
    @property
    def kdb(self) -> 'KVDBSession':
        """
        Gets the keydb
        """
        if self._kdb is None:
            self._kdb = self.settings.ctx.get_kdb_session(self.name)
        return self._kdb
    
    def pdict_get_extra_serialization_kwargs(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the extra serialization kwargs
        """
        return {}
    
    @property
    def data(self) -> 'PersistentDict':
        """
        Gets the Persistent Dict for data
        """
        if self._data is None:
            serializer_kwargs = {
                'compression': self.serialization_compression,
                'compression_level': self.serialization_compression_level,
                'raise_errors': True,
                **self.pdict_get_extra_serialization_kwargs('data'),
            }
            base_key = f'{self.settings.ctx.module_name}.{self.name}.data' if \
                self.data_shared_global else \
                f'{self.settings.ctx.module_name}.{self.settings.app_env.name}.{self.name}.data'
        
            self._data = self.settings.ctx.get_persistent_dict(
                base_key = base_key,
                expiration = self.data_expiration,
                serializer = self.serialization,
                serializer_kwargs = serializer_kwargs,
            )
        return self._data


    @property
    def cache(self) -> 'PersistentDict':
        """
        Gets the Persistent Dict for cache
        """
        if self._cache is None:
            serializer_kwargs = {
                'compression': self.serialization_compression,
                'compression_level': self.serialization_compression_level,
                'raise_errors': True,
                **self.pdict_get_extra_serialization_kwargs('cache'),
            }
            base_key = f'{self.settings.ctx.module_name}.{self.name}.cache' if \
                self.cache_shared_global else \
                f'{self.settings.ctx.module_name}.{self.settings.app_env.name}.{self.name}.cache'
            self._cache = self.settings.ctx.get_persistent_dict(
                base_key = base_key,
                expiration = self.cache_expiration,
                serializer = self.serialization,
                serializer_kwargs = serializer_kwargs,
            )
        return self._cache


    

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
        data: 'BaseSchema',
        cachable: Optional[bool] = True,
        **kwargs,
    ) -> 'ResultSchema':
        """
        Runs the client
        """
        raise NotImplementedError("run must be implemented by the Client")
    
    async def arun(
        self,
        data: 'BaseSchema',
        cachable: Optional[bool] = True,
        **kwargs,
    ) -> 'ResultSchema':
        """
        Runs the client
        """
        raise NotImplementedError("arun must be implemented by the Client")
    
        
    def __call__(
        self,
        data: 'BaseSchema',
        cachable: Optional[bool] = True,
        is_async: Optional[bool] = True,
        **kwargs,
    ) -> 'ResultSchema':
        """
        Runs the client
        """
        method = self.arun if is_async else self.run
        return method(data, cachable = cachable, **kwargs)
    
    def cachify_validator_is_not_cachable(self, *args, cachable: Optional[bool] = True, **kwargs) -> bool:
        """
        Checks if the function is not cachable
        """
        from kvdb.io.cachify.helpers import is_not_cachable
        return is_not_cachable(*args, cachable = cachable, **kwargs)
    
    def cachify_validator_is_disabled(self, *args, disabled: Optional[bool] = None, **kwargs) -> bool:
        """
        Checks if the function is disabled
        """
        from kvdb.io.cachify.helpers import is_disabled
        return is_disabled(*args, disabled = disabled, **kwargs)
    
    def cachify_validator_is_overwrite(self, *args, overwrite: Optional[bool] = None, **kwargs) -> bool:
        """
        Checks if the function is overwrite
        """
        from kvdb.io.cachify.helpers import is_overwrite
        return is_overwrite(*args, overwrite = overwrite, **kwargs)
    
    def cachify_get_exclude_keys(self, func: str, **kwargs) -> List[str]:
        """
        Gets the exclude keys
        """
        return None
    
    def cachify_get_name_builder_kwargs(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the name builder kwargs
        """
        return {}
    
    def cachify_get_extra_serialization_kwargs(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Gets the extra serialization kwargs
        """
        return {}

    def cachify_create_base_name(self, func: str, **kwargs) -> str:
        """
        Creates the base name
        """
        return f'{self.settings.ctx.module_name}.{self.name}' if self.cachify_shared_global  else \
            f'{self.settings.ctx.module_name}.{self.settings.app_env.name}.{self.name}'

    def validate_cachify(self, func: str, **kwargs) -> Dict[str, Any]:
        """
        Validates the cachify function
        """
        if not self.cachify_enabled: return None
        from .utils import create_cachify_build_name_func
        base_name = self.cachify_create_base_name(func, **kwargs)
        if 'name' not in kwargs: kwargs['name'] = create_cachify_build_name_func(
            base_name = base_name,
            **self.cachify_get_name_builder_kwargs(func, **kwargs),
        )
        if 'ttl' not in kwargs: kwargs['ttl'] = self.cachify_ttl
        if 'serializer' not in kwargs and 'encoder' not in kwargs and 'decoder' not in kwargs:
            kwargs['serializer'] = self.serialization
            kwargs['serializer_kwargs'] = {
                'compression': self.serialization_compression,
                'compression_level': self.serialization_compression_level,
                'raise_errors': True,
                **self.cachify_get_extra_serialization_kwargs(func, **kwargs),
            }
        if 'verbosity' not in kwargs and self.settings.is_local_env: kwargs['verbosity'] = 2
        kwargs['disabled'] = self.cachify_validator_is_not_cachable
        kwargs['overwrite_if'] = self.cachify_validator_is_overwrite
        kwargs['disabled_if'] = self.cachify_validator_is_disabled
        if exclude_keys := self.cachify_get_exclude_keys(func, **kwargs):
            kwargs['exclude_keys'] = exclude_keys
        kwargs['exclude_null'] = True
        return kwargs
    
    """
    Helper Methods
    """
    
    def _import(self, name: str) -> Any:
        """
        Imports a module
        """
        from lazyops.utils.lazy import lazy_import
        return lazy_import(name)
    

    def _register_client(self, kind: Optional[str] = None, include_kind: Optional[bool] = None, **kwargs):
        """
        Registers the client
        """
        kind = kind or self.kind
        self.settings.ctx.register_client(self, kind = self.kind, include_kind = include_kind, **kwargs)

    def _get_client(
        self, 
        name: str,
        state: Optional[Literal['global', 'local']] = None,
        kind: Optional[str] = 'client',
        include_kind: Optional[bool] = None,
        **kwargs,
    ) -> 'ClientTypes':
        """
        Retrieves a client
        """
        return self.settings.ctx.get_client(name, state = state, kind = kind, include_kind = include_kind, **kwargs)

    def _get_component_client(
        self,
        name: str,
        *parts: str,
        kind: Optional[str] = None,
        include_kind: Optional[bool] = None,
    ) -> 'ClientTypes':
        """
        Gets a component client
        """
        return self.settings.ctx.get_component_client(name, *parts, kind = kind, include_kind = include_kind)
    

    def _get_component_schema(
        self,
        name: str,
        *parts: str,
        kind: Optional[str] = None,
        include_kind: Optional[bool] = None,
    ) -> Type['ComponentSchemaT']:
        """
        Gets a component schema
        """
        return self.settings.ctx.get_component_schema(name, *parts, kind = kind, include_kind = include_kind)
    
    def _register_component_client(
        self,
        *parts: str,
        kind: Optional[str] = None,
        include_kind: Optional[bool] = None,
    ):
        """
        Registers a component client
        """
        return self.settings.ctx.register_component_client(self, *parts, kind = kind, include_kind = include_kind)
    