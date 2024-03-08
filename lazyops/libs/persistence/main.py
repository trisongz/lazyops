"""
Persistence Types

- Handles persistence of data with Redis or JSON+Pickle
"""
import gc
import atexit
import asyncio
import contextlib
import collections.abc
from lazyops.utils.lazy import lazy_import, get_keydb_enabled
from lazyops.utils.logs import logger, null_logger
# from lazyops.utils.pooler import ThreadPoolV2 as ThreadPooler
from lazyops.utils.pooler import ThreadPooler

from typing import Any, Dict, Optional, Union, Iterable, List, Type, TYPE_CHECKING
from .backends import LocalStatefulBackend, RedisStatefulBackend, StatefulBackendT
from .serializers import ObjectValue

if TYPE_CHECKING:
    from lazyops.types.models import BaseSettings

_DEBUG_ENABLED = False
autologger = logger if _DEBUG_ENABLED else null_logger


RegisteredBackends = {
    'local': LocalStatefulBackend,
    'redis': RedisStatefulBackend,
}

def is_in_async_loop() -> bool:
    """
    Returns True if the function is called in an async loop
    """
    with contextlib.suppress(Exception):
        return asyncio.get_event_loop().is_running()
    return False

class PersistentDict(collections.abc.MutableMapping):
    """
    Persistent Dictionary Interface
    """

    backend_type: Optional[str] = 'auto'
    base_class: Optional[Type[StatefulBackendT]] = None

    def __init__(
        self,
        name: Optional[str] = None,
        serializer: Optional[str] = None,
        serializer_kwargs: Optional[Dict[str, Any]] = None,
        base_key: Optional[str] = None,
        async_enabled: Optional[bool] = False,
        settings: Optional['BaseSettings'] = None,
        backend: Optional[StatefulBackendT] = None,
        backend_type: Optional[str] = None,
        **kwargs,
    ):
        """
        Initializes the Persistent Dictionary
        """
        if backend_type is not None: self.backend_type = backend_type
        if backend is not None:
            self.base_class = lazy_import(backend) if isinstance(backend, str) else backend
        if self.base_class is None:
            self.base_class = self.get_backend_class()
        self.name = name
        self.base_key = base_key
        self.settings = settings

        # Allow for handling of parent/child keys
        # Maybe do something for deeply nested keys
        self.parent_base_key = kwargs.pop('parent_base_key', None)
        self.child_base_key = kwargs.pop('child_base_key', None)
        self.is_child_cache = self.child_base_key is not None

        self._kwargs = kwargs
        self._kwargs['serializer'] = serializer
        self._kwargs['serializer_kwargs'] = serializer_kwargs
        self.base = self.base_class(
            name = self.name,
            base_key = self.base_key,
            async_enabled = async_enabled,
            settings = self.settings,
            **self._kwargs,
        )
        self._mutation_tracker: Dict[str, ObjectValue] = {}
        self._mutation_hashes: Dict[str, str] = {}
        # logger.info(f'Initialized PersistentDict {self.name}/{self.base_key}/{self.base_class}')
        atexit.register(self.flush)
    
    @classmethod
    def register_backend(cls, name: str, backend: Union[str, Type[StatefulBackendT]]):
        """
        Registers a Backend
        """
        global RegisteredBackends
        RegisteredBackends[name] = backend

    def get_backend_class(self, **kwargs) -> Type[StatefulBackendT]:
        """
        Returns the Backend Class
        """
        if self.backend_type in RegisteredBackends:
            bt = RegisteredBackends[self.backend_type]
            return lazy_import(bt) if isinstance(bt, str) else bt
        # if self.backend_type == 'local':
        #     return LocalStatefulBackend
        # elif self.backend_type == 'redis':
        #     return RedisStatefulBackend
        if self.backend_type == 'auto':
            if get_keydb_enabled():
                return RedisStatefulBackend
            return LocalStatefulBackend
        raise NotImplementedError(f'Backend Type {self.backend_type} is not implemented')
    
    @property
    def compression_level(self) -> Optional[int]:
        """
        Returns the Compression Level
        """
        return self.base.serializer.compression_level
    
    @property
    def cache_save_key(self) -> str:
        """
        Returns the cache save key that can be used to save the cache file for globbing
        """
        if not self.is_child_cache: return self.base_key
        return f'p:{self.parent_base_key}:c:{self.child_base_key}'
        
    
    def get_child_kwargs(self, **kwargs) -> Dict[str, Any]:
        """
        Returns the Child Kwargs
        """
        base_kwargs = self._kwargs.copy()
        if kwargs: base_kwargs.update(kwargs)
        if 'settings' not in base_kwargs:
            base_kwargs['settings'] = self.settings
        if 'name' not in base_kwargs:
            base_kwargs['name'] = self.name
        if 'backend_type' not in base_kwargs and 'backend' not in base_kwargs:
            base_kwargs['backend'] = self.base_class
        if 'async_enabled' not in base_kwargs:
            base_kwargs['async_enabled'] = self.base.async_enabled
        return base_kwargs

    def get_child(self, key: str, **kwargs) -> 'PersistentDict':
        """
        Gets a Child Persistent Dictionary
        """
        base_key = f'{self.base_key}:{key}' if self.base_key else key
        base_kwargs = self.get_child_kwargs(**kwargs)
        return self.__class__(base_key = base_key, parent_base_key = self.base_key, child_base_key = key, **base_kwargs)


    def get(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        self._save_mutation_objects(key)
        return self.base.get(key, default = default, _raw = _raw, **kwargs)
    
    def get_values(self, keys: Iterable[str], **kwargs) -> List[Any]:
        """
        Gets a Value from the DB
        """
        self._save_mutation_objects(*keys)
        return self.base.get_values(keys, **kwargs)
    
    def fetch(self, key: str, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        return self.get(key, _raw = _raw, **kwargs) if self.contains(key) else None
    
    def set(self, key: str, value: Any, ex: Optional[Union[float, int]] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        if self.base.async_enabled and is_in_async_loop():
            ThreadPooler.create_background_task(self.base.aset(key, value, ex = ex, _raw = _raw, **kwargs))
        else:
            self.base.set(key, value, ex = ex, _raw = _raw, **kwargs)
    
    def set_batch(self, data: Dict[str, Any], **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        if self.base.async_enabled:
            ThreadPooler.create_background_task(self.base.aset_batch(data, **kwargs))
        else:
            self.base.set_batch(data, **kwargs)

    def delete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        if self.base.async_enabled and is_in_async_loop():
            ThreadPooler.create_background_task(self.base.adelete(key, **kwargs))
        else:
            self.base.delete(key, **kwargs)

    def contains(self, key: str, **kwargs) -> bool:
        """
        Returns True if the Cache contains the Key
        """
        return self.base.contains(key, **kwargs)
    
    def clear(self, *keys, **kwargs) -> None:
        """
        Clears the Cache
        """
        if self.base.async_enabled and is_in_async_loop():
            ThreadPooler.create_background_task(self.base.clear(*keys, **kwargs))
        else:
            self.base.clear(*keys, **kwargs)
    
    async def aget(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        await self._asave_mutation_objects(key)
        return await self.base.aget(key, default = default, _raw = _raw, **kwargs)
    
    async def aget_values(self, keys: Iterable[str], **kwargs) -> List[Any]:
        """
        Gets a Value from the DB
        """
        await self._asave_mutation_objects(*keys)
        return await self.base.aget_values(keys,  **kwargs)
    
    async def afetch(self, key: str, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        return await self.aget(key, _raw = _raw, **kwargs) if await self.acontains(key) else None

    async def aset(self, key: str, value: Any, ex: Optional[Union[float, int]] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        await self.base.aset(key, value, ex = ex, _raw = _raw, **kwargs)

    async def aset_batch(self, data: Dict[str, Any], **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        await self.base.aset_batch(data, **kwargs)

    async def adelete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        await self.base.adelete(key, **kwargs)
    
    async def acontains(self, key: str, **kwargs) -> bool:
        """
        Returns True if the Cache contains the Key
        """
        return await self.base.acontains(key, **kwargs)
    
    async def aclear(self, *keys, **kwargs) -> None:
        """
        Clears the Cache
        """
        await self.base.aclear(*keys, **kwargs)
    
    def get_all_data(self, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        self._save_mutation_objects()
        return self.base.get_all_data(**kwargs)
    
    def get_all_keys(self, **kwargs) -> Iterable[str]:
        """
        Returns all the Keys
        """
        return self.base.get_all_keys(**kwargs)
    
    def get_keys(self, pattern: str, exclude_base_key: Optional[bool] = None, **kwargs) -> List[str]:
        """
        Returns all the Keys
        """
        return self.base.get_keys(pattern, exclude_base_key = exclude_base_key, **kwargs)
    
    def get_all_values(self, **kwargs) -> Iterable[Any]:
        """
        Returns all the Values
        """
        self._save_mutation_objects()
        return self.base.get_all_values(**kwargs)
    
    async def aget_all_data(self, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        await self._asave_mutation_objects()
        return await self.base.aget_all_data(**kwargs)
    
    async def aget_all_keys(self, **kwargs) -> Iterable[str]:
        """
        Returns all the Keys
        """
        return await self.base.aget_all_keys(**kwargs)

    async def aget_keys(self, pattern: str, exclude_base_key: Optional[bool] = None, **kwargs) -> List[str]:
        """
        Returns all the Keys
        """
        return await self.base.aget_keys(pattern, exclude_base_key = exclude_base_key, **kwargs)
    
    async def aget_all_values(self, **kwargs) -> Iterable[Any]:
        """
        Returns all the Values
        """
        await self._asave_mutation_objects()
        return await self.base.aget_all_values(**kwargs)
    
    def keys(self, **kwargs) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return self.base.keys(**kwargs)
    
    def values(self, **kwargs) -> Iterable[Any]:
        """
        Returns the Values
        """
        self._save_mutation_objects()
        return self.base.values(**kwargs)
    
    def items(self, iterable: Optional[bool] = True, **kwargs) -> Dict[Any, Any]:
        """
        Returns the Items
        """
        self._save_mutation_objects()
        return self.base.items(iterable = iterable, **kwargs)
    
    async def akeys(self, **kwargs) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return await self.base.akeys(**kwargs)
    
    async def avalues(self, **kwargs) -> Iterable[Any]:
        """
        Returns the Values
        """
        await self._asave_mutation_objects()
        return await self.base.avalues(**kwargs)
    
    async def aitems(self, iterable: Optional[bool] = True, **kwargs) -> Dict[Any, Any]:
        """
        Returns the Items
        """
        await self._asave_mutation_objects()
        return await self.base.aitems(iterable = iterable, **kwargs)
    
    def expire(self, key: str, timeout: Optional[int] = None, expiration: Optional[int] = None, **kwargs) -> None:
        """
        Expires a Key
        """
        # Add a check to see if expiration or timeout is set
        ex = expiration if expiration is not None else timeout
        self.base.expire(key, ex, **kwargs)

    async def aexpire(self, key: str, timeout: Optional[int] = None, expiration: Optional[int] = None, **kwargs) -> None:
        """
        Expires a Key
        """
        ex = expiration if expiration is not None else timeout
        await self.base.aexpire(key, ex, **kwargs)

    @contextlib.contextmanager
    def track_changes(self, key: str, func: str, *args, **kwargs):
        """
        Tracks Changes
        """
        try:
            value = None
            if key in self._mutation_tracker:
                autologger.info(f'tracked {func} {key} (cached) {self._mutation_tracker[key]}')
                if self.base.create_hash(self._mutation_tracker[key]) == self._mutation_hashes[key]:
                    value = self._mutation_tracker[key]
                else:
                    autologger.info(f'tracked {func} {key} (changed). Saving')
                    self.base.set(key, self._mutation_tracker[key])
                    value = self._mutation_tracker.pop(key)
                    self._mutation_hashes.pop(key)
            
            if value is None:
                autologger.info(f'tracked {func} {key}')
                value = getattr(self.base, func)(key, *args, **kwargs)
            yield value
        finally:
            if key not in self._mutation_hashes:
                self._mutation_hashes[key] = self.base.create_hash(value)
                self._mutation_tracker[key] = value
            if self.base.create_hash(value) != self._mutation_hashes[key]:
                autologger.info(f'tracked {func} {key} (post-changed). Saving')
                self._save_mutation_objects(key)

    
    @contextlib.asynccontextmanager
    async def atrack_changes(self, key: str, func: str, *args, **kwargs):
        """
        Tracks Changes
        """
        try:
            value = None
            if key in self._mutation_tracker:
                autologger.info(f'tracked {func} {key} (cached): {self._mutation_tracker[key]}')
                if self.base.create_hash(self._mutation_tracker[key]) == self._mutation_hashes[key]:
                    value = self._mutation_tracker[key]
                else:
                    autologger.info(f'tracked {func} {key} (changed). Saving')
                    await self.base.aset(key, self._mutation_tracker[key])
                    value = self._mutation_tracker.pop(key)
                    self._mutation_hashes.pop(key)
            if value is None:
                autologger.info(f'tracked {func} {key}')
                value = await getattr(self.base, func)(key, *args, **kwargs)
            yield value
        finally:
            if key not in self._mutation_hashes:
                self._mutation_hashes[key] = self.base.create_hash(value)
                self._mutation_tracker[key] = value
            if self.base.create_hash(value) != self._mutation_hashes[key]:
                autologger.info(f'tracked {func} {key} (post-changed). Saving')
                await self._asave_mutation_objects(key)

    def setdefault(self, key: str, default: Any = None, update_values: Optional[bool] = False, enforce_type: Optional[bool] = False) -> Any:
        """
        Sets a Default Value
        """
        with self.track_changes(key, 'setdefault', default, update_values = update_values, enforce_type = enforce_type) as result:
            return result
    
    async def asetdefault(self, key: str, default: Any = None, update_values: Optional[bool] = False, enforce_type: Optional[bool] = False) -> Any:
        """
        Sets a Default Value
        """
        async with self.atrack_changes(key, 'asetdefault', default, update_values = update_values, enforce_type = enforce_type) as result:
            return result
        
    
    def update(self, data: Dict[str, Any], **kwargs) -> None:
        """
        Updates the Cache
        """
        self._save_mutation_objects()
        self.base.update(data, **kwargs)

    async def aupdate(self, data: Dict[str, Any], **kwargs) -> None:
        """
        Updates the Cache
        """
        await self._asave_mutation_objects()
        await self.base.aupdate(data, **kwargs)

    def popitem(self, **kwargs) -> Any:
        """
        Pops an Item from the Cache
        """
        return self.base.popitem(**kwargs)
    
    async def apopitem(self, **kwargs) -> Any:
        """
        Pops an Item from the Cache
        """
        return await self.base.apopitem(**kwargs)
    
    def pop(self, key: str, default: Optional[Any] = None, **kwargs) -> Any:
        """
        Pops an Item from the Cache
        """
        return self.base.pop(key, default, **kwargs)
    
    async def apop(self, key: str, default: Optional[Any] = None, **kwargs) -> Any:
        """
        Pops an Item from the Cache
        """
        return await self.base.apop(key, default, **kwargs)
    
    def __repr__(self):
        """
        Returns the Representation of the Cache
        """
        return repr(self.base)

    def _clear_from_mutation_tracker(self, key: str):
        """
        Clears the Mutation Tracker
        """
        _ = self._mutation_tracker.pop(key, None)
        _ = self._mutation_hashes.pop(key, None)

    def _save_mutation_objects(self, *keys: str):
        """
        Saves the Mutation Objects
        """
        if not self._mutation_tracker: return
        if keys:
            for key in keys:
                if key in self._mutation_tracker:
                    self.base.set(key, self._mutation_tracker[key])
                    self._clear_from_mutation_tracker(key)
        
        else:
            autologger.info(f'_save_mutation_objects: {list(self._mutation_tracker.keys())}')
            self.base.set_batch(self._mutation_tracker)
            self._mutation_tracker = {}
            self._mutation_hashes = {}
        gc.collect()

    async def _asave_mutation_objects(self, *keys: str):
        """
        Saves the Mutation Objects
        """
        if not self._mutation_tracker: return
        if keys:
            for key in keys:
                if key in self._mutation_tracker:
                    await self.base.aset(key, self._mutation_tracker[key])
                    self._clear_from_mutation_tracker(key)
        else:
            autologger.info(f'_save_mutation_objects: {list(self._mutation_tracker.keys())}')
            await self.base.aset_batch(self._mutation_tracker)
            self._mutation_tracker = {}
            self._mutation_hashes = {}
        gc.collect()

    def __getitem__(self, key: str) -> Union[ObjectValue, List, Dict[str, Union[List, Dict]]]:
        """
        Gets an Item from the DB
        """
        with self.track_changes(key, '__getitem__') as result:
            return result

    
    def __setitem__(self, key: str, value: ObjectValue):
        """
        Sets an Item in the Cache
        """
        autologger.info(f'__setitem__ {key} {value}')
        if key in self._mutation_tracker:
            self._clear_from_mutation_tracker(key)
        return self.base.__setitem__(key, value)
        
    def __delitem__(self, key):
        """
        Deletes an Item from the Cache
        """
        autologger.info(f'__delitem__ {key}')
        if key in self._mutation_tracker:
            self._clear_from_mutation_tracker(key)
        return self.base.__delitem__(key)
        
    def __iter__(self):
        """
        Iterates over the Cache
        """
        return iter(self.base.keys())
    
    def __len__(self):
        """
        Returns the Length of the Cache
        """
        return len(self.base)
    
    def __contains__(self, key: str):
        """
        Returns True if the Cache contains the Key
        """
        return self.base.contains(key)
    
    def __bool__(self):
        """
        Returns True if the Cache is not Empty
        """
        return bool(self.base.keys())
    
    def length(self, **kwargs):
        """
        Returns the Length of the Cache
        """
        return self.base.length(**kwargs)
    
    async def alength(self, **kwargs):
        """
        Returns the Length of the Cache
        """
        return await self.base.alength(**kwargs)

    def migrate_compression(self, **kwargs):
        """
        Migrates the compression
        """
        return self.base.migrate_compression(**kwargs)

    async def amigrate_compression(self, **kwargs):
        """
        Migrates the compression
        """
        return await self.base.amigrate_compression(**kwargs)
    
    def flush(self, *keys: str):
        """
        Finalize any in-memory objects
        """
        if self.base.async_enabled and is_in_async_loop():
            ThreadPooler.create_background_task(self._asave_mutation_objects(*keys))
        else:
            self._save_mutation_objects(*keys)

    async def aflush(self, *keys: str):
        """
        Finalize any in-memory objects
        """
        await self._asave_mutation_objects(*keys)
    

    def get_all_data_raw(self, exclude_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        return self.base.get_all_data_raw(exclude_base_key = exclude_base_key, **kwargs)
    
    async def aget_all_data_raw(self, exclude_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        return await self.base.aget_all_data_raw(exclude_base_key = exclude_base_key, **kwargs)
    
    
    def load_data_raw(self, data: Dict[str, Any], includes_base_key: Optional[bool] = False, **kwargs):
        """
        Loads the Data
        """
        self.base.load_data_raw(data, includes_base_key = includes_base_key, **kwargs)

    async def aload_data_raw(self, data: Dict[str, Any], includes_base_key: Optional[bool] = False, **kwargs):
        """
        Loads the Data
        """
        await self.base.aload_data_raw(data, includes_base_key = includes_base_key, **kwargs)


    def dump_data_raw(self, include_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Dumps the Data
        """
        return self.base.dump_data_raw(include_base_key = include_base_key, **kwargs)
    
    async def adump_data_raw(self, include_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Dumps the Data
        """
        return await self.base.adump_data_raw(include_base_key = include_base_key, **kwargs)
    
    def replicate_from(self, source: Any, **kwargs):
        """
        Replicates the Data
        """
        self.base.replicate_from(source, **kwargs)

    async def areplicate_from(self, source: Any, **kwargs):
        """
        Replicates the Data
        """
        await self.base.areplicate_from(source, **kwargs)

    
    """
    Math Related Methods
    """

    def incr(self, key: str, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Increments the value of the key by the given amount
        """
        return self.base.incr(key, amount = amount, **kwargs)
    
    async def aincr(self, key: str, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Increments the value of the key by the given amount
        """
        return await self.base.aincr(key, amount = amount, **kwargs)
    
    def decr(self, key: str, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Decrements the value of the key by the given amount
        """
        return self.base.decr(key, amount = amount, **kwargs)
    
    async def adecr(self, key: str, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Decrements the value of the key by the given amount
        """
        return await self.base.adecr(key, amount = amount, **kwargs)
    

    """
    Set Operations
    """

    def sadd(self, key: str, *values: Any, **kwargs) -> int:
        """
        Adds the value to the set
        """
        return self.base.sadd(key, *values, **kwargs)
    
    async def asadd(self, key: str, *value: Any, **kwargs) -> int:
        """
        Adds the value to the set
        """
        return await self.base.asadd(key, *value, **kwargs)
    
    def slength(self, key: str, **kwargs) -> int:
        """
        Returns the length of the set
        """
        return self.base.slength(key, **kwargs)
    
    async def aslength(self, key: str, **kwargs) -> int:
        """
        Returns the length of the set
        """
        return await self.base.aslength(key, **kwargs)
    
    
    def sismember(self, key: str, value: Any, **kwargs) -> bool:
        """
        Returns whether the value is a member of the set
        """
        return self.base.sismember(key, value, **kwargs)
    
    async def asismember(self, key: str, value: Any, **kwargs) -> bool:
        """
        Returns whether the value is a member of the set
        """
        return await self.base.asismember(key, value, **kwargs)
    
    def smembers(self, key: str, **kwargs) -> List[Any]:
        """
        Returns the members of the set
        """
        return self.base.smembers(key, **kwargs)

    async def asembers(self, key: str, **kwargs) -> List[Any]:
        """
        Returns the members of the set
        """
        return await self.base.asembers(key, **kwargs)
    
    def smismember(self, key: str, *values: Any, **kwargs) -> bool:
        """
        Returns whether the values are members of the set
        """
        return self.base.smismember(key, *values, **kwargs)

    async def asmismember(self, key: str, *values: Any, **kwargs) -> bool:
        """
        Returns whether the values are members of the set
        """
        return await self.base.asmismember(key, *values, **kwargs)

    def srem(self, key: str, *values: Any, **kwargs) -> int:
        """
        Removes the value from the set
        """
        return self.base.srem(key, *values, **kwargs)
    
    async def asrem(self, key: str, *values: Any, **kwargs) -> int:
        """
        Removes the value from the set
        """
        return await self.base.asrem(key, *values, **kwargs)
    
    def spop(self, key: str, **kwargs) -> Any:
        """
        Removes and returns a random member of the set
        """
        return self.base.spop(key, **kwargs)
    
    async def aspop(self, key: str, **kwargs) -> Any:
        """
        Removes and returns a random member of the set
        """
        return await self.base.aspop(key, **kwargs) 
    
