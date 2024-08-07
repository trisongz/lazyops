
"""
Import Handler for dateparser and pytz
"""


try:
    import dateparser
    import pytz
    _dateparser_available = True
except ImportError:
    dateparser = object
    pytz = object
    _dateparser_available = False

def resolve_dateparser(
    required: bool = False,
):
    """
    Ensures that `dateparser` is available
    """
    global dateparser, pytz, _dateparser_available
    if not _dateparser_available:
        from lazyops.utils.imports import resolve_missing
        resolve_missing('dateparser', required = required)
        import dateparser
        import pytz
        _dateparser_available = True
        globals()['dateparser'] = dateparser
        globals()['pytz'] = pytz


def require_dateparser(
    required: bool = False,
):
    """
    Wrapper for `resolve_dateparser` that can be used as a decorator
    """
    def decorator(func):
        from lazyops.utils.imports import require_missing_wrapper
        return require_missing_wrapper(
            resolver = resolve_dateparser, 
            func = func, 
            required = required
        )
    return decorator