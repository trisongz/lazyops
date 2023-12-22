"""
Persistence Types

- Handles persistence of data with Redis or JSON+Pickle
"""

import json
import zlib
import filelock
import binascii
import diskcache
import cloudpickle
import contextlib
import collections.abc

from io import BytesIO
from pathlib import Path
from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Iterable, List, Type, TYPE_CHECKING
from lazyops.utils.helpers import  create_unique_id


from ..utils.logs import logger


try:
    from fileio import File
except ImportError:
    logger.warning('FileIO is not installed. Not all persistence functionality will be available.')
    File = Path

from ..utils.lazy import get_keydb_session, get_scout_settings, get_keydb_enabled, is_async_enabled, ThreadPooler

SchemaType = TypeVar("SchemaType", bound=BaseModel)

if TYPE_CHECKING:
    from scout.configs import ScoutSettings
    from simdjson import Object, SimValue


class LocalStatefulDict(collections.abc.MutableMapping):
    """
    Implements a Local Stateful Dictionary
    """

    def __init__(
        self,
        file_path: Optional[File] = None,
        encoding: Optional[str] = "utf-8",
        base_key: Optional[str] = None,
        async_enabled: Optional[bool] = False,
        **kwargs,
    ):
        import simdjson
        
        self.parser = simdjson.Parser()
        self.settings = get_scout_settings()
        self.file_path = File(file_path) if file_path is not None else File(self.settings.data_dir.joinpath("scout.cache"))
        self.file_path.parent.mkdir(parents = True, exist_ok = True)
        self.file_lock_path = self.file_path.with_suffix(".lock")
        self.file_hash_path = self.file_path.with_suffix(".hash")
        self.file_lock = filelock.FileLock(lock_file = self.file_lock_path.as_posix(), thread_local = False)
        self.encoding = encoding
        self.async_enabled = async_enabled
        self.cache: SimValue = None
        self.base_key = base_key
        if not self.file_path.exists():
            with self.file_lock:
                self.file_path.write_text('{}')
                self.file_hash = create_unique_id()
                self.file_hash_path.write_text(self.file_hash)
        else:
            self.cache = self.get_data()
            self.file_hash = self.file_hash_path.read_text()
    
    def should_sync(self) -> bool:
        """
        Returns True if the File should be Synced
        """
        return self.file_hash != self.file_hash_path.read_text()
    
    async def ashould_sync(self) -> bool:
        """
        Returns True if the File should be Synced
        """
        return self.file_hash != await self.file_hash_path.async_read_text()
    
    @property
    def cache_data(self) -> Dict[str, Any]:
        """
        Returns the Cache Data
        """
        return self.cache# .as_dict()
    
    def get_cache_data(self) -> Dict[str, Any]:
        """
        Returns the Cache Data
        """
        return self.cache# .as_dict()

    def sync(self) -> None:
        """
        Syncs the File
        """
        if self.should_sync():
            self.cache = self.get_data()

    async def async_sync(self) -> None:
        """
        Syncs the File
        """
        if await self.ashould_sync():
            self.cache = await self.aget_data()

    def get_data(self) -> 'SimValue':
        """
        Returns the Data
        """
        with self.file_lock:
            return self.parser.parse(self.file_path.read_bytes(), recursive=True)
    
    async def aget_data(self) -> 'SimValue':
        """
        Fetch the data
        """
        with self.file_lock:
            return self.parser.parse(await self.file_path.async_read_bytes(), recursive=True)

    def encode_value(self, value: Any) -> str:
        """
        Encodes a Value
        """
        return cloudpickle.dumps(value).hex()
    
    def decode_value(self, value: str) -> Any:
        """
        Decodes a Value
        """
        return cloudpickle.loads(binascii.unhexlify(value), fix_imports=False)
    
    def get_key(self, key: str) -> str:
        """
        Gets a Key
        """
        return f'{self.base_key}.{key}' if self.base_key else key

    def get(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the JSON
        """
        self.sync()
        if value := self.cache.get(self.get_key(key)):
            try:
                return self.decode_value(value)
            except AttributeError:
                logger.warning(f'Unable to decode value for {key}')
                self.delete(key)
                return default
        return default

    def get_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the JSON
        """
        self.sync()
        results = []
        for key in keys:
            if value := self.cache.get(self.get_key(key)):
                try:
                    results.append(self.decode_value(value))
                except AttributeError:
                    logger.warning(f'Unable to decode value for {key}')
                    self.delete(key)
                    results.append(None)
            else:
                results.append(None)
        return results

    def set(self, key: str, value: Any, **kwargs) -> None:
        """
        Sets a Value in the JSON
        """
        self.sync()
        cache_data = self.get_cache_data()
        cache_data[self.get_key(key)] = self.encode_value(value)
        logger.info(f'Setting {key}')
        logger.info(f'Cache Data: {len(cache_data)}')

        self.write_data(cache_data)
    
    def set_batch(self, data: Dict[str, Any], **kwargs) -> None:
        """
        Sets a Value in the JSON
        """
        self.sync()
        cache_data = self.get_cache_data()
        for key, value in data.items():
            cache_data[self.get_key(key)] = self.encode_value(value)
        self.write_data(cache_data)

    def delete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the JSON
        """
        self.sync()
        cache_data = self.get_cache_data()
        _ = cache_data.pop(self.get_key(key))
        self.write_data(cache_data)

    def clear(self, *keys, **kwargs):
        """
        Clears the Cache
        """
        self.sync()
        cache_data = self.get_cache_data()
        if keys:
            for key in keys:
                _ = cache_data.pop(self.get_key(key))
        else:
            cache_data = {}
        self.write_data(cache_data)
    

    async def aget(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the JSON
        """
        await self.async_sync()
        if value := self.cache.get(self.get_key(key)):
            try:
                return self.decode_value(value)
            except AttributeError:
                logger.warning(f'Unable to decode value for {key}')
                await self.adelete(key)
                return default
        return default
    
    async def aget_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the JSON
        """
        await self.async_sync()
        results = []
        for key in keys:
            if value := self.cache.get(self.get_key(key)):
                try:
                    results.append(self.decode_value(value))
                except AttributeError:
                    logger.warning(f'Unable to decode value for {key}')
                    await self.adelete(key)
                    results.append(None)
            else:
                results.append(None)
        return results

    async def aset(self, key: str, value: Any, **kwargs) -> None:
        """
        Sets a Value in the JSON
        """
        await self.async_sync()
        cache_data = self.get_cache_data()
        cache_data[self.get_key(key)] = self.encode_value(value)
        await self.awrite_data(cache_data)

    async def aset_batch(self, data: Dict[str, Any], **kwargs) -> None:
        """
        Sets a Value in the JSON
        """
        await self.async_sync()
        cache_data = self.get_cache_data()
        for key, value in data.items():
            cache_data[self.get_key(key)] = self.encode_value(value)
        await self.awrite_data(cache_data)

    async def adelete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the JSON
        """
        await self.async_sync()
        cache_data = self.get_cache_data()
        _ = cache_data.pop(self.get_key(key))
        await self.awrite_data(cache_data)

    async def aclear(self, *keys, **kwargs):
        """
        Clears the Cache
        """
        await self.async_sync()
        cache_data = self.get_cache_data()
        if keys:
            for key in keys:
                _ = cache_data.pop(self.get_key(key))
        else:
            cache_data = {}
        await self.awrite_data(cache_data)

    def write_data(self, data: Dict):
        """
        Writes the Data to the File
        """
        with self.file_lock:
            self.file_path.write_text(json.dumps(data, indent = 4, ensure_ascii = False))
            self.file_hash = create_unique_id()
            self.file_hash_path.write_text(self.file_hash)
    
    async def awrite_data(self, data: Dict):
        """
        Writes the Data to the File
        """
        with self.file_lock:
            await self.file_path.async_write_text(json.dumps(data, indent = 4, ensure_ascii = False))
            self.file_hash = create_unique_id()
            await self.file_hash_path.async_write_text(self.file_hash)

    def get_all_keys(self) -> Iterable[str]:
        """
        Returns all the Keys
        """
        return [
            key
            for key in self.cache.keys()
            if key.startswith(self.base_key)
        ] if self.base_key else list(self.cache.keys())

    def get_all_data(self) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        self.sync()
        all_keys = self.get_all_keys()
        # cache_data = self.get_cache_data()
        return {
            key: self.decode_value(value)
            for key, value in self.cache.items() if key in all_keys
        }
    
    def get_all_values(self) -> Iterable[Any]:
        """
        Returns all the Values
        """
        self.sync()
        all_keys = self.get_all_keys()
        return [
            self.decode_value(value)
            for key, value in self.cache.items() if key in all_keys
        ]
    

    async def aget_all_data(self) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        await self.async_sync()
        return self.get_all_data()
        
    
    async def aget_all_keys(self) -> Iterable[str]:
        """
        Returns all the Keys
        """
        await self.async_sync()
        return self.get_all_keys()
    
    async def aget_all_values(self) -> Iterable[Any]:
        """
        Returns all the Values
        """
        await self.async_sync()
        return self.get_all_values()


    def __getitem__(self, key):
        """
        Gets an Item from the Cache
        """
        return self.get(key)

    def __setitem__(self, key, value):
        """
        Sets an Item in the Cache
        """
        # if self.async_enabled:
        #     create_background_task(self.aset(key, value))
        # else: 
        self.set(key, value)
    
    def __delitem__(self, key):
        """
        Deletes an Item from the Cache
        """
        if self.async_enabled:
            ThreadPooler.create_background_task(self.adelete(key))
        else:
            self.delete(key)

    def __iter__(self):
        """
        Iterates over the Cache
        """
        self.sync()
        return iter(self.get_all_data())
    
    def keys(self) -> Iterable[Any]:
        """
        Returns the Keys
        """
        self.sync()
        return self.get_all_keys()
    
    def values(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        self.sync()
        return self.get_all_values()
    
    def items(self) -> Iterable[Any]:
        """
        Returns the Items
        """
        self.sync()
        return self.get_all_data()
    

    async def akeys(self) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return iter(await self.aget_all_keys())
    
    async def avalues(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        return iter(await self.aget_all_values())
    
    async def aitems(self) -> Iterable[Any]:
        """
        Returns the Items
        """
        return iter(await self.aget_all_data())
    
    def __len__(self):
        """
        Returns the Length of the Cache
        """
        self.sync()
        return len(self.get_all_keys())
    
    def __repr__(self):
        """
        Returns the Representation of the Cache
        """
        self.sync()
        return f'LocalStatefulDict(keys = {list(self.keys())})'
    
    
    def pop(self, key, default = None):
        """
        Pops an Item from the Cache
        """
        self.sync()
        value = self.get(key)
        if value is not None:
            if self.async_enabled:
                ThreadPooler.create_background_task(self.adelete(key))
            else:
                self.delete(key)
            return value
        return default
    
    def contains(self, key):
        """
        Returns True if the Cache contains the Key
        """
        self.sync()
        return key in self.get_all_keys()
    
    async def acontains(self, key):
        """
        Returns True if the Cache contains the Key
        """
        await self.async_sync()
        return key in self.get_all_keys()
    
    def __contains__(self, key):
        """
        Returns True if the Cache contains the Key
        """
        self.sync()
        return key in self.get_all_keys()
    
    def __eq__(self, other):
        """
        Returns True if the Cache is Equal to the Other
        """
        self.sync()
        return self.get_all_data() == other

class RedisStatefulDict(collections.abc.MutableMapping):
    def __init__(
        self, 
        base_key: Optional[str] = None,
        expiration: Optional[int] = None,
        async_enabled: Optional[bool] = False,
        hset_disabled: Optional[bool] = False,
        
        compression_level: Optional[int] = None,
        serialization_json: Optional[bool] = False,
        serialization_obj_kwargs: Optional[Dict[str, Any]] = None,
        keyjoin: Optional[str] = ':',
        **kwargs,
    ):
        self.cache = get_keydb_session(name = 'persistence', **kwargs, validate_active = True)
        assert self.cache is not None, "Redis is not enabled"
        self.base_key = base_key
        self.keyjoin = keyjoin
        self.expiration = expiration
        self.async_enabled = async_enabled
        self.compression_level = compression_level
        self.serialization_json = serialization_json
        self.serialization_obj_kwargs = serialization_obj_kwargs or {}
        self.hset_enabled = (not hset_disabled and self.base_key is not None)
        self.parser = None
        # logger.info(f'Base Key: {self.base_key} | HSET Enabled: {self.hset_enabled}')
    
    def encode_value(self, value: Union[Any, SchemaType]) -> bytes:
        """
        Encodes a Value
        """

        # with contextlib.suppress(Exception):
        if self.serialization_json:
            try:
                if hasattr(value, 'model_dump'):  value = value.model_dump(mode = 'json', round_trip=True, **self.serialization_obj_kwargs)
            except Exception as e:
                logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {value}', colored = True)
        
        value = json.dumps(value).encode('utf-8') \
            if self.serialization_json else cloudpickle.dumps(value)
        return zlib.compress(value, level = self.compression_level) \
            if self.compression_level is not None else value
    
    def decode_value(self, value: bytes) -> Any:
        """
        Decodes a Value
        """
        value = zlib.decompress(value) if self.compression_level is not None else value
        value = json.loads(value.decode(encoding='utf-8')) \
            if self.serialization_json else cloudpickle.loads(value, fix_imports=False, encoding='utf-8')
        return value
    
    def get_key(self, key: str) -> str:
        """
        Gets a Key
        """
        if not self.base_key: return key
        return key if self.base_key in key else f'{self.base_key}{self.keyjoin}{key}'
    
    def get(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        if self.hset_enabled:
            value = self.cache.hget(self.base_key, key)
        else:
            value = self.cache.client.get(self.get_key(key))
        if value is None: return default
        try:
            return self.decode_value(value)
        except Exception as e:
            logger.error(f'Error Getting Value: {e}')
            self.delete(key)
            return default
        
    def get_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
        if self.hset_enabled:
            values = self.cache.hmget(self.base_key, keys)
        else:
            values = self.cache.client.mget([self.get_key(key) for key in keys])
        results = []
        for key, value in zip(keys, values):
            try:
                results.append(self.decode_value(value))
            except Exception as e:
                logger.error(f'Error Getting Value: {e}')
                self.delete(key)
                results.append(None)
        return results
    
    def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        ex = ex or self.expiration
        if self.hset_enabled:
            self.cache.hset(self.base_key, key, self.encode_value(value))
            if ex is not None: self.cache.expire(self.base_key, ex)
        else:
            self.cache.client.set(self.get_key(key), self.encode_value(value), ex = ex)
    
    def set_batch(self, data: Dict[str, Any], ex: Optional[int] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        ex = ex or self.expiration
        data = {k: self.encode_value(v) for k, v in data.items()}
        if self.hset_enabled:
            self.cache.client.hset(self.base_key, mapping = data)
            if ex is not None: self.cache.expire(self.base_key, ex)
        else:
            if self.base_key: data = {self.get_key(k): v for k, v in data.items()}
            self.cache.client.mset(data)
            if ex is not None:
                for key in data:
                    self.cache.client.expire(key, ex)

    def delete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        if self.hset_enabled:
            self.cache.hdel(self.base_key, key)
        else:
            self.cache.client.delete(self.get_key(key))

    def clear(self, *keys, **kwargs):
        """
        Clears the Cache
        """
        if self.hset_enabled:
            if keys: self.cache.hdel(self.base_key, *keys)
            else: self.cache.delete(self.base_key)
        elif keys:
            keys = [self.get_key(key) for key in keys]
            self.cache.delete(*keys)

        else:
            keys = self.cache.client.keys(f'{self.base_key}{self.keyjoin}*')
            if keys: self.cache.client.delete(*keys)
    
    async def aget(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        if self.hset_enabled: value = await self.cache.async_hget(self.base_key, key)
        else: value = await self.cache.async_client.get(self.get_key(key))
        if value is None: return default
        try:
            return self.decode_value(value)
        except Exception as e:
            logger.error(f'Error Getting Value: {e}')
            await self.adelete(key)
            return default
        
    async def aget_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
        if self.hset_enabled:
            values = await self.cache.async_hmget(self.base_key, keys)
        else:
            values = await self.cache.async_client.mget([self.get_key(key) for key in keys])
        results = []
        for key, value in zip(keys, values):
            try:
                results.append(self.decode_value(value))
            except Exception as e:
                logger.error(f'Error Getting Value: {e}')
                await self.adelete(key)
                results.append(None)
        return results
        
    async def aset(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        ex = ex or self.expiration
        if self.hset_enabled:
            await self.cache.async_hset(self.base_key, key, self.encode_value(value))
            if ex is not None: await self.cache.async_expire(self.base_key, ex)
        else:
            await self.cache.async_client.set(self.get_key(key), self.encode_value(value), ex = ex)

    async def aset_batch(self, data: Dict[str, Any], ex: Optional[int] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        ex = ex or self.expiration
        data = {k: self.encode_value(v) for k, v in data.items()}
        if self.hset_enabled:
            await self.cache.async_client.hset(self.base_key, mapping = data)
            if ex is not None: await self.cache.async_expire(self.base_key, ex)
        else:
            if self.base_key: data = {self.get_key(k): v for k, v in data.items()}
            await self.cache.async_client.mset(data)
            if ex is not None:
                for key in data:
                    await self.cache.async_client.expire(key, ex)
    
    async def adelete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the DB
        """
        if self.hset_enabled:
            await self.cache.async_hdel(self.base_key, key)
        else:
            await self.cache.async_client.delete(self.get_key(key))

    async def aclear(self, *keys, **kwargs):
        """
        Clears the Cache
        """
        if self.hset_enabled:
            if keys: await self.cache.async_hdel(self.base_key, *keys)
            else: await self.cache.async_delete(self.base_key)
        elif keys:
            keys = [self.get_key(key) for key in keys]
            await self.cache.async_delete(*keys)

        else:
            keys = await self.cache.async_client.keys(f'{self.base_key}{self.keyjoin}*')
            if keys: await self.cache.async_client.delete(*keys)

    def __getitem__(self, key):
        """
        Gets an Item from the DB
        """
        return self.get(key)

    def __setitem__(self, key, value):
        """
        Sets an Item in the Cache
        """
        if self.async_enabled:
            ThreadPooler.create_background_task(self.aset(key, value))
        else:
            self.set(key, value)
    
    def __delitem__(self, key):
        """
        Deletes an Item from the Cache
        """
        if self.async_enabled:
            ThreadPooler.create_background_task(self.adelete(key))
        else:
            self.delete(key)

    def __iter__(self):
        """
        Iterates over the Cache
        """
        if self.hset_enabled: return iter(self.cache.hkeys(self.base_key))
        if not self.base_key:
            raise NotImplementedError('Cannot iterate over a Redis Cache without a base key')
        return iter(self.cache.client.keys(f'{self.base_key}{self.keyjoin}*'))
    
    def __len__(self):
        """
        Returns the Length of the Cache
        """
        if self.hset_enabled: return self.cache.hlen(self.base_key)
        if not self.base_key:
            raise NotImplementedError('Cannot get the length of a Redis Cache without a base key')
        return len(self.cache.client.keys(f'{self.base_key}{self.keyjoin}*'))
    
    def _fetch_set_keys(self, decode: Optional[bool] = True) -> List[str]:
        """
        This is a utility func for non-hset
        """
        keys: List[Union[str, bytes]] = self.cache.client.keys(f'{self.base_key}{self.keyjoin}*')
        if decode: return [key.decode() if isinstance(key, bytes) else key for key in keys]
        return keys
    
    async def _afetch_set_keys(self, decode: Optional[bool] = True) -> List[str]:
        """
        This is a utility func for non-hset
        """
        keys: List[Union[str, bytes]] = await self.cache.async_client.keys(f'{self.base_key}{self.keyjoin}*')
        if decode: return [key.decode() if isinstance(key, bytes) else key for key in keys]
        return keys

    def get_all_data(self) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        if not self.hset_enabled and not self.base_key:
            raise NotImplementedError('Cannot get all data from a Redis Cache without a base key')
        if self.hset_enabled:
            data = self.cache.hgetall(self.base_key)
            results = {}
            for key, value in data.items():
                try:
                    results[key] = self.decode_value(value)
                except AttributeError:
                    logger.warning(f'Unable to decode value for {key}')
                    self.delete(key)
            return results
        
        keys = self._fetch_set_keys(decode = True)
        data_list = self.cache.client.mget(keys)
        results = {}
        for key, value in zip(keys, data_list):
            try:
                results[key] = self.decode_value(value)
            except AttributeError:
                logger.warning(f'Unable to decode value for {key}')
                self.delete(key)
        return results

    
    def get_all_keys(self) -> List[str]:
        """
        Returns all the Keys
        """
        if not self.base_key:
            raise NotImplementedError('Cannot get all keys from a Redis Cache without a base key')
        if self.hset_enabled: return self.cache.hkeys(self.base_key)
        return self._fetch_set_keys(decode = True)
    
    def get_all_values(self) -> List[Any]:
        """
        Returns all the Values
        """
        if not self.base_key:
            raise NotImplementedError('Cannot get all values from a Redis Cache without a base key')
        if self.hset_enabled:
            data = self.cache.hgetall(self.base_key)
            results = []
            for key, value in data.items():
                try:
                    results.append(self.decode_value(value))
                except Exception as e:
                    logger.warning(f'Unable to decode value for {key}: {e}')
                    self.delete(key)
            return results
        keys = self._fetch_set_keys(decode = False)
        data_list = self.cache.client.mget(keys)
        results = []
        for key, value in zip(keys, data_list):
            try:
                results.append(self.decode_value(value))
            except Exception as e:
                logger.warning(f'Unable to decode value for {key}: {e}')
                self.delete(key)
        return results
    

    async def aget_all_data(self) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        if not self.base_key:
            raise NotImplementedError('Cannot get all data from a Redis Cache without a base key')
        if self.hset_enabled:
            data = await self.cache.async_hgetall(self.base_key)
            results = {}
            for key, value in data.items():
                try:
                    results[key] = self.decode_value(value)
                except Exception as e:
                    logger.warning(f'Unable to decode value for {key}: {e}')
                    await self.adelete(key)
            return results
        keys = await self._afetch_set_keys(decode = True)
        data_list = await self.cache.async_client.mget(keys)
        results = {}
        for key, value in zip(keys, data_list):
            try:
                results[key] = self.decode_value(value)
            except Exception as e:
                logger.warning(f'Unable to decode value for {key}: {e}')
                await self.adelete(key)
        return results
    
    async def aget_all_keys(self) -> List[str]:
        """
        Returns all the Keys
        """
        if not self.base_key:
            raise NotImplementedError('Cannot get all keys from a Redis Cache without a base key')
        if self.hset_enabled: return await self.cache.async_hkeys(self.base_key)
        return await self._afetch_set_keys(decode = True)
    
    async def aget_all_values(self) -> List[Any]:
        """
        Returns all the Values
        """
        if not self.base_key:
            raise NotImplementedError('Cannot get all values from a Redis Cache without a base key')
        if self.hset_enabled:
            data = await self.cache.async_hgetall(self.base_key)
            results = []
            for key, value in data.items():
                try:
                    results.append(self.decode_value(value))
                except Exception as e:
                    logger.warning(f'Unable to decode value for {key}: {e}')
                    await self.adelete(key)
            return results
        keys = await self._afetch_set_keys(decode = False)
        data_list = await self.cache.async_client.mget(keys)
        results = []
        for key, value in zip(keys, data_list):
            try:
                results.append(self.decode_value(value))
            except Exception as e:
                logger.warning(f'Unable to decode value for {key}: {e}')
                await self.adelete(key)
        return results

    def __repr__(self):
        """
        Returns the Representation of the Cache
        """
        return f'RedisStatefulDict(keys = {list(self.keys())})'
    
    def pop(self, key, default = None):
        """
        Pops an Item from the Cache
        """
        value = self.get(key)
        if value is not None:
            if self.async_enabled:
                ThreadPooler.create_background_task(self.adelete(key))
            else:
                self.delete(key)
            return value
        return default
    
    def contains(self, key):
        """
        Returns True if the Cache contains the Key
        """
        if self.hset_enabled: return self.cache.hexists(self.base_key, key)
        return self.cache.client.exists(self.get_key(key))
    
    async def acontains(self, key):
        """
        Returns True if the Cache contains the Key
        """
        if self.hset_enabled: return await self.cache.async_hexists(self.base_key, key)
        return await self.cache.async_client.exists(self.get_key(key))

    def __contains__(self, key):
        """
        Returns True if the Cache contains the Key
        """
        return self.contains(key)
    
    def __eq__(self, other):
        """
        Returns True if the Cache is Equal to the Other
        """
        return self.get_all_data() == other
    
    def keys(self) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return iter(self.get_all_keys())
    
    def values(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        return iter(self.get_all_values())
    
    def items(self) -> Dict[Any, Any]:
        """
        Returns the Items
        """
        return dict(self.get_all_data())
    
    async def akeys(self) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return iter(await self.aget_all_keys())
    
    async def avalues(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        return iter(await self.aget_all_values())
    
    async def aitems(self) -> Dict[Any, Any]:
        """
        Returns the Items
        """
        return dict(await self.aget_all_data())
    

class PersistentDict(ABC):
    """
    Persistent Dictionary
    """
    async_dict_enabled: bool = False

    def __init__(self, base_key: Optional[str] = None, async_enabled: Optional[bool] = None, **kwargs):
        self.settings = get_scout_settings()
        self.base_class = RedisStatefulDict if get_keydb_enabled() else LocalStatefulDict
        self.base = self.base_class(base_key = base_key, async_enabled = async_enabled, **kwargs)
        self.base_key = base_key
        self._kwargs = kwargs

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
        return self.base.get(key, default = default, **kwargs)
    
    def get_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
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
        return await self.base.aget(key, default = default, **kwargs)
    
    async def aget_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
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
    
    def __repr__(self):
        """
        Returns the Representation of the Cache
        """
        return repr(self.base)
    

    if async_dict_enabled:
        async def __getitem__(self, key):
            """
            Gets an Item from the DB
            """
            return await self.base.aget(key)
    
    else:
        def __getitem__(self, key):
            """
            Gets an Item from the DB
            """
            return self.base.get(key)
    
    def __setitem__(self, key, value):
        """
        Sets an Item in the Cache
        """
        if self.base.async_enabled:
            ThreadPooler.create_background_task(self.base.aset(key, value))
        else:
            self.base.set(key, value)

    def __delitem__(self, key):
        """
        Deletes an Item from the Cache
        """
        if self.base.async_enabled:
            ThreadPooler.create_background_task(self.base.adelete(key))
        else:
            self.base.delete(key)
    
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
    
    def get_all_data(self) -> Dict[str, Any]:
        """
        Loads all the Data
        """
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
        return self.base.get_all_values()
    
    async def aget_all_data(self) -> Dict[str, Any]:
        """
        Loads all the Data
        """
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
        return self.base.values()
    
    def items(self) -> Dict[Any, Any]:
        """
        Returns the Items
        """
        return self.base.items()
    
    async def akeys(self) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return await self.base.akeys()
    
    async def avalues(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        return await self.base.avalues()
    
    async def aitems(self) -> Dict[Any, Any]:
        """
        Returns the Items
        """
        return await self.base.aitems()

"""
Custom Diskcache Implementation
"""

class CloudPickleDisk(diskcache.Disk):
    """Cache key and value using CloudPickle serialization with zlib compression."""

    def __init__(self, directory, compress_level: int = 3, **kwargs):
        """Initialize CloudPickle disk instance.

        Keys and values are compressed using the zlib library. The
        `compress_level` is an integer from 0 to 9 controlling the level of
        compression; 1 is fastest and produces the least compression, 9 is
        slowest and produces the most compression, and 0 is no compression.

        :param str directory: directory path
        :param int compress_level: zlib compression level (default 3)
        :param kwargs: super class arguments

        """
        self.compress_level = compress_level
        super().__init__(directory, **kwargs)

    def put(self, key):
        pbytes = cloudpickle.dumps(key)
        data = zlib.compress(pbytes, self.compress_level)
        return super().put(data)

    def get(self, key, raw):
        data = super().get(key, raw)
        return cloudpickle.loads(zlib.decompress(data), encoding='utf-8')

    def store(self, value, read, key = diskcache.UNKNOWN):
        if not read:
            pbytes = cloudpickle.dumps(value)
            value = zlib.compress(pbytes, level = self.compress_level)
        return super().store(value, read, key=key)

    def fetch(self, mode, filename, value, read):
        data = super().fetch(mode, filename, value, read)
        if not read: data = cloudpickle.loads(zlib.decompress(data), encoding='utf-8')
        return data


def create_diskcache(
    directory: Optional[Union[str, Path]] = None,
    disk: Optional[Type[diskcache.Disk]] = CloudPickleDisk,
    **kwargs,
) -> diskcache.Cache:
    """
    Returns a Diskcache
    """
    directory = directory or get_scout_settings().diskcache_dir
    directory = Path(directory)
    directory.mkdir(parents = True, exist_ok = True)
    return diskcache.Cache(directory = directory, disk = disk, **kwargs)