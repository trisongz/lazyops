from __future__ import annotations

"""
Base Compression Classes
"""

import abc

from lazyops.utils.logs import logger
# from lazyops.utils.pooler import ThreadPoolV2 as ThreadPooler
from lazyops.utils.pooler import ThreadPooler
from typing import Any, Optional, Union, Dict, TypeVar


class BaseCompression(abc.ABC):
    """
    The Base Compression Class
    """
    name: Optional[str] = None
    compression_level: Optional[int] = None
    encoding: Optional[str] = None

    def __init__(
        self,    
        compression_level: Optional[int] = None,
        encoding: Optional[str] = None,
        raise_errors: bool = False,
        compression_kwargs: Optional[Dict[str, Any]] = None,
        decompression_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initializes the serializer
        """
        if compression_level is not None:
            self.compression_level = compression_level
        if encoding is not None:
            self.encoding = encoding
        self.raise_errors = raise_errors
        self._compression_kwargs = compression_kwargs or {}
        self._decompression_kwargs = decompression_kwargs or {}
        self._kwargs = kwargs
        self.check_deps()
        self.validate_compression_level()

    def validate_compression_level(self):
        """
        Validates the compression level
        """
        pass

    def check_deps(self):
        """
        Checks for dependencies
        """
        pass

    def compress(self, data: Union[str, bytes], level: Optional[int] = None, **kwargs) -> bytes:
        """
        Base Compress
        """
        raise NotImplementedError()
    
    def decompress(self, data: Union[str, bytes], **kwargs) -> Union[str, bytes]:
        """
        Base Decompress
        """
        raise NotImplementedError()
    
    async def acompress(self, data: Union[str, bytes], level: Optional[int] = None, **kwargs) -> bytes:
        """
        Base Compress
        """
        return await ThreadPooler.run_async(self.compress, data, level = level, **kwargs)
    
    async def adecompress(self, data: Union[str, bytes], **kwargs) -> Union[str, bytes]:
        """
        Base Decompress
        """
        return await ThreadPooler.run_async(self.decompress, data, **kwargs)


