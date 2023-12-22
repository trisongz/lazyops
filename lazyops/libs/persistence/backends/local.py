"""
Local Persistence Types
"""

import os
import json
import copy
import filelock
import binascii
import contextlib
import collections.abc

from io import BytesIO
from pathlib import Path, PurePath
from pydantic import BaseModel
from abc import ABC, abstractmethod
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
        self.file_path.parent.mkdir(parents = True, exist_ok = True)
        self.file_lock_path = self.file_path.with_suffix(".lock")
        self.file_hash_path = self.file_path.with_suffix(".hash")
        self.file_lock = filelock.FileLock(lock_file = self.file_lock_path.as_posix(), thread_local = False)
        try:
            import simdjson
            self.parser = simdjson.Parser()
            self.cache: simdjson.SimValue = None
        except ImportError:
            self.parser = None
            self.cache: Dict[str, Any] = None

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

    def get_data(self) -> Dict[str, Any]:
        """
        Returns the Data
        """
        with self.file_lock:
            if self.parser is None:
                return json.loads(self.file_path.read_text())
            return self.parser.parse(self.file_path.read_bytes(), recursive=True)
    
    async def aget_data(self) -> Dict[str, Any]:
        """
        Fetch the data
        """
        with self.file_lock:
            if self.parser is None:
                return json.loads(await self.file_path.async_read_text())
            return self.parser.parse(await self.file_path.async_read_bytes(), recursive=True)
        
    def encode_value(self, value: Union[Any, SchemaType], **kwargs) -> str:
        """
        Encodes a Value
        """
        result = super().encode_value(value, **kwargs)
        return result.hex() if isinstance(result, bytes) else result
    
    def decode_value(self, value: str, **kwargs) -> Any:
        """
        Decodes a Value
        """
        if self.serializer.name == 'pickle' or self.serializer.compression_enabled:
            value = binascii.unhexlify(value)
        return super().decode_value(value, **kwargs)

    def get(self, key: str, default: Optional[Any] = None, **kwargs) -> Optional[Any]:
        """
        Gets a Value from the JSON
        """
        self.sync()
        if value := self.cache.get(self.get_key(key)):
            try:
                return self.decode_value(value, **kwargs) or default
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
    

    def set(self, key: str, value: Any, **kwargs) -> None:
        """
        Sets a Value in the JSON
        """
        self.sync()
        cache_data = copy.deepcopy(self.cache)
        cache_data[self.get_key(key)] = self.encode_value(value)
        self.write_data(cache_data)


            
            


    

        











