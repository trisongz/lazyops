"""
ZLib Compress
"""

import zlib
from .base import BaseCompress
from typing import Union

class ZLibCompress(BaseCompress):

    @classmethod
    def compress(cls, data: Union[str, bytes], encoding: str = 'utf-8', **kwargs) -> bytes:
        """
        ZLib Compress
        """
        if isinstance(data, str): data = data.encode(encoding)
        return zlib.compress(data)

    @classmethod
    def decompress(cls, data: Union[str, bytes], encoding: str = 'utf-8', **kwargs) -> bytes:
        """
        ZLib Decompress
        """
        if isinstance(data, str): data = data.encode(encoding = encoding)
        return zlib.decompress(data)

