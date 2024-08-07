from .base import BaseCompression
from ._gzip import GzipCompression
from ._lz4 import Lz4Compression
from ._zlib import ZlibCompression
from ._zstd import ZstdCompression
from typing import Any, Dict, Optional, Union, Type

CompressionT = Union[GzipCompression, Lz4Compression, ZlibCompression, ZstdCompression, BaseCompression]

def get_compression(
    compression_type: Optional[str] = None,
    compression_level: Optional[int] = None,
    **kwargs
) -> CompressionT:
    """
    Returns a Compression
    """
    compression_type = compression_type or "lz4"
    if compression_type == "gzip":
        return GzipCompression(compression_level = compression_level, **kwargs)
    if compression_type == "lz4":
        return Lz4Compression(compression_level = compression_level, **kwargs)
    if compression_type == "zlib":
        return ZlibCompression(compression_level = compression_level, **kwargs)
    if compression_type == "zstd":
        return ZstdCompression(compression_level = compression_level, **kwargs)
    raise ValueError(f"Invalid Compression Type: {compression_type}")