
"""
Import Handler for `fileio`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    from fileio import File, FileLike
    _fileio_available = True
except ImportError:
    from os import PathLike
    File = object
    FileLike = PathLike
    _fileio_available = False

def resolve_fileio(
    required: bool = False,
):
    """
    Ensures that `fileio` is available
    """
    global fileio, _fileio_available
    if not _fileio_available:
        resolve_missing('fileio', required = required)
        import fileio
        _fileio_available = True


def require_fileio(
    required: bool = False,
):
    """
    Wrapper for `resolve_fileio` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_fileio, 
            func = func, 
            required = required
        )
    return decorator