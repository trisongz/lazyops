import os
from lzl.logging import get_logger, change_logger_level, null_logger
# from lazyops.utils.logs import get_logger, change_logger_level, null_logger

# to prevent recursive imports, we'll just use os environ here
logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()
logger = get_logger(logger_level)
logger.set_module_name('lzl.io.file', 'file', is_relative = True)
