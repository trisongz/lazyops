from __future__ import annotations

"""
OpenAI Functions Manager
"""

import functools
from abc import ABC
from lzl.proxied import ProxyObject
from lzo.utils import Timer
from lzl.api.openai.schemas.functions import (
    FunctionSchemaT,
    BaseFunction,
    FunctionT,
    FunctionResultT,

)
from typing import Optional, Any, Set, Dict, List, Union, Type, Tuple, Awaitable, Generator, AsyncGenerator, TypeVar, TYPE_CHECKING
if TYPE_CHECKING:
    from lzl.api.openai.clients import OpenAIManager as OpenAISessionManager
    from lzl.logging import Logger
    from lazyops.libs.persistence import PersistentDict



class FunctionManager(ABC):
    """
    The Functions Manager Class that handles registering and managing functions

    - Additionally supports caching through `kvdb`
    """

    name: Optional[str] = 'functions'

    def __init__(
        self,
        **kwargs,
    ):
        from lzl.api.openai.configs import settings
        from lzl.api.openai.utils.logs import logger, null_logger
        self.logger = logger
        self.null_logger = null_logger
        self.settings = settings
        self.debug_enabled = self.settings.debug_enabled
        self.cache_enabled = self.settings.function_cache_enabled

        self._api: Optional['OpenAISessionManager'] = None
        self._cache: Optional['PersistentDict'] = None
        self.functions: Dict[str, 'BaseFunction'] = {}
        self._kwargs = kwargs
        from lzo.utils.hashing import create_hash_from_args_and_kwargs
        self.create_hash = create_hash_from_args_and_kwargs

        # try:
        #     import xxhash
        #     self._hash_func = xxhash.xxh64
        # except ImportError:
        #     from hashlib import md5
        #     self._hash_func = md5
        
        try:
            import cloudpickle
            self._pickle = cloudpickle
        except ImportError:
            import pickle
            self._pickle = pickle

    @property
    def api(self) -> 'OpenAISessionManager':
        """
        Returns the API
        """
        if self._api is None:
            from lzl.api.openai.clients import OpenAI
            # from async_openai.client import OpenAIManager
            self._api = OpenAI
        return self._api
    
    @property
    def autologger(self) -> 'Logger':
        """
        Returns the logger
        """
        return self.logger if \
            (self.debug_enabled or self.settings.is_development_env) else self.null_logger

    @property
    def cache(self) -> 'PersistentDict':
        """
        Gets the cache
        """
        if self._cache is None:
            serializer_kwargs = {
                'compression': self._kwargs.get('serialization_compression', None),
                'compression_level': self._kwargs.get('serialization_compression_level', None),
                'raise_errors': True,
            }
            kwargs = {
                'base_key': f'lzl.openai.functions.{self.api.settings.app_env.name}.{self.api.settings.proxy.proxy_app_name or "default"}',
                'expiration': self._kwargs.get('cache_expiration', 60 * 60 * 24 * 3),
                'serializer': self._kwargs.get('serialization', 'json'),
                'serializer_kwargs': serializer_kwargs,
            }
            try:
                import kvdb
                self._cache = kvdb.create_persistence(session_name = 'openai', **kwargs)
            except ImportError:
                from lazyops.libs.persistence import PersistentDict
                self._cache = PersistentDict(**kwargs)
        return self._cache

    def register_function(
        self,
        func: Union['BaseFunction', Type['BaseFunction'], str],
        name: Optional[str] = None,
        overwrite: Optional[bool] = False,
        raise_error: Optional[bool] = False,
        initialize: Optional[bool] = True,
        **kwargs,
    ):
        """
        Registers the function
        """
        if isinstance(func, str):
            from lzl.load import lazy_import
            # from lazyops.utils.lazy import lazy_import
            func = lazy_import(func)
        if isinstance(func, type) and initialize:
            func = func(**kwargs)
        name = name or func.name
        if not overwrite and name in self.functions:
            if raise_error: raise ValueError(f"Function {name} already exists")
            return
        self.functions[name] = func
        self.autologger.info(f"Registered Function: |g|{name}|e|", colored=True)

    async def acreate_hash(self, *args, **kwargs) -> str:
        """
        Creates a hash
        """
        return await self.api.pooler.asyncish(self.create_hash, *args, **kwargs)
    
    def _get_function(self, name: str) -> Optional['BaseFunction']:
        """
        Gets the function
        """
        func = self.functions.get(name)
        if not func: return None
        if isinstance(func, type):
            func = func(**self._kwargs)
            self.functions[name] = func
        return func

    def get(self, name: Union[str, 'FunctionT']) -> Optional['FunctionT']:
        """
        Gets the function
        """
        return name if isinstance(name, BaseFunction) else self._get_function(name)
        
    
    def parse_iterator_func(
        self,
        function: 'FunctionT',
        *args,
        with_index: Optional[bool] = False,
        **function_kwargs,
    ) -> Tuple[int, Set, Dict[str, Any]]:
        """
        Parses the iterator function kwargs
        """
        func_iter_arg = args[0]
        args = args[1:]
        idx = None
        if with_index: idx, item = func_iter_arg
        else: item = func_iter_arg
        _func_kwargs = function.get_function_kwargs()
        if isinstance(item, dict) and any(k in _func_kwargs for k in item):
            function_kwargs.update(item)
        else:
            # Get the missing function kwargs
            _added = False
            for k in _func_kwargs:
                if k not in function_kwargs:
                    function_kwargs[k] = item
                    # self.autologger.info(f"Added missing function kwarg: {k} = {item}", prefix = function.name, colored = True)
                    _added = True
                    break
            if not _added:
                # If not, then add the item as the first argument
                args = (item,) + args
        return idx, args, function_kwargs

    def execute(
        self,
        function: Union['FunctionT', str],
        *args,
        item_hashkey: Optional[str] = None,
        cachable: Optional[bool] = True,
        overrides: Optional[List[str]] = None,
        with_index: Optional[bool] = False,
        **function_kwargs
    ) -> Union[Optional['FunctionSchemaT'], Tuple[int, Optional['FunctionSchemaT']]]:
        # sourcery skip: low-code-quality
        """
        Runs the function
        """
        overwrite = function_kwargs.pop('overwrite', None)
        overwrite = overwrite or overrides and 'functions' in overrides
        function = self.get(function)
        if overwrite and overrides and self.check_value_present(overrides, f'{function.name}.cachable'):
            cachable = False
        
        # Iterators
        is_iterator = function_kwargs.pop('_is_iterator', False)
        if is_iterator:
            idx, args, function_kwargs = self.parse_iterator_func(function, *args, with_index = with_index, **function_kwargs)
        
        if item_hashkey is None: item_hashkey = self.create_hash(**function_kwargs)
        key = f'{item_hashkey}.{function.name}'
        if function.has_diff_model_than_default:
            key += f'.{function.default_model_func}'

        t = Timer(format_short = 1)
        result = None
        cache_hit = False
        if self.cache_enabled and not overwrite:
            result: 'FunctionResultT' = self.cache.fetch(key)
            if result:
                if isinstance(result, dict): result = function.schema.model_validate(result)
                result.function_name = function.name
                cache_hit = True
        
        if result is None:
            result = function(*args, cachable = cachable, is_async = False, **function_kwargs)
            if self.cache_enabled and function.is_valid_response(result):
                self.cache.set(key, result)
        
        self.autologger.info(f"Function: {function.name} in {t.total_s} (Model: {result.function_model}, Client: {result.function_client_name}, Cache Hit: {cache_hit})", prefix = key, colored = True)
        if is_iterator and with_index:
            return idx, result if function.is_valid_response(result) else (idx, None)
        return result if function.is_valid_response(result) else None

    
    async def aexecute(
        self,
        function: Union['FunctionT', str],
        *args,
        item_hashkey: Optional[str] = None,
        cachable: Optional[bool] = True,
        overrides: Optional[List[str]] = None,
        with_index: Optional[bool] = False,
        **function_kwargs
    ) -> Union[Optional['FunctionSchemaT'], Tuple[int, Optional['FunctionSchemaT']]]:
        # sourcery skip: low-code-quality
        """
        Runs the function
        """
        overwrite = function_kwargs.pop('overwrite', None)
        overwrite = overwrite or overrides and 'functions' in overrides
        function = self.get(function)
        if overwrite and overrides and self.check_value_present(overrides, f'{function.name}.cachable'):
            cachable = False
        
        # Iterators
        is_iterator = function_kwargs.pop('_is_iterator', False)
        if is_iterator:
            idx, args, function_kwargs = self.parse_iterator_func(function, *args, with_index = with_index, **function_kwargs)

        if item_hashkey is None: item_hashkey = await self.acreate_hash(*args, **function_kwargs)
        key = f'{item_hashkey}.{function.name}'
        if function.has_diff_model_than_default:
            key += f'.{function.default_model_func}'

        t = Timer(format_short = 1)
        result = None
        cache_hit = False
        if self.cache_enabled and not overwrite:
            result: 'FunctionResultT' = await self.cache.afetch(key)
            if result:
                if isinstance(result, dict): result = function.schema.model_validate(result)
                result.function_name = function.name
                cache_hit = True
        
        if result is None:
            result = await function(*args, cachable = cachable, is_async = True, **function_kwargs)
            if self.cache_enabled and function.is_valid_response(result):
                await self.cache.aset(key, result)
        
        self.autologger.info(f"Function: {function.name} in {t.total_s} (Model: {result.function_model}, Client: {result.function_client_name}, Cache Hit: {cache_hit})", prefix = key, colored = True)
        if is_iterator and with_index:
            return idx, result if function.is_valid_response(result) else (idx, None)
        return result if function.is_valid_response(result) else None

    
    
    @property
    def function_names(self) -> List[str]:
        """
        Returns the function names
        """
        return list(self.functions.keys())
    
    def __getitem__(self, name: str) -> Optional['FunctionT']:
        """
        Gets the function
        """
        return self.get(name)

    def __setitem__(self, name: str, value: Union[FunctionT, Type[FunctionT], str]):
        """
        Sets the function
        """
        return self.register_function(value, name = name)
    
    def append(self, value: Union[FunctionT, Type[FunctionT], str]):
        """
        Appends the function
        """
        return self.register_function(value)
    

    def check_value_present(
        self, items: List[str], *values: str,
    ) -> bool:
        """
        Checks if the value is present
        """
        if not values:
            return any(self.name in item for item in items)
        for value in values:
            key = f'{self.name}.{value}' if value else self.name
            if any((key in item or value in item) for item in items):
                return True
        return False
    
    def map(
        self,
        function: Union['FunctionT', str],
        iterable_kwargs: List[Union[Dict[str, Any], Any]],
        *args,
        cachable: Optional[bool] = True,
        overrides: Optional[List[str]] = None,
        return_ordered: Optional[bool] = True,
        with_index: Optional[bool] = False,
        **function_kwargs
    ) -> List[Union[Optional['FunctionSchemaT'], Tuple[int, Optional['FunctionSchemaT']]]]:
        """
        Maps the function to the iterable in parallel
        """
        partial = functools.partial(
            self.execute, 
            function, 
            # *args,
            cachable = cachable, 
            overrides = overrides, 
            _is_iterator = True,
            with_index = with_index,
            **function_kwargs
        )
        if with_index: iterable_kwargs = list(enumerate(iterable_kwargs))
        return self.api.pooler.map(partial, iterable_kwargs, *args, return_ordered = return_ordered)
    
    async def amap(
        self,
        function: Union['FunctionT', str],
        iterable_kwargs: List[Dict[str, Any]],
        *args,
        cachable: Optional[bool] = True,
        overrides: Optional[List[str]] = None,
        return_ordered: Optional[bool] = True,
        concurrency_limit: Optional[int] = None,
        with_index: Optional[bool] = False,
        **function_kwargs
    ) -> List[Union[Optional['FunctionSchemaT'], Tuple[int, Optional['FunctionSchemaT']]]]:
        """
        Maps the function to the iterable in parallel
        """
        partial = functools.partial(
            self.aexecute, 
            function, 
            # *args,
            cachable = cachable, 
            overrides = overrides, 
            _is_iterator = True,
            with_index = with_index,
            **function_kwargs
        )
        if with_index: iterable_kwargs = list(enumerate(iterable_kwargs))
        return await self.api.pooler.amap(partial, iterable_kwargs, *args, return_ordered = return_ordered, concurrency_limit = concurrency_limit)
    
    def iterate(
        self,
        function: Union['FunctionT', str],
        iterable_kwargs: List[Dict[str, Any]],
        *args,
        cachable: Optional[bool] = True,
        overrides: Optional[List[str]] = None,
        return_ordered: Optional[bool] = False,
        with_index: Optional[bool] = False,
        **function_kwargs
    ) -> Generator[Union[Optional['FunctionSchemaT'], Tuple[int, Optional['FunctionSchemaT']]], None, None]:
        """
        Maps the function to the iterable in parallel
        """
        partial = functools.partial(
            self.execute, 
            function, 
            # *args, 
            cachable = cachable, 
            overrides = overrides, 
            _is_iterator = True,
            with_index = with_index,
            **function_kwargs
        )
        if with_index: iterable_kwargs = list(enumerate(iterable_kwargs))
        return self.api.pooler.iterate(partial, iterable_kwargs, *args, return_ordered = return_ordered)

    def aiterate(
        self,
        function: Union['FunctionT', str],
        iterable_kwargs: List[Dict[str, Any]],
        *args,
        cachable: Optional[bool] = True,
        overrides: Optional[List[str]] = None,
        return_ordered: Optional[bool] = False,
        concurrency_limit: Optional[int] = None,
        with_index: Optional[bool] = False,
        **function_kwargs
    ) -> AsyncGenerator[Union[Optional['FunctionSchemaT'], Tuple[int, Optional['FunctionSchemaT']]], None]:
        """
        Maps the function to the iterable in parallel
        """
        partial = functools.partial(
            self.aexecute, 
            function, 
            # *args, 
            cachable = cachable, 
            overrides = overrides, 
            _is_iterator = True,
            with_index = with_index,
            **function_kwargs
        )
        if with_index: iterable_kwargs = list(enumerate(iterable_kwargs))
        return self.api.pooler.aiterate(partial, iterable_kwargs, *args, return_ordered = return_ordered, concurrency_limit = concurrency_limit)
    
    def __call__(
        self,
        function: Union['FunctionT', str],
        *args,
        item_hashkey: Optional[str] = None,
        cachable: Optional[bool] = True,
        overrides: Optional[List[str]] = None,
        is_async: Optional[bool] = True,
        **function_kwargs
    ) -> Union[Awaitable['FunctionSchemaT'], 'FunctionSchemaT']:
        """
        Runs the function
        """
        method = self.aexecute if is_async else self.execute
        return method(
            function = function,
            *args,
            item_hashkey = item_hashkey,
            cachable = cachable,
            overrides = overrides,
            **function_kwargs
        )
    



OpenAIFunctions: FunctionManager = ProxyObject(FunctionManager)