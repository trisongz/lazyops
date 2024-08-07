from __future__ import annotations

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

from typing import Any, Dict, Optional, Union, Iterable, List, Type, Set, Callable, Mapping, MutableMapping, Tuple, TypeVar, overload, TYPE_CHECKING
from .backends import LocalStatefulBackend, RedisStatefulBackend, StatefulBackendT
from .serializers import ObjectValue
from .addons import (
    NumericValuesContainer,
    DurationMetric, 
    CountMetric, 
    MonetaryMetric, 
    NestedDurationMetric, 
    NestedMonetaryMetric, 
    NestedCountMetric,
    MetricT
)
from .debug import get_autologger

if TYPE_CHECKING:
    from lazyops.types.models import BaseSettings
    from kvdb.components.persistence import KVDBStatefulBackend

    BackendT = Union[KVDBStatefulBackend, StatefulBackendT]



autologger = get_autologger('main')


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

class ContextError(Exception):
    """
    Context Error
    """
    pass

RegisteredMetricTypes = {
    'numeric': NumericValuesContainer,
    'count': CountMetric,
    'duration': DurationMetric,
    'monetary': MonetaryMetric,
    'nested_count': NestedCountMetric,
    'nested_duration': NestedDurationMetric,
    'nested_monetary': NestedMonetaryMetric,
}

KT = TypeVar('KT')
VT = TypeVar('VT')
# https://stackoverflow.com/questions/61112684/how-to-subclass-a-dictionary-so-it-supports-generic-type-hints

class PersistentDict(collections.abc.MutableMapping, MutableMapping[KT, VT]):
    """
    Persistent Dictionary Interface
    """

    backend_type: Optional[str] = 'auto'
    base_class: Optional[Type['BackendT']] = None

    def __init__(
        self,
        name: Optional[str] = None,
        serializer: Optional[str] = None,
        serializer_kwargs: Optional[Dict[str, Any]] = None,
        base_key: Optional[str] = None,
        async_enabled: Optional[bool] = False,
        settings: Optional['BaseSettings'] = None,
        backend: Optional['BackendT'] = None,
        backend_type: Optional[str] = None,
        metric_types: Optional[Dict[str, Union[str, Type['MetricT']]]] = None,
        **kwargs,
    ):
        """
        Initializes the Persistent Dictionary
        """
        if backend_type is not None: self.backend_type = backend_type
        if backend is not None:
            self.base_class = lazy_import(backend) if isinstance(backend, str) else backend
        if self.base_class is None:
            self.base_class = self.get_backend_class(**kwargs)
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
        # self._mutation_tracker: Dict[str, ObjectValue] = {}
        self._mutation_tracker: Dict[KT, VT] = {}
        self._mutation_hashes: Dict[str, str] = {}

        # V2 Mutation Tracking with Context Manager
        self._in_context: bool = False
        # self._temporal_dict: Dict[str, ObjectValue] = {}
        self._temporal_dict: Dict[KT, VT] = {}
        self._metric_types: Dict[str, Type['MetricT']] = metric_types or {}
        if self._metric_types:
            for k, v in self._metric_types.items():
                if isinstance(v, str): v = lazy_import(v)
                self._metric_types[k] = v
        
        # self._metrics_dict: Dict[str, 'MetricT'] = {}
        atexit.register(self.flush)
    
    @classmethod
    def register_backend(cls, name: str, backend: Union[str, Type['BackendT']]):
        """
        Registers a Backend
        """
        global RegisteredBackends
        RegisteredBackends[name] = backend

    def get_backend_class(self, **kwargs) -> Type['BackendT']:
        # sourcery skip: assign-if-exp, hoist-similar-statement-from-if, reintroduce-else, swap-nested-ifs
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
            with contextlib.suppress(Exception):
                import kvdb
                if kvdb.is_available(url = kwargs.get('url')):
                    from kvdb.components.persistence import KVDBStatefulBackend
                    return KVDBStatefulBackend
            
            if get_keydb_enabled():
                return RedisStatefulBackend
            logger.warning('Defaulting to Local Stateful Backend')
            return LocalStatefulBackend
        raise NotImplementedError(f'Backend Type {self.backend_type} is not implemented')
    
    def get_metric_class(self, kind: str, **kwargs) -> Type['MetricT']:
        """
        Metric Class
        """
        return self._metric_types.get(kind, RegisteredMetricTypes[kind])

    
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

    def get_child(self, key: KT, **kwargs) -> 'PersistentDict':
        """
        Gets a Child Persistent Dictionary
        """
        base_key = f'{self.base_key}:{key}' if self.base_key else key
        base_kwargs = self.get_child_kwargs(**kwargs)
        return self.__class__(base_key = base_key, parent_base_key = self.base_key, child_base_key = key, **base_kwargs)


    def get(self, key: KT, default: Optional[VT] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[VT]:
        """
        Gets a Value from the DB
        """
        self._save_mutation_objects(key)
        return self.base.get(key, default = default, _raw = _raw, **kwargs)
    
    def get_values(self, keys: Iterable[str], **kwargs) -> List[VT]:
        """
        Gets a Value from the DB
        """
        self._save_mutation_objects(*keys)
        return self.base.get_values(keys, **kwargs)
    
    def fetch(self, key: KT, _raw: Optional[bool] = None, **kwargs) -> Optional[VT]:
        """
        Gets a Value from the DB
        """
        return self.get(key, _raw = _raw, **kwargs) if self.contains(key) else None
    
    def set(self, key: KT, value: Any, ex: Optional[Union[float, int]] = None, _raw: Optional[bool] = None, **kwargs) -> None:
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

    def delete(self, key: KT, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        if self.base.async_enabled and is_in_async_loop():
            ThreadPooler.create_background_task(self.base.adelete(key, **kwargs))
        else:
            self.base.delete(key, **kwargs)

    def contains(self, key: KT, **kwargs) -> bool:
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
    
    async def aget(self, key: KT, default: Optional[VT] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[VT]:
        """
        Gets a Value from the DB
        """
        await self._asave_mutation_objects(key)
        return await self.base.aget(key, default = default, _raw = _raw, **kwargs)
    
    async def aget_values(self, keys: Iterable[KT], **kwargs) -> List[VT]:
        """
        Gets a Value from the DB
        """
        await self._asave_mutation_objects(*keys)
        return await self.base.aget_values(keys,  **kwargs)
    
    async def afetch(self, key: KT, _raw: Optional[bool] = None, **kwargs) -> Optional[VT]:
        """
        Gets a Value from the DB
        """
        return await self.aget(key, _raw = _raw, **kwargs) if await self.acontains(key) else None

    async def aset(self, key: KT, value: VT, ex: Optional[Union[float, int]] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        await self.base.aset(key, value, ex = ex, _raw = _raw, **kwargs)

    async def aset_batch(self, data: Dict[KT, VT], **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        await self.base.aset_batch(data, **kwargs)

    async def adelete(self, key: KT, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        await self.base.adelete(key, **kwargs)
    
    async def acontains(self, key: KT, **kwargs) -> bool:
        """
        Returns True if the Cache contains the Key
        """
        return await self.base.acontains(key, **kwargs)
    
    async def aclear(self, *keys, **kwargs) -> None:
        """
        Clears the Cache
        """
        await self.base.aclear(*keys, **kwargs)
    
    def get_all_data(self, **kwargs) -> Dict[KT, VT]:
        """
        Loads all the Data
        """
        self._save_mutation_objects()
        return self.base.get_all_data(**kwargs)
    
    def get_all_keys(self, **kwargs) -> Iterable[KT]:
        """
        Returns all the Keys
        """
        return self.base.get_all_keys(**kwargs)
    
    def get_keys(self, pattern: str, exclude_base_key: Optional[bool] = None, **kwargs) -> List[KT]:
        """
        Returns all the Keys
        """
        return self.base.get_keys(pattern, exclude_base_key = exclude_base_key, **kwargs)
    
    def get_all_values(self, **kwargs) -> Iterable[VT]:
        """
        Returns all the Values
        """
        self._save_mutation_objects()
        return self.base.get_all_values(**kwargs)
    
    async def aget_all_data(self, **kwargs) -> Dict[KT, VT]:
        """
        Loads all the Data
        """
        await self._asave_mutation_objects()
        return await self.base.aget_all_data(**kwargs)
    
    async def aget_all_keys(self, **kwargs) -> Iterable[KT]:
        """
        Returns all the Keys
        """
        return await self.base.aget_all_keys(**kwargs)

    async def aget_keys(self, pattern: str, exclude_base_key: Optional[bool] = None, **kwargs) -> List[KT]:
        """
        Returns all the Keys
        """
        return await self.base.aget_keys(pattern, exclude_base_key = exclude_base_key, **kwargs)
    
    async def aget_all_values(self, **kwargs) -> Iterable[VT]:
        """
        Returns all the Values
        """
        await self._asave_mutation_objects()
        return await self.base.aget_all_values(**kwargs)
    
    def keys(self, **kwargs) -> Iterable[KT]:
        """
        Returns the Keys
        """
        return self.base.keys(**kwargs)
    
    def values(self, **kwargs) -> Iterable[VT]:
        """
        Returns the Values
        """
        self._save_mutation_objects()
        return self.base.values(**kwargs)
    
    def items(self, iterable: Optional[bool] = True, **kwargs) -> Dict[KT, VT]:
        """
        Returns the Items
        """
        self._save_mutation_objects()
        return self.base.items(iterable = iterable, **kwargs)
    
    async def akeys(self, **kwargs) -> Iterable[KT]:
        """
        Returns the Keys
        """
        return await self.base.akeys(**kwargs)
    
    async def avalues(self, **kwargs) -> Iterable[VT]:
        """
        Returns the Values
        """
        await self._asave_mutation_objects()
        return await self.base.avalues(**kwargs)
    
    @overload
    async def aitems(self, iterable: None = None, **kwargs) -> Iterable[Tuple[KT, VT]]:
        """
        Returns the Items
        """
        ...
    
    @overload
    async def aitems(self, iterable: bool = False, **kwargs) -> Dict[KT, VT]:
        """
        Returns the Items
        """
        ...


    async def aitems(self, iterable: Optional[bool] = True, **kwargs) -> Union[Iterable[Tuple[KT, VT]], Dict[KT, VT]]:
        """
        Returns the Items
        """
        await self._asave_mutation_objects()
        return await self.base.aitems(iterable = iterable, **kwargs)
    
    def expire(self, key: KT, timeout: Optional[int] = None, expiration: Optional[int] = None, **kwargs) -> None:
        """
        Expires a Key
        """
        # Add a check to see if expiration or timeout is set
        ex = expiration if expiration is not None else timeout
        self.base.expire(key, ex, **kwargs)

    async def aexpire(self, key: KT, timeout: Optional[int] = None, expiration: Optional[int] = None, **kwargs) -> None:
        """
        Expires a Key
        """
        ex = expiration if expiration is not None else timeout
        await self.base.aexpire(key, ex, **kwargs)

    @contextlib.contextmanager
    def track_changes(self, key: KT, func: str, *args, **kwargs):
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
    async def atrack_changes(self, key: KT, func: str, *args, **kwargs):
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

    def setdefault(self, key: KT, default: Any = None, update_values: Optional[bool] = False, enforce_type: Optional[bool] = False) -> Any:
        """
        Sets a Default Value
        """
        with self.track_changes(key, 'setdefault', default, update_values = update_values, enforce_type = enforce_type) as result:
            return result
    
    async def asetdefault(self, key: KT, default: Any = None, update_values: Optional[bool] = False, enforce_type: Optional[bool] = False) -> Any:
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
    
    def pop(self, key: KT, default: Optional[VT] = None, **kwargs) -> VT:
        """
        Pops an Item from the Cache
        """
        return self.base.pop(key, default, **kwargs)
    
    async def apop(self, key: KT, default: Optional[VT] = None, **kwargs) -> VT:
        """
        Pops an Item from the Cache
        """
        return await self.base.apop(key, default, **kwargs)
    
    # def __repr__(self):
    #     """
    #     Returns the Representation of the Cache
    #     """
    #     return repr(self.base)

    def __repr__(self):
        """
        Returns the Representation of the Cache
        """
        return f'{self.base_key}: {dict(self.items())}'

    def _clear_from_mutation_tracker(self, key: KT):
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

    """
    v2 Mutation Tracking
    """
    # TODO: deal with atomicity across multiple threads/processes/workers

    def _enter_context(self, timeout: Optional[float] = None, blocking: Optional[bool] = True, **kwargs) -> bool:
        """
        Enters the context
        """
        if self.base.acquire_lock(timeout = timeout, blocking = blocking):
            self._save_mutation_objects()
            self._in_context = True
            autologger.info(f'Entering Context: {self.name}/{self.base_key}')
            return True
        return False

    def _exit_context(self):
        """
        Exits the context
        """
        autologger.info(f'Exiting Context: {self.name}/{self.base_key}')
        autologger.info(self._temporal_dict, prefix = self.base_key, colored = True)
        self.base.set_batch(self._temporal_dict)
        self._temporal_dict.clear()
        self.base.release_lock()
        self._in_context = False

    @contextlib.contextmanager
    def acquire_context(self, timeout: Optional[float] = None, blocking: Optional[bool] = True, **kwargs):
        """
        Acquires the context
        """
        if self._enter_context(timeout = timeout, blocking = blocking, **kwargs):
            try:
                yield
            finally:
                self._exit_context()
        else:
            raise ContextError('Unable to acquire context due to concurrency')

    async def _aenter_context(self, timeout: Optional[float] = None, blocking: Optional[bool] = True, **kwargs) -> bool:
        """
        Enters the context
        """
        if await self.base.acquire_alock(timeout = timeout, blocking = blocking, **kwargs):
            await self._asave_mutation_objects()
            self._in_context = True
            autologger.info(f'Entering Context: {self.name}/{self.base_key}')
            return True
        return False

    async def _aexit_context(self):
        """
        Exits the context
        """
        autologger.info(f'Exiting Context: {self.name}/{self.base_key}')
        autologger.info(self._temporal_dict, prefix = self.base_key, colored = True)
        await self.base.aset_batch(self._temporal_dict)
        self._temporal_dict.clear()
        await self.base.release_alock()
        self._in_context = False

    async def acquire_acontext(self, timeout: Optional[float] = None, blocking: Optional[bool] = True, **kwargs):
        """
        Acquires the context
        """
        if await self._aenter_context(timeout = timeout, blocking = blocking, **kwargs):
            try:
                yield
            finally:
                await self._aexit_context()
        else:
            raise ContextError('Unable to acquire context due to concurrency')

    def __getitem__(self, key: KT) -> Union[VT, List[VT], Dict[KT, Union[List[VT], Dict[KT, VT]]]]:
        """
        Gets an Item from the DB
        """
        if self._in_context:
            if key not in self._temporal_dict:
                autologger.info(f'Loading {key}', prefix = f'{self.name}/{self.base_key}', colored = True)
                self._temporal_dict[key] = self.base.get(key)
            return self._temporal_dict[key]

        with self.track_changes(key, '__getitem__') as result:
            return result

    def __setitem__(self, key: KT, value: VT):
        """
        Sets an Item in the Cache
        """
        if self._in_context:
            autologger.info(f'Setting {key}: {value}', prefix = self.base_key, colored = True)
            self._temporal_dict[key] = value
            return

        autologger.info(f'__setitem__ {key} {value}')
        if key in self._mutation_tracker:
            self._clear_from_mutation_tracker(key)
        return self.base.__setitem__(key, value)
        
    def __delitem__(self, key):
        """
        Deletes an Item from the Cache
        """
        if self._in_context:
            autologger.info(f'Deleting {key}', prefix = self.base_key, colored = True)
            del self._temporal_dict[key]
            return

        autologger.info(f'__delitem__ {key}')
        if key in self._mutation_tracker:
            self._clear_from_mutation_tracker(key)
        return self.base.__delitem__(key)
        
    def __contains__(self, key: KT):
        """
        Returns True if the Cache contains the Key
        """
        if self._in_context:
            return key in self._temporal_dict
        return self.base.contains(key)
    
    def __iter__(self):
        """
        Iterates over the Cache
        """
        if self._in_context:
            return iter(self._temporal_dict)
        return iter(self.base.keys())
    
    def __len__(self):
        """
        Returns the Length of the Cache
        """
        return len(self._temporal_dict) if self._in_context else len(self.base)
    
    def __bool__(self):
        """
        Returns True if the Cache is not Empty
        """
        return bool(self.base.keys())

    def __enter__(self):
        """
        Enters the context
        """
        if self._enter_context():
            return self
        raise ContextError('Unable to acquire context due to concurrency')
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the context
        """
        self._exit_context()

    async def __aenter__(self):
        """
        Enters the context
        """
        if await self._aenter_context():
            return self
        raise ContextError('Unable to acquire context due to concurrency')
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the context
        """
        await self._aexit_context()
    
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

    def incr(self, key: KT, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Increments the value of the key by the given amount
        """
        return self.base.incr(key, amount = amount, **kwargs)
    
    async def aincr(self, key: KT, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Increments the value of the key by the given amount
        """
        return await self.base.aincr(key, amount = amount, **kwargs)
    
    def decr(self, key: KT, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Decrements the value of the key by the given amount
        """
        return self.base.decr(key, amount = amount, **kwargs)
    
    async def adecr(self, key: KT, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Decrements the value of the key by the given amount
        """
        return await self.base.adecr(key, amount = amount, **kwargs)
    

    """
    Set Operations
    """

    def sadd(self, key: KT, *values: Any, **kwargs) -> int:
        """
        Adds the value to the set
        """
        return self.base.sadd(key, *values, **kwargs)
    
    async def asadd(self, key: KT, *value: Any, **kwargs) -> int:
        """
        Adds the value to the set
        """
        return await self.base.asadd(key, *value, **kwargs)
    
    def slength(self, key: KT, **kwargs) -> int:
        """
        Returns the length of the set
        """
        return self.base.slength(key, **kwargs)
    
    async def aslength(self, key: KT, **kwargs) -> int:
        """
        Returns the length of the set
        """
        return await self.base.aslength(key, **kwargs)
    
    
    def sismember(self, key: KT, value: Any, **kwargs) -> bool:
        """
        Returns whether the value is a member of the set
        """
        return self.base.sismember(key, value, **kwargs)
    
    async def asismember(self, key: KT, value: Any, **kwargs) -> bool:
        """
        Returns whether the value is a member of the set
        """
        return await self.base.asismember(key, value, **kwargs)
    
    def smembers(self, key: KT, **kwargs) -> List[Any]:
        """
        Returns the members of the set
        """
        return self.base.smembers(key, **kwargs)

    async def asembers(self, key: KT, **kwargs) -> List[Any]:
        """
        Returns the members of the set
        """
        return await self.base.asembers(key, **kwargs)
    
    def smismember(self, key: KT, *values: Any, **kwargs) -> bool:
        """
        Returns whether the values are members of the set
        """
        return self.base.smismember(key, *values, **kwargs)

    async def asmismember(self, key: KT, *values: Any, **kwargs) -> bool:
        """
        Returns whether the values are members of the set
        """
        return await self.base.asmismember(key, *values, **kwargs)

    def srem(self, key: KT, *values: Any, **kwargs) -> int:
        """
        Removes the value from the set
        """
        return self.base.srem(key, *values, **kwargs)
    
    async def asrem(self, key: KT, *values: Any, **kwargs) -> int:
        """
        Removes the value from the set
        """
        return await self.base.asrem(key, *values, **kwargs)
    
    def spop(self, key: KT, **kwargs) -> Any:
        """
        Removes and returns a random member of the set
        """
        return self.base.spop(key, **kwargs)
    
    async def aspop(self, key: KT, **kwargs) -> Any:
        """
        Removes and returns a random member of the set
        """
        return await self.base.aspop(key, **kwargs) 
    
    """
    Copy Methods
    """

    def copy(
        self,
        exclude: Optional[Set[str]] = None,
        exclude_none: Optional[bool] = False,
        **kwargs
    ) -> Dict[KT, VT]:
        """
        Copies the current data and returns a Dict
        """
        data = self.items()
        if exclude is not None: data = {k: v for k, v in data.items() if k not in exclude}
        if exclude_none: data = {k: v for k, v in data.items() if v is not None}
        return data
    
    async def acopy(
        self,
        exclude: Optional[Set[str]] = None,
        exclude_none: Optional[bool] = False,
        **kwargs
    ) -> Dict[KT, VT]:
        """
        Copies the current data and returns a Dict
        """
        data = await self.aitems()
        if exclude is not None: data = {k: v for k, v in data.items() if k not in exclude}
        if exclude_none: data = {k: v for k, v in data.items() if v is not None}
        return data

    
    """
    Schema Modification Methods
    """

    def migrate_schema(self, schema_map: Dict[str, Any], overwrite: Optional[bool] = None, **kwargs) -> None:
        """
        Migrates the schema
        """
        self.base.migrate_schema(schema_map, overwrite = overwrite, **kwargs)


    async def amigrate_schema(self, schema_map: Dict[str, Any], overwrite: Optional[bool] = None, **kwargs) -> None:
        """
        Migrates the schema
        """
        await self.base.amigrate_schema(schema_map, overwrite = overwrite, **kwargs)


    def clone(
        self, 
        target: Optional[Any], 
        target_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = None, 
        **kwargs
    ):
        """
        Clones the data from the current PersistentDict to a new PersistentDict
        """
        return self.base.clone(target = target, target_base_key = target_base_key, schema_map = schema_map, overwrite = overwrite, **kwargs)

    @overload
    async def aclone(
        self,
        target: str, 
        target_base_key: Optional[str] = None,
        target_db_id: Optional[int] = None,
        source_url: Optional[str] = None,
        source_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = None, 
        excluded: Optional[Union[str, List[str]]] = None,
        filter_function: Optional[Callable[[str], bool]] = None,
        raise_errors: Optional[bool] = True,
        verbose: Optional[bool] = True,
        **kwargs
    ) -> Dict[str, Union[List[str], int, float]]:
        """
        Clones the data from the current PersistentDict to a new PersistentDict
        """
        ...

    async def aclone(
        self,
        target: Optional[Any], 
        target_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = None, 
        **kwargs
    ):
        """
        Clones the data from the current PersistentDict to a new PersistentDict
        """
        return await self.base.aclone(target = target, target_base_key = target_base_key, schema_map = schema_map, overwrite = overwrite, **kwargs)
    
    def clone_from(
        self,
        target: Any, 
        target_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = None, 
        **kwargs
    ):
        """
        Clones the data from the target PersistentDict to a current PersistentDict
        """
        return self.base.clone_from(target = target, target_base_key = target_base_key, schema_map = schema_map, overwrite = overwrite, **kwargs)

    @overload
    async def aclone_from(
        self,
        target: str, 
        target_base_key: Optional[str] = None,
        target_db_id: Optional[int] = None,
        source_url: Optional[str] = None,
        source_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = None, 
        excluded: Optional[Union[str, List[str]]] = None,
        filter_function: Optional[Callable[[str], bool]] = None,
        raise_errors: Optional[bool] = True,
        verbose: Optional[bool] = True,
        **kwargs
    ) -> Dict[str, Union[List[str], int, float]]:
        """
        Clones the data from the target PersistentDict to a current PersistentDict
        """
        ...

    async def aclone_from(
        self,
        target: Any, 
        target_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = None, 
        **kwargs
    ):
        """
        Clones the data from the target PersistentDict to a current PersistentDict
        """
        return await self.base.aclone_from(target = target, target_base_key = target_base_key, schema_map = schema_map, overwrite = overwrite, **kwargs)

    
    """
    Metrics
    """

    def configure_metric(
        self,
        name: str,
        kind: str,
        reset: Optional[bool] = None,
        metric_class: Optional[Union[Type['MetricT'], str]] = None,
        verbose: Optional[bool] = False,
        **kwargs,
    ):
        """
        Configures a Metric
        """
        if 'metrics' not in self: self['metrics'] = {}
        if reset or name not in self['metrics']:
            if metric_class: metric_class = lazy_import(metric_class) if isinstance(metric_class, str) else metric_class
            else: metric_class = self.get_metric_class(kind, **kwargs)
            self['metrics'][name] = metric_class(name = name, **kwargs)
        elif verbose:
            autologger.info(f'Metric {kind} {name} already configured', prefix = self.name, colored = True)

    
    @property
    def metrics(self) -> Dict[str, 'MetricT']:
        """
        Returns the Metrics
        """
        return self.__getitem__('metrics')
    

    