from __future__ import annotations

"""
Base Serializers
"""

import abc
import zlib
from lzl.logging import logger
from lzl.pool import ThreadPool
from lzl.types import BaseModel
from lzo.utils.hashing import create_object_hash, create_hash_from_args_and_kwargs, ObjT as ObjectValue, PyModelType as SchemaType
from .utils import (
    get_object_classname, 
    get_object_class, 
    register_object_class, 
    register_schema_mapping,
    SerializableObject,
    SerMode,
    serialize_object,
    deserialize_object,
)
from typing import Any, Optional, Union, Dict, TypeVar, Type, List, TYPE_CHECKING
from types import ModuleType


if TYPE_CHECKING:
    from ..compression import CompressionT


class BaseSerializer(abc.ABC):
    """
    The Base Serializer Class
    """
    name: Optional[str] = None
    encoding: Optional[str] = None
    binary: Optional[bool] = False
    compressor: Optional['CompressionT'] = None
    previous_compressor: Optional['CompressionT'] = None
    enforce_string_value: Optional[bool] = False
    enforce_byte_value: Optional[bool] = False
    ser_mode: Optional[SerMode] = 'auto'
    _is_ser: Optional[bool] = True

    def __init__(
        self,
        compression: Optional[str] = None,
        compression_level: Optional[int] = None,
        encoding: Optional[str] = None,
        raise_errors: bool = False,
        enforce_string_value: Optional[bool] = None,
        enforce_byte_value: Optional[bool] = None,
        ser_mode: Optional[SerMode] = None,
        deprecated_compression: Optional[str] = None,
        schema_map: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """
        Initializes the serializer
        """
        if compression is not None or compression_level is not None:
            from ..compression import get_compression
            compression_kwargs = kwargs.pop("compression_kwargs", None)
            decompression_kwargs = kwargs.pop("decompression_kwargs", None)
            deprecated_compression = kwargs.pop("deprecated_compression", None)
            self.compressor = get_compression(
                compression, 
                compression_level = compression_level, 
                compression_kwargs = compression_kwargs, 
                decompression_kwargs = decompression_kwargs,
            )
            if deprecated_compression is not None and deprecated_compression != compression:
                self.previous_compressor = get_compression(deprecated_compression)
        if encoding is not None: self.encoding = encoding
        if enforce_string_value is not None: self.enforce_string_value = enforce_string_value
        if enforce_byte_value is not None: self.enforce_byte_value = enforce_byte_value
        if ser_mode is not None: self.ser_mode = ser_mode
        self.schema_map = schema_map
        self.raise_errors = raise_errors
        self._kwargs = kwargs

    @property
    def compression_enabled(self) -> bool:
        """
        Returns if compression is enabled
        """
        return self.compressor is not None
    
    @property
    def compression_level(self) -> Optional[int]:
        """
        Returns the compression level
        """
        return self.compressor.compression_level if self.compressor is not None else None
    
    @property
    def is_binary(self) -> bool:
        """
        Returns whether the serializer output is binary
        """
        if self.enforce_byte_value: return True
        if self.enforce_string_value: return False
        return self.binary or self.compression_enabled

    @staticmethod
    def fetch_object_classname(obj: ObjectValue, is_type: Optional[bool] = False) -> str:
        """
        Fetches the object classname
        """
        return get_object_classname(obj, is_type = is_type)
    
    @staticmethod
    def fetch_object_class(name: str) -> Type[SerializableObject]:
        """
        Gets the object class
        """
        return get_object_class(name)
    
    @staticmethod
    def register_schema(schema: Dict[str, str]) -> None:
        """
        Registers the schema
        """
        register_schema_mapping(schema)

    @staticmethod
    def register_object_class(obj: SerializableObject, is_type: Optional[bool] = False) -> str:
        """
        Registers the object class
        """
        return register_object_class(obj, is_type = is_type)
    
    def create_hash(self, obj: ObjectValue) -> str:
        """
        Creates a hash for the object
        """
        return create_object_hash(obj)

    async def acreate_hash(self, obj: ObjectValue) -> str:
        """
        Creates a hash for the object asynchronously
        """
        return await ThreadPool.run_async(self.create_hash, obj)
    
    def coerce_output_value(self, value: Union[str, bytes], **kwargs) -> Union[str, bytes]:
        """
        Coerces the output value
        """
        if self.enforce_string_value and isinstance(value, bytes): value = value.decode(self.encoding)
        elif self.enforce_byte_value and not isinstance(value, bytes): value = value.encode(self.encoding)
        return value
    
    def compress_value(self, value: Union[str, bytes], **kwargs) -> Union[str, bytes]:
        """
        Compresses the value
        """
        if self.compression_enabled:
            if isinstance(value, str): value = value.encode(self.encoding)
            return self.coerce_output_value(self.compressor.compress(value))
        return self.coerce_output_value(value)
    
    def deprecated_decompress_value(self, value: Union[str, bytes], **kwargs) -> Optional[Union[str, bytes]]:
        """
        Attempts to decompress the value using the deprecated compressor
        """
        e = None
        attempt_msg = f"{self.name}"
        if self.previous_compressor is not None:
            try:
                return self.previous_compressor.decompress(value)
            except Exception as e:
                attempt_msg += f"-> {self.previous_compressor.name}"
        try:
            return zlib.decompress(value)
        except Exception as e:
            attempt_msg += " -> ZLib"
            logger.trace(f'[{attempt_msg}] Error in Decompression: {str(value)[:100]}', e)
            if self.raise_errors: raise e
            return None
        
    
    def decompress_value(self, value: Union[str, bytes], **kwargs) -> Union[str, bytes]:
        # sourcery skip: extract-duplicate-method
        """
        Decompresses the value
        """
        if not self.compression_enabled: return value
        try:
            value = self.compressor.decompress(value, **kwargs)
        except Exception as e:
            if self.previous_compressor is not None:
                value = self.deprecated_decompress_value(value, **kwargs)
        if value is not None and not self.binary: value = value.decode(self.encoding)
        return value

    def encode_value(self, value: ObjectValue, **kwargs) -> Union[str, bytes]:
        """
        Encodes the value
        """
        raise NotImplementedError
    
    def encode(self, value: ObjectValue, **kwargs) -> Union[str, bytes]:
        """
        Encodes the value
        """
        return self.compress_value(self.encode_value(value, **kwargs))
    
    async def aencode(self, value: ObjectValue, **kwargs) -> Union[str, bytes]:
        """
        Encodes the value asynchronously
        """
        return await ThreadPool.run_async(self.encode, value, **kwargs)
    
    def decode_value(self, value: Union[str, bytes], **kwargs) -> ObjectValue:
        """
        Decodes the value
        """
        raise NotImplementedError
    
    def decode(self, value: Union[str, bytes], **kwargs) -> ObjectValue:
        """
        Decodes the value
        """
        return self.decode_value(self.decompress_value(value, **kwargs), **kwargs)
    
    async def adecode(self, value: Union[str, bytes], **kwargs) -> ObjectValue:
        """
        Decodes the value asynchronously
        """
        return await ThreadPool.run_async(self.decode, value, **kwargs)
    
    def dumps(self, value: ObjectValue, **kwargs) -> Union[str, bytes]:
        # sourcery skip: class-extract-method
        """
        Dumps the value
        """
        try:
            return self.encode(value, **kwargs)
        except Exception as e:
            logger.trace(f'[{self.name}] Error in Encoding: {str(value)[:500]}', e)
            if self.raise_errors: raise e
            return None
        
    async def adumps(self, value: ObjectValue, **kwargs) -> Union[str, bytes]:
        """
        Dumps the value asynchronously
        """
        return await ThreadPool.run_async(self.dumps, value, **kwargs)
    
    def loads(self, value: Union[str, bytes], **kwargs) -> ObjectValue:
        """
        Loads the value
        """
        try:
            return self.decode(value, **kwargs)
        except Exception as e:
            logger.trace(f'[{self.name}] Error in Decoding: {str(value)[:500]}', e)
            if self.raise_errors: raise e
            return None
        
    async def aloads(self, value: Union[str, bytes], **kwargs) -> ObjectValue:
        """
        Loads the value asynchronously
        """
        return await ThreadPool.run_async(self.loads, value, **kwargs)
    
    
    def serialize_obj(self, obj: SerializableObject, mode: Optional[SerMode] = None, **kwargs) -> Union[str, bytes]:
        """
        Serializes the object
        """
        mode = mode or self.ser_mode
        return serialize_object(obj, mode = mode, **kwargs)
    
    def deserialize_obj(
        self, 
        obj: Union[Dict[str, Any], List[Dict[str, Any]], Any], 
        schema_map: Optional[Dict[str, str]] = None, 
        allow_failed_import: Optional[bool] = False,
        **kwargs
    ) -> SerializableObject:
        """
        Deserializes the object
        """
        return deserialize_object(obj, schema_map = schema_map or self.schema_map, allow_failed_import = allow_failed_import, **kwargs)


class BinaryBaseSerializer(BaseSerializer):

    binary: Optional[bool] = True

