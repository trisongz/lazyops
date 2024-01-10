"""
Persistence Types

- Handles persistence of data with Redis or JSON+Pickle
"""

import contextlib
import collections.abc
from lazyops.utils.lazy import lazy_import, get_keydb_enabled
from lazyops.utils.logs import logger, null_logger
from lazyops.utils.pooler import ThreadPoolV2 as ThreadPooler

from typing import Any, Dict, Optional, Union, Iterable, List, Type, TYPE_CHECKING
from .backends import LocalStatefulBackend, RedisStatefulBackend, StatefulBackendT
from .serializers import ObjectValue

if TYPE_CHECKING:
    from lazyops.types.models import BaseSettings

_DEBUG_ENABLED = False
autologger = logger if _DEBUG_ENABLED else null_logger

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
        self._kwargs = kwargs
        self._kwargs['serializer'] = serializer
        self._kwargs['serializer_kwargs'] = serializer_kwargs
        self.base = self.base_class(
            base_key = self.base_key,
            async_enabled = async_enabled,
            settings = self.settings,
            **self._kwargs,
        )
        self._mutation_tracker: Dict[str, ObjectValue] = {}
        self._mutation_hashes: Dict[str, str] = {}
    
    def get_backend_class(self, **kwargs) -> Type[StatefulBackendT]:
        """
        Returns the Backend Class
        """
        if self.backend_type == 'local':
            return LocalStatefulBackend
        elif self.backend_type == 'redis':
            return RedisStatefulBackend
        elif self.backend_type == 'auto':
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

    def get_child(self, key: str, **kwargs) -> 'PersistentDict':
        """
        Gets a Child Persistent Dictionary
        """
        base_key = f'{self.base_key}.{key}' if self.base_key else key
        if 'async_enabled' not in kwargs:
            kwargs['async_enabled'] = self.base.async_enabled
        base_kwargs = self._kwargs.copy()
        base_kwargs.update(kwargs)
        return self.__class__(base_key = base_key, **base_kwargs)


    def get(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        self._save_mutation_objects(key)
        return self.base.get(key, default = default, **kwargs)
    
    def get_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
        self._save_mutation_objects(*keys)
        return self.base.get_values(keys)
    
    def fetch(self, key: str) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        return self.get(key) if self.contains(key) else None
    
    def set(self, key: str, value: Any, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        if self.base.async_enabled:
            ThreadPooler.create_background_task(self.base.aset(key, value, **kwargs))
        else:
            self.base.set(key, value, **kwargs)
    
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
        if self.base.async_enabled:
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
        if self.base.async_enabled:
            ThreadPooler.create_background_task(self.base.clear(*keys, **kwargs))
        else:
            self.base.clear(*keys, **kwargs)
    
    async def aget(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        await self._asave_mutation_objects(key)
        return await self.base.aget(key, default = default, **kwargs)
    
    async def aget_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
        await self._asave_mutation_objects(*keys)
        return await self.base.aget_values(keys)
    
    async def afetch(self, key: str) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        return await self.aget(key) if await self.acontains(key) else None

    async def aset(self, key: str, value: Any, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        await self.base.aset(key, value, **kwargs)

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
    
    def get_all_data(self) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        self._save_mutation_objects()
        return self.base.get_all_data()
    
    def get_all_keys(self) -> Iterable[str]:
        """
        Returns all the Keys
        """
        return self.base.get_all_keys()
    
    def get_all_values(self) -> Iterable[Any]:
        """
        Returns all the Values
        """
        self._save_mutation_objects()
        return self.base.get_all_values()
    
    async def aget_all_data(self) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        await self._asave_mutation_objects()
        return await self.base.aget_all_data()
    
    async def aget_all_keys(self) -> Iterable[str]:
        """
        Returns all the Keys
        """
        return await self.base.aget_all_keys()
    
    async def aget_all_values(self) -> Iterable[Any]:
        """
        Returns all the Values
        """
        await self._asave_mutation_objects()
        return await self.base.aget_all_values()
    
    def keys(self) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return self.base.keys()
    
    def values(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        self._save_mutation_objects()
        return self.base.values()
    
    def items(self, iterable: Optional[bool] = True) -> Dict[Any, Any]:
        """
        Returns the Items
        """
        self._save_mutation_objects()
        return self.base.items(iterable = iterable)
    
    async def akeys(self) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return await self.base.akeys()
    
    async def avalues(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        await self._asave_mutation_objects()
        return await self.base.avalues()
    
    async def aitems(self, iterable: Optional[bool] = True) -> Dict[Any, Any]:
        """
        Returns the Items
        """
        await self._asave_mutation_objects()
        return await self.base.aitems(iterable = iterable)
    
    def expire(self, key: str, timeout: int) -> None:
        """
        Expires a Key
        """
        self.base.expire(key, timeout)

    async def aexpire(self, key: str, timeout: int) -> None:
        """
        Expires a Key
        """
        await self.base.aexpire(key, timeout)

    @contextlib.contextmanager
    def track_changes(self, key: str, func: str, *args, **kwargs):
        """
        Tracks Changes
        """
        try:
            value = None
            if key in self._mutation_tracker:
                autologger.info(f'tracked {func} {key} (cached) {self._mutation_tracker[key]}')
                if self.base.serializer.create_hash(self._mutation_tracker[key]) == self._mutation_hashes[key]:
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
                self._mutation_hashes[key] = self.base.serializer.create_hash(value)
                self._mutation_tracker[key] = value
            if self.base.serializer.create_hash(value) != self._mutation_hashes[key]:
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
                if self.base.serializer.create_hash(self._mutation_tracker[key]) == self._mutation_hashes[key]:
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
                self._mutation_hashes[key] = self.base.serializer.create_hash(value)
                self._mutation_tracker[key] = value
            if self.base.serializer.create_hash(value) != self._mutation_hashes[key]:
                autologger.info(f'tracked {func} {key} (post-changed). Saving')
                await self._asave_mutation_objects(key)

    def setdefault(self, key: str, default: Any = None, update_values: Optional[bool] = False) -> Any:
        """
        Sets a Default Value
        """
        with self.track_changes(key, 'setdefault', default, update_values = update_values) as result:
            return result
    
    async def asetdefault(self, key: str, default: Any = None, update_values: Optional[bool] = False) -> Any:
        """
        Sets a Default Value
        """
        async with self.atrack_changes(key, 'asetdefault', default, update_values = update_values) as result:
            return result
        
    
    def update(self, data: Dict[str, Any]) -> None:
        """
        Updates the Cache
        """
        self._save_mutation_objects()
        self.base.update(data)

    async def aupdate(self, data: Dict[str, Any]) -> None:
        """
        Updates the Cache
        """
        await self._asave_mutation_objects()
        await self.base.aupdate(data)

    def popitem(self) -> Any:
        """
        Pops an Item from the Cache
        """
        return self.base.popitem()
    
    async def apopitem(self) -> Any:
        """
        Pops an Item from the Cache
        """
        return await self.base.apopitem()
    
    def pop(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Pops an Item from the Cache
        """
        return self.base.pop(key, default)
    
    async def apop(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Pops an Item from the Cache
        """
        return await self.base.apop(key, default)
    
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

    def __getitem__(self, key: str) -> ObjectValue:
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