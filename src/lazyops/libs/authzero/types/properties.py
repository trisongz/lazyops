from __future__ import annotations

"""
Persistence Types
"""

from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Any, Dict, Optional, Iterable, Type, TYPE_CHECKING

SchemaType = TypeVar("SchemaType", bound=BaseModel)

if TYPE_CHECKING:
    from kvdb import PersistentDict
    from lazyops.libs.authzero.configs import AuthZeroSettings


class StatefulProperty(Generic[SchemaType], ABC):
    """
    Router Class for Stateful Properties
    """
    __obj_: Optional[SchemaType] = None
    _settings: Optional['AuthZeroSettings'] = None
    name: Optional[str] = None
    schema_type: Type[BaseModel] = None

    def __init__(
        self, 
        cache_key: str,
        serializer: Optional[str] = "json",
        serializer_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initializes the Stateful Property
        """
        self.cache_key = cache_key
        self._pdict: Optional['PersistentDict'] = None
        self._pdict_kwargs: Dict[str, Any] = {
            'serializer': serializer,
            'serializer_kwargs': serializer_kwargs,
            **kwargs,
        }
        self.data_cache_key = f'{self.cache_key}:data'

    @property
    def settings(self) -> 'AuthZeroSettings':
        """
        Returns the settings
        """
        if self._settings is None:
            from lazyops.libs.authzero.utils.lazy import get_az_settings
            self._settings = get_az_settings()
        return self._settings
    
    @property
    def pdict(self) -> 'PersistentDict':
        """
        Returns the Persistent Dict
        """
        if self._pdict is None:
            from lazyops.libs.authzero.utils.lazy import get_az_pdict
            from lazyops.libs.authzero.utils.helpers import normalize_audience_name
            base_key = f'{self.settings.base_cache_key}.'
            if self.settings.app_name:
                base_key += f'{self.settings.app_name}.'
            elif self.settings.app_ingress:
                base_key += f'{normalize_audience_name(self.settings.app_ingress)}.'
            else: base_key += 'default.'
            base_key += f'{self.settings.app_env.name}.{self.name}'
            base_key = base_key.replace(' ', '_').lower().replace('..', '.')
            self._pdict = get_az_pdict(
                base_key = base_key,
                **self._pdict_kwargs,
            )
        return self._pdict

    @property
    def resource(self) -> SchemaType:
        """
        Returns the Object Resource
        """
        # if self.__obj_ is None or (self.__obj_ is not None and self.is_expired(self.__obj_)):
        if self.__obj_ is None or self.is_expired(self.__obj_):
            self.__obj_ = self.fetch()
        return self.__obj_
    
    @property
    async def aresource(self) -> SchemaType:
        """
        Returns the Object Resource
        """
        if self.__obj_ is None or self.is_expired(self.__obj_):
            self.__obj_ = await self.afetch()
        return self.__obj_

    def __call__(self, *args, **kwargs) -> Any:
        """
        Call the proxy object
        """
        return self.resource(*args, **kwargs)

    def __getattr__(self, name):
        """
        Forward all unknown attributes to the proxy object
        """
        if hasattr(self.resource, name):
            return getattr(self.resource, name)
        raise AttributeError(f"Property {name} not found in {self.name}")

    def fetch(self) -> SchemaType:
        """
        Returns the Value
        """
        data = self.pdict.get(self.cache_key)
        if data is None or not self.is_valid_type(data) or self.is_expired(data):
            data = self.load()
            self.pdict.set(self.cache_key, data, ex = self.get_ttl(data))
        return data
    
    async def afetch(self) -> SchemaType:
        """
        Returns the Value
        """
        data = await self.pdict.aget(self.cache_key)
        if data is None or not self.is_valid_type(data) or self.is_expired(data):
            data = await self.aload()
            await self.pdict.aset(self.cache_key, data, ex = self.get_ttl(data))
        return data
    
    @classmethod
    def get(cls, *args, **kwargs) -> SchemaType:
        """
        Get the value
        """
        return cls(*args, **kwargs).fetch()
    
    @classmethod
    async def aget(cls, *args, **kwargs) -> SchemaType:
        """
        Get the value
        """
        return await cls(*args, **kwargs).afetch()

    def is_valid_type(self, data: Any) -> bool:
        """
        Returns True if the Data is a Valid Type
        """
        return self.schema_type is None or isinstance(data, self.schema_type)

    async def aload(self) -> SchemaType:
        """
        Loads the Data
        """
        raise NotImplementedError

    def load(self) -> SchemaType:
        """
        Loads the Data
        """
        raise NotImplementedError

    def is_expired(self, data: SchemaType) -> bool:
        """
        Returns True if the Data is Expired
        """
        raise getattr(data, 'is_expired', False)

    def get_ttl(self, data: SchemaType) -> int:
        """
        Returns the TTL
        """
        return None
    
    def save(self, data: SchemaType, ex: Optional[int] = None) -> None:
        """
        Saves the Object
        """
        self.pdict.set(self.cache_key, data, ex = ex or self.get_ttl(data))

    async def asave(self, data: SchemaType, ex: Optional[int] = None) -> None:
        """
        Saves the Object
        """
        await self.pdict.aset(self.cache_key, data, ex = ex or self.get_ttl(data))

    def delete(self):
        """
        Deletes the Object
        """
        self.pdict.delete(self.cache_key)

    async def adelete(self):
        """
        Deletes the Object
        """
        await self.pdict.adelete(self.cache_key)

    def save_data(self, data: Any, ex: Optional[int] = None) -> None:
        """
        Saves the Data
        """
        self.pdict.set(self.data_cache_key, data, ex = ex)

    async def asave_data(self, data: Any, ex: Optional[int] = None) -> None:
        """
        Saves the Data
        """
        await self.pdict.aset(self.data_cache_key, data, ex = ex)

    def load_data(self, default: Optional[Any] = None) -> Any:
        """
        Loads the Data
        """
        return self.pdict.get(self.data_cache_key, default = default)
    
    async def aload_data(self, default: Optional[Any] = None) -> Any:
        """
        Loads the Data
        """
        return await self.pdict.aget(self.data_cache_key, default = default)
    
    def delete_data(self) -> None:
        """
        Deletes the Data
        """
        self.pdict.delete(self.data_cache_key)
    
    async def adelete_data(self) -> None:
        """
        Deletes the Data
        """
        await self.pdict.adelete(self.data_cache_key)

    @classmethod
    def create_hash_key(cls, data: Any) -> str:
        """
        Creates a hash for the data
        """
        from ..utils.helpers import get_hashed_key
        return get_hashed_key(data)
    
    
    

