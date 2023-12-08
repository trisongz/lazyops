
"""
Import Handler for `bs4`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import bs4
    _bs4_available = True
except ImportError:
    bs4 = object
    _bs4_available = False

def resolve_bs4(
    required: bool = False,
):
    """
    Ensures that `bs4` is available
    """
    global bs4, _bs4_available
    if not _bs4_available:
        resolve_missing('bs4', required = required)
        import bs4
        _bs4_available = True
        globals()['bs4'] = bs4


def require_bs4(
    required: bool = False,
):
    """
    Wrapper for `resolve_bs4` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_bs4, 
            func = func, 
            required = required
        )
    return decorator