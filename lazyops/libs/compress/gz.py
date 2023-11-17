"""
GZIP Compress
"""

import gzip
from .base import BaseCompress
from typing import Union

class GzipCompress(BaseCompress):

    @classmethod
    def compress(cls, data: Union[str, bytes], encoding: str = 'utf-8', **kwargs) -> bytes:
        """
        GZip Compress
        """
        if isinstance(data, str): data = data.encode(encoding)
        return gzip.compress(data)

    @classmethod
    def decompress(cls, data: Union[str, bytes], encoding: str = 'utf-8', **kwargs) -> bytes:
        """
        GZip Decompress
        """
        if isinstance(data, str): data = data.encode(encoding = encoding)
        return gzip.decompress(data)

