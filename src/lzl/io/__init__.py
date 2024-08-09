from __future__ import annotations

"""
I/O Modules
"""

from typing import Any, Dict, Optional, Union, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .ser import (
        SerT, 
    )
    from .compression import CompressionT