
"""
Import Handler for slack_sdk
"""

from lazyops.utils.imports import resolve_missing, require_missing_wrapper

try:
    import slack_sdk
    _slack_sdk_available = True
except ImportError:
    slack_sdk = object
    _slack_sdk_available = False

def resolve_slack_sdk(
    required: bool = False,
):
    """
    Ensures that `slack_sdk` is available
    """
    global slack_sdk, _slack_sdk_available
    if not _slack_sdk_available:
        resolve_missing('slack_sdk', required = required)
        import slack_sdk
        _slack_sdk_available = True
        globals()['slack_sdk'] = slack_sdk


def require_slack_sdk(
    required: bool = False,
):
    """
    Wrapper for `resolve_slack_sdk` that can be used as a decorator
    """
    def decorator(func):
        return require_missing_wrapper(
            resolver = resolve_slack_sdk, 
            func = func, 
            required = required
        )
    return decorator