"""
ZStd Compress

Note - ZStd doesn't work as well as it returned some errors when decompressing.
"""

from .base import BaseCompress
from typing import Union

try:
    import zstd
    _zstd_available = True
except ImportError:
    _zstd_available = False

def ensure_zstd_available():
    """
    Ensure Zstd is available
    """
    global _zstd_available, zstd
    if _zstd_available is False: 
        from lazyops.utils.imports import resolve_missing
        resolve_missing('zstd', required = True)
        import zstd
        _zstd_available = True
        globals()['zstd'] = zstd


class ZStdCompress(BaseCompress):


    @classmethod
    def compress(cls, data: Union[str, bytes], encoding: str = 'utf-8', **kwargs) -> bytes:
        """
        ZStd Compress
        """
        ensure_zstd_available()
        if isinstance(data, str): data = data.encode(encoding)
        return zstd.compress(data)

    @classmethod
    def decompress(cls, data: Union[str, bytes], encoding: str = 'utf-8', **kwargs) -> bytes:
        """
        ZStd Decompress
        """
        ensure_zstd_available()
        if isinstance(data, str): data = data.encode(encoding = encoding)
        return zstd.decompress(data)

