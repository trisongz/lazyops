import os
from lzl.logging import get_logger, change_logger_level, null_logger
logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()
logger = get_logger(logger_level)

logger.set_module_name('lzl.api.aioreq', 'aioreq', is_relative = True)
