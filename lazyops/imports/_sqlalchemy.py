
"""
Import Handler for sqlalchemy
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import sqlalchemy
    _sqlalchemy_available = True
except ImportError:
    sqlalchemy = object
    _sqlalchemy_available = False

def resolve_sqlalchemy(
    required: bool = False,
):
    """
    Ensures that `sqlalchemy` is available
    """
    global sqlalchemy, _sqlalchemy_available
    if not _sqlalchemy_available:
        resolve_missing('sqlalchemy', required = required)
        import sqlalchemy
        _sqlalchemy_available = True
        globals()['sqlalchemy'] = sqlalchemy


def require_sqlalchemy(
    required: bool = False,
):
    """
    Wrapper for `resolve_sqlalchemy` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_sqlalchemy, 
            func = func, 
            required = required
        )
    return decorator