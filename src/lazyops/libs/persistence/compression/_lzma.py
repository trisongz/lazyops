from __future__ import annotations

"""
LZMA Compression
"""

import lzma
from .base import BaseCompression, logger
from typing import Optional

class LzmaCompression(BaseCompression):
    name: str = "lzma"
    compression_level: Optional[int] = 9

    def validate_compression_level(self):
        """
        Validates the compression level
        """
        assert self.compression_level in range(10), "Compression level must be between 0 and 9"

    def compress(self, data: bytes, level: Optional[int] = None, **kwargs) -> bytes:
        """
        Compresses the data
        """
        if level is None: level = self.compression_level
        _kwargs = self._compression_kwargs.copy()
        if kwargs: _kwargs.update(kwargs)
        return lzma.compress(data, preset = level, **_kwargs)

    def decompress(self, data: bytes, **kwargs) -> bytes:
        """
        Decompresses the data
        """
        _kwargs = self._decompression_kwargs.copy()
        if kwargs: _kwargs.update(kwargs)
        return lzma.decompress(data, **_kwargs)
    
    

