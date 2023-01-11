
"""
Import Handler for backoff
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import backoff
    _backoff_available = True
except ImportError:
    backoff = object
    _backoff_available = False

def resolve_backoff(
    required: bool = False,
):
    """
    Ensures that `backoff` is available
    """
    global backoff, _backoff_available
    if not _backoff_available:
        resolve_missing('backoff', required = required)
        import backoff
        _backoff_available = True


def require_backoff(
    required: bool = False,
):
    """
    Wrapper for `resolve_backoff` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_backoff, 
            func = func, 
            required = required
        )
    return decorator