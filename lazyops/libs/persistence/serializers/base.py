from __future__ import annotations

"""
Base Serializers
"""

import abc
import zlib
import hashlib
from lazyops.types import BaseModel
from lazyops.utils.logs import logger
# from lazyops.utils.pooler import ThreadPoolV2 as ThreadPooler
from lazyops.utils.pooler import ThreadPooler
from typing import Any, Optional, Union, Dict, TypeVar, TYPE_CHECKING

try:
    import xxhash
    _xxhash_available = True
except ImportError:
    _xxhash_available = False

if TYPE_CHECKING:
    from ..compression import CompressionT


SchemaType = TypeVar("SchemaType", bound=BaseModel)
ObjectValue = Union[SchemaType, Dict, Any]

def create_obj_hash(obj: ObjectValue) -> str:
    """
    Creates a hash for the object
    """
    if isinstance(obj, BaseModel) or hasattr(obj, "model_dump"):
        if _xxhash_available:
            return xxhash.xxh64(obj.model_dump_json()).hexdigest()
        return hashlib.sha256(obj.model_dump_json().encode()).hexdigest()
    if isinstance(obj, dict):
        if _xxhash_available:
            return xxhash.xxh64(str(obj).encode()).hexdigest()
        return hashlib.sha256(str(obj).encode()).hexdigest()
    if _xxhash_available:
        return xxhash.xxh64(str(obj).encode()).hexdigest()
    return hashlib.sha256(str(obj).encode()).hexdigest()

class BaseSerializer(abc.ABC):
    """
    The Base Serializer Class
    """
    name: Optional[str] = None
    encoding: Optional[str] = None
    binary: Optional[bool] = False
    compressor: Optional['CompressionT'] = None
    previous_compressor: Optional['CompressionT'] = None

    def __init__(
        self,
        compression: Optional[str] = None,
        compression_level: Optional[int] = None,
        encoding: Optional[str] = None,
        raise_errors: bool = False,
        enable_deprecation_support: bool = True,
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
        self.raise_errors = raise_errors
        self.enable_deprecation_support = enable_deprecation_support
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

    def fetch_object_classname(self, obj: ObjectValue) -> str:
        """
        Fetches the object classname
        """
        return f"{obj.__class__.__module__}.{obj.__class__.__name__}"
    
    def create_hash(self, obj: ObjectValue) -> str:
        """
        Creates a hash for the object
        """
        return create_obj_hash(obj)
    
    def compress_value(self, value: Union[str, bytes], **kwargs) -> Union[str, bytes]:
        """
        Compresses the value
        """
        if self.compression_enabled:
            if isinstance(value, str): value = value.encode(self.encoding)
            return self.compressor.compress(value)
        return value
    
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
            if self.enable_deprecation_support or self.previous_compressor is not None:
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
        return await ThreadPooler.run_async(self.encode, value, **kwargs)
    
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
        return await ThreadPooler.run_async(self.decode, value, **kwargs)
    
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
        return await ThreadPooler.run_async(self.dumps, value, **kwargs)
    
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
        return await ThreadPooler.run_async(self.loads, value, **kwargs)
    
    

class BinaryBaseSerializer(BaseSerializer):

    binary: Optional[bool] = True

