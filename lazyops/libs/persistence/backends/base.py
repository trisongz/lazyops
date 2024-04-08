from __future__ import annotations

"""
Base Persistence Backend
"""
import contextlib
import collections.abc
from threading import Lock
from asyncio import Lock as AsyncLock
from pathlib import Path
from pydantic import BaseModel
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Iterable, List, Type, ItemsView, TYPE_CHECKING
from lazyops.utils.helpers import  create_unique_id
from lazyops.utils.logs import logger
# from lazyops.utils.pooler import ThreadPoolV2 as ThreadPooler
from lazyops.utils.pooler import ThreadPooler
from ..serializers import get_serializer, SerializerT
from ..serializers.base import create_obj_hash

if TYPE_CHECKING:
    from lazyops.types.models import BaseSettings
    from ..serializers.base import ObjectValue

SchemaType = TypeVar("SchemaType", bound=BaseModel)


class BaseStatefulBackend(collections.abc.MutableMapping):
    """
    Base Stateful Backend
    """
    serializer: Optional[SerializerT] = None
    serializer_type: Optional[str] = None
    serializer_kwargs: Optional[Dict[str, Any]] = {}

    def __init__(
        self,
        serializer: Optional[str] = None,
        serializer_kwargs: Optional[Dict[str, Any]] = None,
        base_key: Optional[str] = None,
        async_enabled: Optional[bool] = False,
        settings: Optional['BaseSettings'] = None,
        **kwargs,
    ):
        """
        Initializes the backend
        """
        self.base_key = base_key
        self.async_enabled = async_enabled
        self.settings = settings
        if serializer is not None:
            self.serializer_type = serializer
        if serializer_kwargs is not None:
            self.serializer_kwargs = serializer_kwargs
        if self.serializer is None:
            self.serializer = get_serializer(self.serializer_type, **self.serializer_kwargs)
        self._lock: Optional[Lock] = None
        self._alock: Optional[AsyncLock] = None
        self._kwargs = kwargs


    def get_key(self, key: str) -> str:
        """
        Gets a Key
        """
        return f'{self.base_key}.{key}' if self.base_key else key

    def encode_value(self, value: Union[Any, SchemaType], _raw: Optional[bool] = None, **kwargs) -> Union[str, bytes]:
        """
        Encodes a Value
        """
        return value if _raw else self.serializer.encode(value, **kwargs)
    
    async def aencode_value(self, value: Union[Any, SchemaType], _raw: Optional[bool] = None,  **kwargs) -> Union[str, bytes]:
        """
        Encodes a Value
        """
        return value if _raw else await self.serializer.aencode(value, **kwargs)

    def decode_value(self, value: Union[str, bytes], _raw: Optional[bool] = None, **kwargs) -> Any:
        """
        Decodes a Value
        """
        return value if _raw else self.serializer.decode(value, **kwargs)
    
    async def adecode_value(self, value: Union[str, bytes], _raw: Optional[bool] = None, **kwargs) -> Any:
        """
        Decodes a Value
        """
        return value if _raw else await self.serializer.adecode(value, **kwargs)
    
    def create_hash(self, obj: 'ObjectValue') -> str:
        """
        Creates a Hash
        """
        return self.serializer.create_hash(obj) if self.serializer is not None else \
            create_obj_hash(obj)

    
    def _precheck(self, **kwargs):
        """
        Run a precheck operation
        """
        pass

    def get(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        raise NotImplementedError
            
    def get_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
        raise NotImplementedError


    def set(self, key: str, value: Any, ex: Optional[int] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        raise NotImplementedError


    def set_batch(self, data: Dict[str, Any], ex: Optional[int] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        raise NotImplementedError


    def delete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        raise NotImplementedError


    def clear(self, *keys: str, **kwargs):
        """
        Clears the Cache
        """
        raise NotImplementedError

    
    async def aget(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        return await ThreadPooler.run_async(self.get, key, default, _raw = _raw, **kwargs)

    async def aget_values(self, keys: Iterable[str], **kwargs) -> List[Any]:
        """
        Gets a Value from the DB
        """
        return await ThreadPooler.run_async(self.get_values, keys, **kwargs)

    
    async def aset(self, key: str, value: Any, ex: Optional[int] = None, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        return await ThreadPooler.run_async(self.set, key, value, ex, _raw = _raw, **kwargs)


    async def aset_batch(self, data: Dict[str, Any], ex: Optional[int] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        return await ThreadPooler.run_async(self.set_batch, data, ex, **kwargs)

    async def adelete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        return await ThreadPooler.run_async(self.delete, key, **kwargs)

    async def aclear(self, *keys: str, **kwargs):
        """
        Clears the Cache
        """
        return await ThreadPooler.run_async(self.clear, *keys, **kwargs)

    def iterate(self, **kwargs) -> Iterable[Any]:
        """
        Iterates over the Cache
        """
        raise NotImplementedError


    def get_all_data(self, exclude_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        raise NotImplementedError


    def get_all_keys(self, exclude_base_key: Optional[bool] = False, **kwargs) -> List[str]:
        """
        Returns all the Keys
        """
        raise NotImplementedError


    def get_all_values(self, **kwargs) -> List[Any]:
        """
        Returns all the Values
        """
        raise NotImplementedError


    async def aget_all_data(self, exclude_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        return await ThreadPooler.run_async(self.get_all_data, exclude_base_key = exclude_base_key, **kwargs)

    async def aget_all_keys(self, exclude_base_key: Optional[bool] = False, **kwargs) -> List[str]:
        """
        Returns all the Keys
        """
        return await ThreadPooler.run_async(self.get_all_keys, exclude_base_key = exclude_base_key, **kwargs)

    async def aget_all_values(self,  **kwargs) -> List[Any]:
        """
        Returns all the Values
        """
        return await ThreadPooler.run_async(self.get_all_values, **kwargs)


    def pop(self, key, default = None, **kwargs):
        """
        Pops an Item from the Cache
        """
        self._precheck()
        value = self.get(key, **kwargs)
        if self.async_enabled:
            ThreadPooler.create_background_task(self.adelete(key))
        else:
            self.delete(key)
        return value if value is not None else default
    
    async def apop(self, key, default = None, **kwargs):
        """
        Pops an Item from the Cache
        """
        self._precheck()
        value = await self.aget(key, **kwargs)
        await self.adelete(key)
        return value if value is not None else default

    def contains(self, key: str, **kwargs) -> bool:
        """
        Returns True if the Cache contains the Key
        """
        raise NotImplementedError

    async def acontains(self, key: str, **kwargs) -> bool:
        """
        Returns True if the Cache contains the Key
        """
        return await ThreadPooler.run_async(self.contains, key, **kwargs)

    def keys(self, **kwargs) -> Iterable[str]:
        """
        Returns the Keys
        """
        return iter(self.get_all_keys(True, **kwargs))

    def get_keys(self, pattern: str, exclude_base_key: Optional[bool] = None, **kwargs) -> List[str]:
        """
        Returns the Keys
        """
        raise NotImplementedError
    
    def values(self, **kwargs) -> Iterable[Any]:
        """
        Returns the Values
        """
        return iter(self.get_all_values(**kwargs))
    
    def items(self, iterable: Optional[bool] = True, **kwargs) -> Union[Iterable[ItemsView], Dict[str, Any]]:
        """
        Returns the Items
        """
        items = self.get_all_data(True, **kwargs)
        return items.items() if iterable else items
    
    async def akeys(self, **kwargs) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return iter(await self.aget_all_keys(True, **kwargs))
    
    async def aget_keys(self, pattern: str, exclude_base_key: Optional[bool] = None, **kwargs) -> List[str]:
        """
        Returns the Keys
        """
        raise NotImplementedError
    
    async def avalues(self, **kwargs) -> Iterable[Any]:
        """
        Returns the Values
        """
        return iter(await self.aget_all_values(**kwargs))
    
    async def aitems(self, iterable: Optional[bool] = True, **kwargs) -> Union[Iterable[ItemsView], Dict[str, Any]]:
        """
        Returns the Items
        """
        items = await self.aget_all_data(True, **kwargs)
        return items.items() if iterable else items
    
    def expire(self, key: str, ex: Optional[int] = None, **kwargs) -> None:
        """
        Expires a Key
        """
        pass
            
    async def aexpire(self, key: str, ex: Optional[int] = None, **kwargs) -> None:
        """
        Expires a Key
        """
        pass
    
    def setdefault(self, key: str, default: Any = None, update_values: Optional[bool] = False, enforce_type: Optional[bool] = False, **kwargs):
        """
        Sets a Default Value
        """
        if self.contains(key):
            with contextlib.suppress(Exception):
                value = self.get(key)
                if value is not None:
                    if enforce_type and not isinstance(value, type(default)):
                        value = type(default)(value)
                    if update_values and isinstance(value, dict) and default and isinstance(default, dict):
                        from lazyops.libs.abcs.utils.helpers import update_dict
                        value = update_dict(value, default, exclude_none = True)
                        # for k, v in default.items():
                        #     if k not in value or value[k] is None:
                        #         
                        #         value[k] = v
                        self.set(key, value)
                    return value
        self.set(key, default)
        return default
    
    async def asetdefault(self, key: str, default: Any = None, update_values: Optional[bool] = False, enforce_type: Optional[bool] = False, **kwargs):
        """
        Sets a Default Value
        """
        if await self.acontains(key):
            with contextlib.suppress(Exception):
                value = await self.aget(key)
                if value is not None:
                    if enforce_type and not isinstance(value, type(default)):
                        value = type(default)(value)
                    if update_values and isinstance(value, dict) and default and isinstance(default, dict):
                        from lazyops.libs.abcs.utils.helpers import update_dict
                        value = update_dict(value, default, exclude_none = True)
                        # for k, v in default.items():
                        #     if k not in value or value[k] is None:
                        #         value[k] = v
                        await self.aset(key, value)
                    return value
        await self.aset(key, default)
        return default
    
    def update(self, data: Dict[str, Any], **kwargs):
        """
        Updates the Cache
        """
        for key, value in data.items():
            self.set(key, value, **kwargs)
    
    async def aupdate(self, data: Dict[str, Any], **kwargs):
        """
        Updates the Cache
        """
        for key, value in data.items():
            await self.aset(key, value, **kwargs)

    def popitem(self, **kwargs):
        """
        Pops an Item from the Cache
        """
        self._precheck()
        key = next(iter(self))
        value = self.get(key, **kwargs)
        if value is not None:
            if self.async_enabled:
                ThreadPooler.create_background_task(self.adelete(key))
            else:
                self.delete(key)
            return key, value
        return None, None
    
    async def apopitem(self, **kwargs):
        """
        Pops an Item from the Cache
        """
        self._precheck()
        key = next(iter(self))
        value = await self.aget(key, **kwargs)
        if value is not None:
            await self.adelete(key)
            return key, value
        return None, None


    def __getitem__(self, key):
        """
        Gets an Item from the DB
        """
        
        return self.get(key)

    def __setitem__(self, key, value):
        """
        Sets an Item in the Cache
        """
        return ThreadPooler.create_background_task(self.aset(key, value)) if \
            self.async_enabled else self.set(key, value)
    
    def __delitem__(self, key):
        """
        Deletes an Item from the Cache
        """
        return ThreadPooler.create_background_task(self.adelete(key)) if \
            self.async_enabled else self.delete(key)

    def __iter__(self):
        """
        Iterates over the Cache
        """
        return self.iterate()
    

    def __len__(self):
        """
        Returns the Length of the Cache
        """
        self._precheck()
        return len(list(self.iterate()))
    
    def length(self, **kwargs):
        """
        Returns the Length of the Cache
        """
        self._precheck()
        return len(self.get_all_keys(**kwargs))

    async def alength(self, **kwargs):
        """
        Returns the Length of the Cache
        """
        self._precheck()
        return len(await self.aget_all_keys(**kwargs))


    def __contains__(self, key):
        """
        Returns True if the Cache contains the Key
        """
        return self.contains(key)
    
    def __eq__(self, other):
        """
        Returns True if the Cache is Equal to the Other
        """
        return self.get_all_data(True) == other
    
    def __repr__(self):
        """
        Returns the Representation of the Cache
        """
        return f"<{self.__class__.__name__} num_keys={len(self)}, base_key={self.base_key}, serializer={self.serializer.name}>"
    
    def migrate_compression(self, **kwargs):
        """
        Migrates the Compression
        """
        pass

    async def amigrate_compression(self, **kwargs):
        """
        Migrates the Compression
        """
        pass

    def get_all_data_raw(self, exclude_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        raise NotImplementedError
    
    async def aget_all_data_raw(self, exclude_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        return await ThreadPooler.run_async(self.get_all_data_raw, exclude_base_key = exclude_base_key, **kwargs)
    
    def load_data_raw(self, data: Dict[str, Any], includes_base_key: Optional[bool] = False, **kwargs):
        """
        Loads the Data
        """
        raise NotImplementedError
    
    async def aload_data_raw(self, data: Dict[str, Any], includes_base_key: Optional[bool] = False, **kwargs):
        """
        Loads the Data
        """
        return await ThreadPooler.run_async(self.load_data_raw, data, includes_base_key = includes_base_key, **kwargs)
    
    def dump_data_raw(self, include_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Dumps the Data
        """
        raise NotImplementedError
    
    async def adump_data_raw(self, include_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Dumps the Data
        """
        return await ThreadPooler.run_async(self.dump_data_raw, include_base_key = include_base_key, **kwargs)
    
    
    def replicate_from(self, source: Any, **kwargs):
        """
        Replicates the Cache from a Source
        """
        raise NotImplementedError
    
    async def areplicate_from(self, source: Any, **kwargs):
        """
        Replicates the Cache from a Source
        """
        return await ThreadPooler.run_async(self.replicate_from, source, **kwargs)

    """
    Math Related Methods
    """

    def incr(self, key: str, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        [int/float] Increments the value of the key by the given amount
        """
        if isinstance(amount, int): return self.incrby(key, amount = amount, **kwargs)
        return self.incrbyfloat(key, amount = amount, **kwargs)
    
    def incrby(self, key: str, amount: int = 1, **kwargs) -> int:
        """
        [int] Increments the value of the key by the given amount
        """
        raise NotImplementedError
    
    def incrbyfloat(self, key: str, amount: float = 1.0, **kwargs) -> float:
        """
        [float] Increments the value of the key by the given amount
        """
        raise NotImplementedError
    
    async def aincr(self, key: str, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Increments the value of the key by the given amount
        """
        if isinstance(amount, int): return await self.aincrby(key, amount = amount, **kwargs)
        return await self.aincrbyfloat(key, amount = amount, **kwargs)
    
    async def aincrby(self, key: str, amount: int = 1, **kwargs) -> int:
        """
        [int] Increments the value of the key by the given amount
        """
        raise NotImplementedError
    
    async def aincrbyfloat(self, key: str, amount: float = 1.0, **kwargs) -> float:
        """
        [float] Increments the value of the key by the given amount
        """
        raise NotImplementedError
    
    def decr(self, key: str, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        [int/float] Decrements the value of the key by the given amount
        """
        if isinstance(amount, int): return self.decrby(key, amount = amount, **kwargs)
        return self.decrbyfloat(key, amount = amount, **kwargs)
    
    def decrby(self, key: str, amount: int = 1, **kwargs) -> int:
        """
        [int] Decrements the value of the key by the given amount
        """
        raise NotImplementedError
    
    def decrbyfloat(self, key: str, amount: float = 1.0, **kwargs) -> float:
        """
        [float] Decrements the value of the key by the given amount
        """
        raise NotImplementedError
    
    async def adecr(self, key: str, amount: Union[int, float] = 1, **kwargs) -> Union[int, float]:
        """
        Decrements the value of the key by the given amount
        """
        if isinstance(amount, int): return await self.adecrby(key, amount = amount, **kwargs)
        return await self.adecrbyfloat(key, amount = amount, **kwargs)
    
    async def adecrby(self, key: str, amount: int = 1, **kwargs) -> int:
        """
        [int] Decrements the value of the key by the given amount
        """
        raise NotImplementedError
    
    async def adecrbyfloat(self, key: str, amount: float = 1.0, **kwargs) -> float:
        """
        [float] Decrements the value of the key by the given amount
        """
        raise NotImplementedError

    """
    Set Operations
    """

    def sadd(self, key: str, *values: Any, **kwargs) -> int:
        """
        Adds the value to the set
        """
        raise NotImplementedError
        
    async def asadd(self, key: str, *values: Any, **kwargs) -> int:
        """
        Adds the value to the set
        """
        return await ThreadPooler.run_async(self.sadd, key, *values, **kwargs)
    
    def slength(self, key: str, **kwargs) -> int:
        """
        Returns the length of the set
        """
        raise NotImplementedError
    
    async def aslength(self, key: str, **kwargs) -> int:
        """
        Returns the length of the set
        """
        return await ThreadPooler.run_async(self.slength, key, **kwargs)
    
    
    def sismember(self, key: str, value: Any, **kwargs) -> bool:
        """
        Returns whether the value is a member of the set
        """
        raise NotImplementedError
    
    async def asismember(self, key: str, value: Any, **kwargs) -> bool:
        """
        Returns whether the value is a member of the set
        """
        return await ThreadPooler.run_async(self.sismember, key, value, **kwargs)
    
    def smembers(self, key: str, **kwargs) -> List[Any]:
        """
        Returns the members of the set
        """
        raise NotImplementedError

    async def asembers(self, key: str, **kwargs) -> List[Any]:
        """
        Returns the members of the set
        """
        return await ThreadPooler.run_async(self.smembers, key, **kwargs)

    def smismember(self, key: str, *values: Any, **kwargs) -> bool:
        """
        Returns whether the values are members of the set
        """
        raise NotImplementedError
    
    async def asmismember(self, key: str, *values: Any, **kwargs) -> bool:
        """
        Returns whether the values are members of the set
        """
        return await ThreadPooler.run_async(self.smismember, key, *values, **kwargs)

    def srem(self, key: str, *values: Any, **kwargs) -> int:
        """
        Removes the value from the set
        """
        raise NotImplementedError
    
    async def asrem(self, key: str, *values: Any, **kwargs) -> int:
        """
        Removes the value from the set
        """
        return await ThreadPooler.run_async(self.srem, key, *values, **kwargs)
    
    def spop(self, key: str, **kwargs) -> Any:
        """
        Removes and returns a random member of the set
        """
        raise NotImplementedError
    
    async def aspop(self, key: str, **kwargs) -> Any:
        """
        Removes and returns a random member of the set
        """
        return await ThreadPooler.run_async(self.spop, key, **kwargs)
    
    """
    Schema Modification Methods
    """

    def migrate_schema(self, schema_map: Dict[str, Any], overwrite: Optional[bool] = None, **kwargs) -> None:
        """
        Migrates the schema
        """
        raise NotImplementedError
    
    async def amigrate_schema(self, schema_map: Dict[str, Any], overwrite: Optional[bool] = None, **kwargs) -> None:
        """
        Migrates the schema
        """
        await ThreadPooler.run_async(self.migrate_schema, schema_map, overwrite = overwrite, **kwargs)

    """
    Context Manager Locks
    """
    
    def acquire_lock(self, timeout: Optional[float] = None, blocking: Optional[bool] = True, **kwargs) -> bool:
        """
        Acquires the lock
        """
        if self._lock is None: self._lock = Lock()
        try:
            return self._lock.acquire(timeout = timeout, blocking = blocking)
        except Exception as e:
            logger.error(f'Error acquiring lock: {e}')
            return False
    
    def release_lock(self):
        """
        Releases the lock
        """
        if self._lock is not None:
            try:
                self._lock.release()
            except Exception as e:
                logger.error(f'Error releasing lock: {e}')

    async def acquire_alock(self, timeout: Optional[float] = None, blocking: Optional[bool] = True, **kwargs) -> bool:
        """
        Acquires the lock
        """
        if self._alock is None: self._alock = AsyncLock()
        try:
            return await self._alock.acquire(timeout = timeout, blocking = blocking)
        except Exception as e:
            logger.error(f'Error acquiring lock: {e}')
            return False
        
    async def release_alock(self):
        """
        Releases the lock
        """
        if self._alock is not None:
            try:
                await self._alock.release()
            except Exception as e:
                logger.error(f'Error releasing lock: {e}')

    """
    Cloning Methods
    """

    def clone(
        self, 
        target: Optional[Any], 
        target_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = False, 
        **kwargs
    ):
        """
        Clones the data from the current PersistentDict to a new PersistentDict
        """
        raise NotImplementedError

    async def aclone(
        self,
        target: Optional[Any], 
        target_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = False, 
        excluded: Optional[Union[str, List[str]]] = None,
        **kwargs
    ):  # sourcery skip: low-code-quality
        """
        Clones the data from the target PersistentDict to a current PersistentDict
        """
        raise NotImplementedError



    def clone_from(
        self,
        target: Any, 
        target_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = False, 
        excluded: Optional[Union[str, List[str]]] = None,
        **kwargs
    ): 
        """
        Clones the data from the target PersistentDict to a current PersistentDict
        """
        raise NotImplementedError


    async def aclone_from(
        self,
        target: Any, 
        target_base_key: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        overwrite: Optional[bool] = False, 
        excluded: Optional[Union[str, List[str]]] = None,
        **kwargs
    ): 
        """
        Clones the data from the target PersistentDict to a current PersistentDict
        """
        raise NotImplemented



