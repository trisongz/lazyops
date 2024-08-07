from __future__ import annotations

import zlib
from .base import BaseCompression, logger
from typing import Optional

class ZlibCompression(BaseCompression):
    name: str = "zlib"
    compression_level: Optional[int] = -1

    def validate_compression_level(self):
        """
        Validates the compression level
        """
        assert self.compression_level == -1 or self.compression_level in range(10), "Compression level must be between 0 and 9 or -1"


    def compress(self, data: bytes, level: Optional[int] = None, **kwargs) -> bytes:
        """
        Compresses the data
        """
        if level is None: level = self.compression_level
        return zlib.compress(data, level = level)

    def decompress(self, data: bytes, **kwargs) -> bytes:
        """
        Decompresses the data
        """
        _kwargs = self._decompression_kwargs.copy()
        if kwargs: _kwargs.update(kwargs)
        return zlib.decompress(data, **_kwargs)
    


