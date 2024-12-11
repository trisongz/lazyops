import os
import logging
from typing import Optional
from lzl.logging import get_logger, change_logger_level, null_logger, Logger, NullLogger

# to prevent recursive imports, we'll just use os environ here
logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()
logger = get_logger(logger_level)

logger.set_module_name('lzl.api.aiohttpx', 'aiohttpx', is_relative = True)

_muted_httpx: Optional[bool] = None


def mute_httpx_logger() -> None:
    """
    Mute the httpx logger.
    """
    global _muted_httpx
    if _muted_httpx is not None:
        return
    _muted_httpx = True
    logging.getLogger("httpx").setLevel(logging.WARNING)