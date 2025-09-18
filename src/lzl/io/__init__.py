from __future__ import annotations

"""High-level IO façade.

This module publicly re-exports the primary IO helpers used across LazyOps.
Keeping the concise surface area documented in a single place makes it easier
for downstream projects – and Mintlify generated documentation – to link to the
canonical entry points without needing to traverse the underlying package
structure.
"""

import typing as t

from .file import File, FileLike, PathLike

if t.TYPE_CHECKING:
    from .ser import (
        SerT, 
        JsonSerializer,
        PickleSerializer,
    )
    from .compression import CompressionT
    from .persistence import PersistentDict, TemporaryData

__all__ = ["File", "FileLike", "PathLike"]
