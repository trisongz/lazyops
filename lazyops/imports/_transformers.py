
"""
Import Handler for `transformers`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import transformers
    _transformers_available = True
except ImportError:
    transformers = object
    _transformers_available = False

def resolve_transformers(
    required: bool = False,
    version: str = None,
):
    """
    Ensures that `transformers` is available
    """
    global transformers, _transformers_available
    if not _transformers_available:
        pkg = 'transformers'
        if version is not None:
            pkg += f'=={version}'
        resolve_missing(pkg, required = required)
        import transformers
        _transformers_available = True


def require_transformers(
    required: bool = False,
    version: str = None,
):
    """
    Wrapper for `resolve_transformers` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_transformers, 
            func = func, 
            required = required,
            version = version
        )
    return decorator