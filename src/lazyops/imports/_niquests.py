
"""
Import Handler for niquests
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import niquests
    _niquests_available = True
except ImportError:
    niquests = object
    _niquests_available = False

def resolve_niquests(
    required: bool = False,
):
    """
    Ensures that `niquests` is available
    """
    global niquests, _niquests_available
    if not _niquests_available:
        resolve_missing('niquests', required = required)
        import niquests
        _niquests_available = True
        globals()['niquests'] = niquests


def require_niquests(
    required: bool = False,
):
    """
    Wrapper for `resolve_niquests` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_niquests, 
            func = func, 
            required = required
        )
    return decorator