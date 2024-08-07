
"""
Import Handler for `aiofiles`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import aiofiles
    _aiofiles_available = True
except ImportError:
    aiofiles = object
    _aiofiles_available = False

def resolve_aiofiles(
    required: bool = False,
):
    """
    Ensures that `aiofiles` is available
    """
    global aiofiles, _aiofiles_available
    if not _aiofiles_available:
        resolve_missing('aiofiles', required = required)
        import aiofiles
        _aiofiles_available = True
        globals()['aiofiles'] = aiofiles


def require_aiofiles(
    required: bool = False,
):
    """
    Wrapper for `resolve_aiofiles` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_aiofiles, 
            func = func, 
            required = required
        )
    return decorator