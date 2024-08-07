
"""
Import Handler for `magic`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import magic
    _magic_available = True
except ImportError:
    magic = object
    _magic_available = False

def resolve_magic(
    required: bool = False,
):
    """
    Ensures that `magic` is available
    """
    global magic, _magic_available
    if not _magic_available:
        resolve_missing('magic', 'python-magic', required = required)
        import magic
        _magic_available = True
        globals()['magic'] = magic


def require_magic(
    required: bool = False,
):
    """
    Wrapper for `resolve_magic` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_magic, 
            func = func, 
            required = required
        )
    return decorator