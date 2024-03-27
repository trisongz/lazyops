
"""
Import Handler for gspread
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import gspread
    _gspread_available = True
except ImportError:
    gspread = object
    _gspread_available = False

def resolve_gspread(
    required: bool = False,
):
    """
    Ensures that `gspread` is available
    """
    global gspread, _gspread_available
    if not _gspread_available:
        resolve_missing('gspread', required = required)
        import gspread
        _gspread_available = True
        globals()['gspread'] = gspread


def require_gspread(
    required: bool = False,
):
    """
    Wrapper for `resolve_gspread` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_gspread, 
            func = func, 
            required = required
        )
    return decorator