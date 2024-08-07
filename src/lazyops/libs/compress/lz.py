"""
LZ4 Compress
"""

from .base import BaseCompress
from typing import Union

try:
    import lz4.frame
    _lz4_available = True
except ImportError:
    _lz4_available = False

def ensure_lz4_available():
    """
    Ensure LZ4 is available
    """
    global _lz4_available, lz4
    if _lz4_available is False: 
        from lazyops.utils.imports import resolve_missing
        resolve_missing('lz4', required = True)
        import lz4.frame
        _lz4_available = True
        globals()['lz4'] = lz4


class Lz4Compress(BaseCompress):


    @classmethod
    def compress(cls, data: Union[str, bytes], encoding: str = 'utf-8', **kwargs) -> bytes:
        """
        LZ4 Compress
        """
        ensure_lz4_available()
        if isinstance(data, str): data = data.encode(encoding)
        return lz4.frame.compress(data)

    @classmethod
    def decompress(cls, data: Union[str, bytes], encoding: str = 'utf-8', **kwargs) -> bytes:
        """
        LZ4 Decompress
        """
        ensure_lz4_available()
        if isinstance(data, str): data = data.encode(encoding = encoding)
        return lz4.frame.decompress(data)

