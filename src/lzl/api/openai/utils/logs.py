import os
import logging
from lzl.logging import get_logger, change_logger_level, null_logger
# from lazyops.utils.logs import get_logger, change_logger_level, null_logger

# to prevent recursive imports, we'll just use os environ here
logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()
logger = get_logger(logger_level)

logger.set_module_name('lzl.api.openai', 'openai')

def configure_httpx_logger(level: int = logging.ERROR):
    """
    Helper Method to Disable HTTPX Logger
    """
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(level)
