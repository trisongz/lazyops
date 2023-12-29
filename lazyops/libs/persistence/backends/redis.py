"""
Redis Persistence Type leveraging `aiokeydb` library
"""

from typing import Any, Dict, Optional, Union, Iterable, List, Type, TYPE_CHECKING
from lazyops.utils.lazy import get_keydb_session
from .base import BaseStatefulBackend, SchemaType, logger

if TYPE_CHECKING:
    from aiokeydb import KeyDBSession
    from lazyops.types.models import BaseSettings


class RedisStatefulBackend(BaseStatefulBackend):
    """
    Implements a Redis Stateful Backend
    """
    name: Optional[str] = "redis"

    # Default Global Level Settings that can then be tuned
    # at an instance level
    expiration: Optional[int] = None
    hset_disabled: Optional[bool] = False
    keyjoin: Optional[str] = ':'

    def __init__(
        self,
        name: Optional[str] = None,
        expiration: Optional[int] = None,
        hset_disabled: Optional[bool] = False,
        keyjoin: Optional[str] = None,
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
        super().__init__(
            serializer=serializer,
            serializer_kwargs=serializer_kwargs,
            base_key=base_key,
            async_enabled=async_enabled,
            settings=settings,
            **kwargs,
        )
        if name is not None: self.name = name
        if expiration is not None: self.expiration = expiration
        self.hset_enabled = (not hset_disabled and self.base_key is not None)
        if keyjoin is not None: self.keyjoin = keyjoin
        self.cache: 'KeyDBSession' = get_keydb_session(name = 'persistence', **kwargs)

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
        if self.hset_enabled: value = self.cache.hget(self.base_key, key)
        else: value = self.cache.client.get(self.get_key(key))
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
        if self.hset_enabled: values = self.cache.hmget(self.base_key, keys)
        else: values = self.cache.client.mget([self.get_key(key) for key in keys])
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
        if self.hset_enabled: self.cache.hdel(self.base_key, key)
        else: self.cache.client.delete(self.get_key(key))

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
        if self.hset_enabled: values = await self.cache.async_hmget(self.base_key, keys)
        else: values = await self.cache.async_client.mget([self.get_key(key) for key in keys])
        results = []
        for key, value in zip(keys, values):
            try: results.append(self.decode_value(value))
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
        if self.hset_enabled: await self.cache.async_hdel(self.base_key, key)
        else: await self.cache.async_client.delete(self.get_key(key))

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

    def iterate(self, **kwargs) -> Iterable[Any]:
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
    

    def get_all_data(self, exclude_base_key: Optional[bool] = False) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        if not self.hset_enabled and not self.base_key:
            raise NotImplementedError('Cannot get all data from a Redis Cache without a base key')
        if self.hset_enabled:
            data = self.cache.hgetall(self.base_key)
            results = {}
            for key, value in data.items():
                if isinstance(key, bytes): key = key.decode()
                try: results[key] = self.decode_value(value)
                except AttributeError:
                    logger.warning(f'Unable to decode value for {key}')
                    self.delete(key)
            return results
        
        keys = self._fetch_set_keys(decode = True)
        data_list = self.cache.client.mget(keys)
        results: Dict[str, Any] = {}
        for key, value in zip(keys, data_list):
            if isinstance(key, bytes): key = key.decode()
            try:
                results[key] = self.decode_value(value)
            except AttributeError:
                logger.warning(f'Unable to decode value for {key}')
                self.delete(key)
        if exclude_base_key:
            results = {k.replace(f'{self.base_key}.', ''): v for k, v in results.items()}
        return results
    
    def get_all_keys(self, exclude_base_key: Optional[bool] = False) -> List[str]:
        """
        Returns all the Keys
        """
        if not self.base_key:
            raise NotImplementedError('Cannot get all keys from a Redis Cache without a base key')
        if self.hset_enabled: return self._fetch_hset_keys(decode = True)
        keys = self._fetch_set_keys(decode = True)
        if exclude_base_key:
            keys = [key.replace(f'{self.base_key}.', '') for key in keys]
        return keys
    
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

    async def aget_all_data(self, exclude_base_key: Optional[bool] = False) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        if not self.base_key:
            raise NotImplementedError('Cannot get all data from a Redis Cache without a base key')
        if self.hset_enabled:
            data = await self.cache.async_hgetall(self.base_key)
            results = {}
            for key, value in data.items():
                if isinstance(key, bytes): key = key.decode()
                try:
                    results[key] = self.decode_value(value)
                except Exception as e:
                    logger.warning(f'Unable to decode value for {key}: {e}')
                    await self.adelete(key)
            return results
        keys = await self._afetch_set_keys(decode = True)
        data_list = await self.cache.async_client.mget(keys)
        results: Dict[str, Any] = {}
        for key, value in zip(keys, data_list):
            try:
                results[key] = self.decode_value(value)
            except Exception as e:
                logger.warning(f'Unable to decode value for {key}: {e}')
                await self.adelete(key)
        if exclude_base_key:
            results = {k.replace(f'{self.base_key}.', ''): v for k, v in results.items()}
        return results
    
    async def aget_all_keys(self, exclude_base_key: Optional[bool] = False) -> List[str]:
        """
        Returns all the Keys
        """
        if not self.base_key:
            raise NotImplementedError('Cannot get all keys from a Redis Cache without a base key')
        if self.hset_enabled: 
            return await self._afetch_hset_keys(decode = True)
        keys = await self._afetch_set_keys(decode = True)
        if exclude_base_key:
            keys = [key.replace(f'{self.base_key}.', '') for key in keys]
        return keys
    
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


    """
    Utility Functions
    """

    def _fetch_set_keys(self, decode: Optional[bool] = True) -> List[str]:
        """
        This is a utility func for non-hset
        """
        keys: List[Union[str, bytes]] = self.cache.client.keys(f'{self.base_key}{self.keyjoin}*')
        if decode: return [key.decode() if isinstance(key, bytes) else key for key in keys]
        return keys
    
    def _fetch_hset_keys(self, decode: Optional[bool] = True) -> List[str]:
        """
        This is a utility func for hset
        """
        keys: List[Union[str, bytes]] = self.cache.hkeys(self.base_key)
        if decode: return [key.decode() if isinstance(key, bytes) else key for key in keys]
        return keys

    async def _afetch_set_keys(self, decode: Optional[bool] = True) -> List[str]:
        """
        This is a utility func for non-hset
        """
        keys: List[Union[str, bytes]] = await self.cache.async_client.keys(f'{self.base_key}{self.keyjoin}*')
        if decode: return [key.decode() if isinstance(key, bytes) else key for key in keys]
        return keys
    
    async def _afetch_hset_keys(self, decode: Optional[bool] = True) -> List[str]:
        """
        This is a utility func for hset
        """
        keys: List[Union[str, bytes]] = await self.cache.async_hkeys(self.base_key)
        if decode: return [key.decode() if isinstance(key, bytes) else key for key in keys]
        return keys
    
