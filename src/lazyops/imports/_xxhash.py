
"""
Import Handler for `xxhash`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import xxhash
    _xxhash_available = True
except ImportError:
    xxhash = object
    _xxhash_available = False

def resolve_xxhash(
    required: bool = False,
):
    """
    Ensures that `xxhash` is available
    """
    global xxhash, _xxhash_available
    if not _xxhash_available:
        resolve_missing('xxhash', required = required)
        import xxhash
        _xxhash_available = True
        globals()['xxhash'] = xxhash


def require_xxhash(
    required: bool = False,
):
    """
    Wrapper for `resolve_xxhash` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_xxhash, 
            func = func, 
            required = required
        )
    return decorator