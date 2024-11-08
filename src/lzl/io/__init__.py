from __future__ import annotations

"""
I/O Modules
"""

from typing import Any, Dict, Optional, Union, Type, TYPE_CHECKING
from .file import File, FileLike, PathLike

if TYPE_CHECKING:
    from .ser import (
        SerT, 
        JsonSerializer,
        PickleSerializer,
    )
    from .compression import CompressionT
    from .persistence import PersistentDict, TemporaryData