from __future__ import annotations


from .base import BaseCompression, logger
from typing import Optional

try:
    import lz4.frame
    _lz4_available = True
except ImportError:
    _lz4_available = False


class Lz4Compression(BaseCompression):
    name: str = "lz4"
    compression_level: Optional[int] = 4

    def check_deps(self):
        """
        Checks for dependencies
        """
        if _lz4_available is False:
            logger.error("lz4 is not available. Please install lz4 to use lz4 compression")
            raise ImportError("lz4 is not available. Please install lz4 to use lz4 compression")


    def validate_compression_level(self):
        """
        Validates the compression level
        """
        assert self.compression_level in range(17), "Compression level must be between 0 and 16"


    def compress(self, data: bytes, level: Optional[int] = None, **kwargs) -> bytes:
        """
        Compresses the data
        """
        if level is None: level = self.compression_level
        _kwargs = self._compression_kwargs.copy()
        if kwargs: _kwargs.update(kwargs)
        return lz4.frame.compress(data, compression_level = level, **_kwargs)

    def decompress(self, data: bytes, **kwargs) -> bytes:
        """
        Decompresses the data
        """
        _kwargs = self._decompression_kwargs.copy()
        if kwargs: _kwargs.update(kwargs)
        return lz4.frame.decompress(data, **_kwargs)
    
    

