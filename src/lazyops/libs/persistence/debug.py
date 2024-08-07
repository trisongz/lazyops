from lazyops.libs.logging import logger, null_logger, Logger

_DEBUG_MODE_ENABLED = False
_COMPONENT_DEBUG = {
    'main': False,
    'addons': False,
}

def get_autologger(name: str) -> Logger:
    """
    Returns the Autologger
    """
    if _DEBUG_MODE_ENABLED: return logger
    return logger if _COMPONENT_DEBUG.get(name, False) else null_logger