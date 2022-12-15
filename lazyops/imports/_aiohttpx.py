
"""
Import Handler for aiohttpx
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import aiohttpx
    _aiohttpx_available = True
except ImportError:
    aiohttpx = object
    _aiohttpx_available = False

def resolve_aiohttpx(
    required: bool = False,
):
    """
    Ensures that `aiohttpx` is available
    """
    global aiohttpx, _aiohttpx_available
    if not _aiohttpx_available:
        resolve_missing('aiohttpx', required = required)
        import aiohttpx
        _aiohttpx_available = True


def require_aiohttpx(
    required: bool = False,
):
    """
    Wrapper for `resolve_aiohttpx` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_aiohttpx, 
            func = func, 
            required = required
        )
    return decorator