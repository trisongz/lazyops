
"""
Import Handler for aiokeydb
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

_min_version = 'v0.1.0'

try:
    import aiokeydb
    _aiokeydb_available = True
except ImportError:
    aiokeydb = object
    _aiokeydb_available = False

def resolve_aiokeydb(
    required: bool = False,
    version: str = _min_version,
):
    """
    Ensures that `aiokeydb` is available
    """
    global aiokeydb, _aiokeydb_available
    if not _aiokeydb_available:
        resolve_missing(f'aiokeydb=={version}', required = required)
        import aiokeydb
        _aiokeydb_available = True


def require_aiokeydb(
    required: bool = False,
    version: str = _min_version,
):
    """
    Wrapper for `resolve_aiokeydb` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_aiokeydb, 
            func = func, 
            required = required,
            version = version,
        )
    return decorator