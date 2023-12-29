from __future__ import annotations

"""
Base Persistence Backend
"""

import collections.abc
from pathlib import Path
from pydantic import BaseModel
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Iterable, List, Type, ItemsView, TYPE_CHECKING
from lazyops.utils.helpers import  create_unique_id
from lazyops.utils.logs import logger
from lazyops.utils.pooler import ThreadPoolV2 as ThreadPooler
from ..serializers import get_serializer, SerializerT

if TYPE_CHECKING:
    from lazyops.types.models import BaseSettings

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
        self._kwargs = kwargs
    
    def get_key(self, key: str) -> str:
        """
        Gets a Key
        """
        return f'{self.base_key}.{key}' if self.base_key else key

    def encode_value(self, value: Union[Any, SchemaType], **kwargs) -> Union[str, bytes]:
        """
        Encodes a Value
        """
        return self.serializer.encode(value, **kwargs)
    
    async def aencode_value(self, value: Union[Any, SchemaType], **kwargs) -> Union[str, bytes]:
        """
        Encodes a Value
        """
        return await self.serializer.aencode(value, **kwargs)

    def decode_value(self, value: Union[str, bytes], **kwargs) -> Any:
        """
        Decodes a Value
        """
        return self.serializer.decode(value, **kwargs)
    
    async def adecode_value(self, value: Union[str, bytes], **kwargs) -> Any:
        """
        Decodes a Value
        """
        return await self.serializer.adecode(value, **kwargs)
    
    def _precheck(self, **kwargs):
        """
        Run a precheck operation
        """
        pass

    def get(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        raise NotImplementedError
            
    def get_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
        raise NotImplementedError


    def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        raise NotImplementedError


    def set_batch(self, data: Dict[str, Any], ex: Optional[int] = None, **kwargs) -> None:
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

    
    async def aget(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the DB
        """
        return await ThreadPooler.run_async(self.get, key, default, **kwargs)

    async def aget_values(self, keys: Iterable[str]) -> List[Any]:
        """
        Gets a Value from the DB
        """
        return await ThreadPooler.run_async(self.get_values, keys)

    
    async def aset(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> None:
        """
        Saves a Value to the DB
        """
        return await ThreadPooler.run_async(self.set, key, value, ex, **kwargs)


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


    def get_all_data(self, exclude_base_key: Optional[bool] = False) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        raise NotImplementedError


    def get_all_keys(self, exclude_base_key: Optional[bool] = False) -> List[str]:
        """
        Returns all the Keys
        """
        raise NotImplementedError


    def get_all_values(self) -> List[Any]:
        """
        Returns all the Values
        """
        raise NotImplementedError


    async def aget_all_data(self, exclude_base_key: Optional[bool] = False) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        return await ThreadPooler.run_async(self.get_all_data)

    async def aget_all_keys(self, exclude_base_key: Optional[bool] = False) -> List[str]:
        """
        Returns all the Keys
        """
        return await ThreadPooler.run_async(self.get_all_keys)

    async def aget_all_values(self) -> List[Any]:
        """
        Returns all the Values
        """
        return await ThreadPooler.run_async(self.get_all_values)


    def pop(self, key, default = None):
        """
        Pops an Item from the Cache
        """
        self._precheck()
        value = self.get(key)
        if value is not None:
            if self.async_enabled:
                ThreadPooler.create_background_task(self.adelete(key))
            else:
                self.delete(key)
            return value
        return default
    
    async def apop(self, key, default = None):
        """
        Pops an Item from the Cache
        """
        self._precheck()
        value = await self.aget(key)
        if value is not None:
            await self.adelete(key)
            return value
        return default

    def contains(self, key: str) -> bool:
        """
        Returns True if the Cache contains the Key
        """
        raise NotImplementedError

    async def acontains(self, key: str) -> bool:
        """
        Returns True if the Cache contains the Key
        """
        return await ThreadPooler.run_async(self.contains, key)

    def keys(self) -> Iterable[str]:
        """
        Returns the Keys
        """
        return iter(self.get_all_keys(True))
    
    def values(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        return iter(self.get_all_values())
    
    def items(self) -> Iterable[ItemsView]:
        """
        Returns the Items
        """
        return self.get_all_data(True).items()
        # return iter(self.get_all_data())
    
    async def akeys(self) -> Iterable[Any]:
        """
        Returns the Keys
        """
        return iter(await self.aget_all_keys(True))
    
    async def avalues(self) -> Iterable[Any]:
        """
        Returns the Values
        """
        return iter(await self.aget_all_values())
    
    async def aitems(self) -> Iterable[ItemsView]:
        """
        Returns the Items
        """
        return (await self.aget_all_data(True)).items()
    
    def setdefault(self, key: str, default: Any = None):
        """
        Sets a Default Value
        """
        if self.contains(key):
            return self.get(key)
        self.set(key, default)
        return default        
    
    async def asetdefault(self, key: str, default: Any = None):
        """
        Sets a Default Value
        """
        if await self.acontains(key):
            return await self.aget(key)
        await self.aset(key, default)
        return default
    
    def update(self, data: Dict[str, Any]):
        """
        Updates the Cache
        """
        for key, value in data.items():
            self.set(key, value)
    
    async def aupdate(self, data: Dict[str, Any]):
        """
        Updates the Cache
        """
        for key, value in data.items():
            await self.aset(key, value)

    def popitem(self):
        """
        Pops an Item from the Cache
        """
        self._precheck()
        key = next(iter(self))
        value = self.get(key)
        if value is not None:
            if self.async_enabled:
                ThreadPooler.create_background_task(self.adelete(key))
            else:
                self.delete(key)
            return key, value
        return None, None
    
    async def apopitem(self):
        """
        Pops an Item from the Cache
        """
        self._precheck()
        key = next(iter(self))
        value = await self.aget(key)
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
    
