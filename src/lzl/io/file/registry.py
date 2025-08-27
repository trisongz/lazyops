from __future__ import annotations

"""
FileIO Registry - Allows users to register different loaders
"""

import typing as t

if t.TYPE_CHECKING:
    from .main import FileLike

### File Extension to File Loader Mapping
# Maps file extensions to their respective file loaders
# .json -> JSONFileLoader

_ext_to_file_loader: t.Dict[str, t.Union[t.Callable[['FileLike'], None], t.Awaitable['FileLike', None]]] = {}


def register_loader(ext: str, loader: t.Union[t.Callable[['FileLike'], None], t.Awaitable['FileLike', None]], overwrite: t.Optional[bool] = None) -> None:
    """
    Registers a file loader for a specific file extension.
    """
    if not ext.startswith('.'): ext = '.' + ext
    if not overwrite and ext in _ext_to_file_loader:
        raise ValueError(f"Loader for extension '{ext}' is already registered.")
    _ext_to_file_loader[ext] = loader

def get_file_loader(ext: str) -> t.Union[t.Callable[['FileLike'], None], t.Awaitable['FileLike', None]]:
    """
    Returns the file loader for a specific file extension, if registered.
    """
    if not ext.startswith('.'): ext = '.' + ext
    if ext in _ext_to_file_loader:
        return _ext_to_file_loader[ext]
    raise ValueError(f"No loader registered for extension '{ext}'")