"""
Compression Utilities
"""

from typing import Union
from .base import BaseCompress
from .gz import GzipCompress
from .lz import Lz4Compress
from .zb import ZLibCompress
from .ztd import ZStdCompress

CompressionT = Union[BaseCompress, GzipCompress]

class Compress:

    gzip = GzipCompress
    zstd = ZStdCompress
    zlib = ZLibCompress
    lz4 = Lz4Compress
    