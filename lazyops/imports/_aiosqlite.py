
"""
Import Handler for `aiosqlite`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import aiosqlite
    _aiosqlite_available = True
except ImportError:
    aiosqlite = object
    _aiosqlite_available = False

def resolve_aiosqlite(
    required: bool = False,
):
    """
    Ensures that `aiosqlite` is available
    """
    global aiosqlite, _aiosqlite_available
    if not _aiosqlite_available:
        resolve_missing('aiosqlite', required = required)
        import aiosqlite
        _aiosqlite_available = True
        globals()['aiosqlite'] = aiosqlite


def require_aiosqlite(
    required: bool = False,
):
    """
    Wrapper for `resolve_aiosqlite` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_aiosqlite, 
            func = func, 
            required = required
        )
    return decorator