"""
Local Persistence Types
"""

import os
import json
import filelock
import binascii
from pathlib import Path, PurePath
from typing import TypeVar, Generic, Any, Dict, Optional, Union, Iterable, List, Type, TYPE_CHECKING
from lazyops.utils.helpers import  create_unique_id
from .base import BaseStatefulBackend, SchemaType, logger

try:
    from fileio import File, FileLike
except ImportError:
    File = Path
    FileLike = PurePath


if TYPE_CHECKING:
    from lazyops.types.models import BaseSettings


class LocalStatefulBackend(BaseStatefulBackend):
    """
    Implements a Local Stateful Backend
    """
    name: Optional[str] = "local"
    encoding: Optional[str] = "utf-8"

    def __init__(
        self,
        name: Optional[str] = None,
        file_path: Optional[File] = None,
        encoding: Optional[str] = None,

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
        if encoding is not None: self.encoding = encoding
        if file_path is None:
            if hasattr(self.settings, "data_dir"):
                file_path = self.settings.data_dir.joinpath(f"{self.name}.cache")
            else:
                file_path = Path(os.getcwd()).joinpath(f"{self.name}.cache")
        self.file_path = File(file_path)
        if self.file_path.is_dir():
            self.file_path = self.file_path.joinpath(f"{self.name}.cache")
        self.file_path.parent.mkdir(parents = True, exist_ok = True)
        self.file_lock_path = self.file_path.with_suffix(".lock")
        self.file_hash_path = self.file_path.with_suffix(".hash")
        self.file_lock = filelock.FileLock(lock_file = self.file_lock_path.as_posix(), thread_local = False)
        try:
            import simdjson
            self.parser = simdjson.Parser()
            self.cache: simdjson.SimValue = {}
        except ImportError:
            self.parser = None
            self.cache: Dict[str, Any] = {}

        if not self.file_path.exists():
            with self.file_lock:
                self.file_path.write_text('{}')
                self.file_hash = create_unique_id()
                self.file_hash_path.write_text(self.file_hash)
        else:
            self.cache = self.get_data()
            self.file_hash = self.file_hash_path.read_text()
    
    def encode_value(self, value: Union[Any, SchemaType], _raw: Optional[bool] = None, **kwargs) -> str:
        """
        Encodes a Value
        """
        if _raw: return value
        result = super().encode_value(value, **kwargs)
        return result.hex() if isinstance(result, bytes) else result
    
    def decode_value(self, value: str, _raw: Optional[bool] = None, **kwargs) -> Any:
        """
        Decodes a Value
        """
        if _raw: return value
        if self.serializer.binary or self.serializer.compression_enabled:
            value = binascii.unhexlify(value)
        return super().decode_value(value, **kwargs)
    
    def _precheck(self, **kwargs):
        """
        Precheck
        """
        self.sync()

    def get(self, key: str, default: Optional[Any] = None, _raw: Optional[bool] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the JSON
        """
        self.sync()
        if value := self.cache.get(self.get_key(key)):
            try:
                result = self.decode_value(value, _raw = _raw, **kwargs)
                return result if result is not None else default
            except Exception as e:
                logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {value}', colored = True)
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
    

    def set(self, key: str, value: Any, *args, _raw: Optional[bool] = None, **kwargs) -> None:
        """
        Sets a Value in the JSON
        """
        self.sync()
        self.cache[self.get_key(key)] = self.encode_value(value, _raw = _raw)
        self.write_data(self.cache)
        

    def set_batch(self, data: Dict[str, Any], *args, **kwargs) -> None:
        """
        Sets a Value in the JSON
        """
        self.sync()
        for key, value in data.items():
            self.cache[self.get_key(key)] = self.encode_value(value, **kwargs)
        self.write_data(self.cache)

    def delete(self, key: str, **kwargs) -> None:
        """
        Deletes a Value from the JSON
        """
        self.sync()
        _ = self.cache.pop(self.get_key(key), None)
        self.write_data(self.cache)
    
    def clear(self, *keys: str, **kwargs):
        """
        Clears the Cache
        """
        self.sync()
        if keys:
            for key in keys:
                self.cache.pop(self.get_key(key), None)
        else:
            self.cache = {}
        self.write_data(self.cache)


    def get_all_keys(self, exclude_base_key: Optional[bool] = False, **kwargs) -> List[str]:
        """
        Returns all the Keys
        """
        self.sync()
        keys = [
            key
            for key in self.cache.keys()
            if key.startswith(self.base_key)
        ] if self.base_key else list(self.cache.keys())
        if exclude_base_key:
            keys = [key.replace(f'{self.base_key}.', '') for key in keys]
        return keys

    def get_all_data(self, exclude_base_key: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """
        Loads all the Data
        """
        self.sync()
        all_keys = self.get_all_keys()
        data = {
            key: self.decode_value(value)
            for key, value in self.cache.items() if key in all_keys
        }
        if exclude_base_key:
            data = {key.replace(f'{self.base_key}.', ''): value for key, value in data.items()}
        return data
    
    def get_all_values(self, **kwargs) -> Iterable[Any]:
        """
        Returns all the Values
        """
        self.sync()
        all_keys = self.get_all_keys(**kwargs)
        return [
            self.decode_value(value, **kwargs)
            for key, value in self.cache.items() if key in all_keys
        ]    

    def contains(self, key: str, **kwargs) -> bool:
        """
        Returns True if the Cache contains the Key
        """
        self.sync()
        return key in self.get_all_keys(**kwargs)
    

    def iterate(self, **kwargs) -> Iterable[Any]:
        """
        Iterates over the Cache
        """
        self.sync()
        return iter(self.get_all_keys(**kwargs))


    """
    Primary Utility Methods
    """

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

    def get_data(self, **kwargs) -> Dict[str, Any]:
        """
        Returns the Data
        """
        with self.file_lock:
            if self.parser is None:
                return json.loads(self.file_path.read_text())
            return self.parser.parse(self.file_path.read_bytes(), recursive=True)
    
    async def aget_data(self, **kwargs) -> Dict[str, Any]:
        """
        Fetch the data
        """
        with self.file_lock:
            if self.parser is None:
                return json.loads(await self.file_path.async_read_text())
            return self.parser.parse(await self.file_path.async_read_bytes(), recursive=True)
        
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

    

    def incrby(self, key: str, amount: int = 1, **kwargs) -> int:
        # sourcery skip: class-extract-method
        """
        [int] Increments the value of the key by the given amount
        """
        existing = self.get(key, 0)
        value = existing + amount
        self.set(key, value)
        return value
    
    def incrbyfloat(self, key: str, amount: float = 1.0, **kwargs) -> float:
        """
        [float] Increments the value of the key by the given amount
        """
        existing = self.get(key, 0.0)
        value = existing + amount
        self.set(key, value)
        return value
    
    async def aincrby(self, key: str, amount: int = 1, **kwargs) -> int:
        """
        [int] Increments the value of the key by the given amount
        """
        existing = await self.aget(key, 0)
        value = existing + amount
        await self.aset(key, value)
        return value
    
    async def aincrbyfloat(self, key: str, amount: float = 1.0, **kwargs) -> float:
        """
        [float] Increments the value of the key by the given amount
        """
        existing = await self.aget(key, 0.0)
        value = existing + amount
        await self.aset(key, value)
        return value
    
    def decrby(self, key: str, amount: int = 1, **kwargs) -> int:
        """
        [int] Decrements the value of the key by the given amount
        """
        existing = self.get(key, 0)
        value = existing - amount
        self.set(key, value)
        return value
    
    def decrbyfloat(self, key: str, amount: float = 1.0, **kwargs) -> float:
        """
        [float] Decrements the value of the key by the given amount
        """
        existing = self.get(key, 0.0)
        value = existing - amount
        self.set(key, value)
        return value
    
    async def adecrby(self, key: str, amount: int = 1, **kwargs) -> int:
        """
        [int] Decrements the value of the key by the given amount
        """
        existing = await self.aget(key, 0)
        value = existing - amount
        await self.aset(key, value)
        return value
    
    async def adecrbyfloat(self, key: str, amount: float = 1.0, **kwargs) -> float:
        """
        [float] Decrements the value of the key by the given amount
        """
        existing = await self.aget(key, 0.0)
        value = existing - amount
        await self.aset(key, value)
        return value