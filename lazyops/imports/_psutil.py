
"""
Import Handler for `psutil`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import psutil
    _psutil_available = True
except ImportError:
    psutil = object
    _psutil_available = False

def resolve_psutil(
    required: bool = False,
):
    """
    Ensures that `psutil` is available
    """
    global psutil, _psutil_available
    if not _psutil_available:
        resolve_missing('psutil', required = required)
        import psutil
        _psutil_available = True


def require_psutil(
    required: bool = False,
):
    """
    Wrapper for `resolve_psutil` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_psutil, 
            func = func, 
            required = required
        )
    return decorator