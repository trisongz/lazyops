from .base import BaseCompression
from ._gzip import GzipCompression
from ._lz4 import Lz4Compression, _lz4_available
from ._zlib import ZlibCompression
from ._zstd import ZstdCompression, _zstd_available
from typing import Any, Dict, Optional, Union, Type


CompressionT = Union[GzipCompression, Lz4Compression, ZlibCompression, ZstdCompression, BaseCompression]


DEFAULT_COMPRESSION = (
    "zstd" if _zstd_available else \
    "lz4" if _lz4_available else \
    "zlib"
)

def get_default_compression() -> str:
    """
    Returns the default serializer
    """
    return DEFAULT_COMPRESSION

def set_default_compression(
    compression: str,
) -> None:
    """
    Sets the default compression

    :param compression: The compression to use
    """
    global DEFAULT_COMPRESSION
    DEFAULT_COMPRESSION = compression

_initialized_compressors: Dict[str, CompressionT] = {}

def get_compression(
    compression_type: Optional[str] = None,
    compression_level: Optional[int] = None,
    **kwargs
) -> CompressionT:
    """
    Returns a Compression
    """
    from lzo.utils.hashing import create_hash_from_args_and_kwargs
    if compression_type == 'auto': compression_type = None
    compression_type = compression_type or get_default_compression()
    comp_hash = create_hash_from_args_and_kwargs(compression_type, compression_level = compression_level, **kwargs)
    if comp_hash in _initialized_compressors:
        return _initialized_compressors[comp_hash]
    if compression_type == "gzip":
        new = GzipCompression(compression_level = compression_level, **kwargs)
    elif compression_type == "lz4":
        new = Lz4Compression(compression_level = compression_level, **kwargs)
    elif compression_type == "zlib":
        new = ZlibCompression(compression_level = compression_level, **kwargs)
    elif compression_type == "zstd":
        new = ZstdCompression(compression_level = compression_level, **kwargs)
    else: raise ValueError(f"Invalid Compression Type: {compression_type}")
    _initialized_compressors[comp_hash] = new
    return new