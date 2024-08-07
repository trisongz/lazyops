
"""
Import Handler for `pycryptodome`
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import Crypto
    _pycryptodome_available = True
except ImportError:
    Crypto = object
    _pycryptodome_available = False

def resolve_pycryptodome(
    required: bool = False,
):
    """
    Ensures that `pycryptodome` is available
    """
    global Crypto, _pycryptodome_available
    if not _pycryptodome_available:
        resolve_missing('pycryptodome', required = required)
        import Crypto
        _pycryptodome_available = True
        globals()['Crypto'] = Crypto


def require_pycryptodome(
    required: bool = False,
):
    """
    Wrapper for `resolve_pycryptodome` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_pycryptodome, 
            func = func, 
            required = required
        )
    return decorator