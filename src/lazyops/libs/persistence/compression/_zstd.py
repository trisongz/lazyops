from __future__ import annotations

"""
ZStd Compression
"""

from .base import BaseCompression, logger
from typing import Optional

try:
    import zstd
    _zstd_available = True
except ImportError:
    _zstd_available = False


class ZstdCompression(BaseCompression):
    name: str = "zstd"
    compression_level: Optional[int] = 3


    def validate_compression_level(self):
        """
        Validates the compression level
        """
        assert self.compression_level <= 0 or \
            self.compression_level in range(23), \
            "Compression level must be between 0 and 22 or -131072 to -1"


    def check_deps(self):
        """
        Checks for dependencies
        """
        if _zstd_available is False:
            logger.error("zstd is not available. Please install `zstd` or `pyzstd` to use zstd compression")
            raise ImportError("zstd is not available. Please install `zstd` or `pyzstd` to use zstd compression")

    def compress(self, data: bytes, level: Optional[int] = None, **kwargs) -> bytes:
        """
        Compresses the data
        """
        if level is None: level = self.compression_level
        return zstd.compress(data, level)

    def decompress(self, data: bytes, **kwargs) -> bytes:
        """
        Decompresses the data
        """
        return zstd.decompress(data)
    
    

