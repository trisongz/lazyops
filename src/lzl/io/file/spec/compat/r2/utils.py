from lzl.io.file.utils import logger

# MPU seems to work > 150MB?
_debug_mode: bool = False

def _log(f, *args, verbose: bool = False, **kwargs):
    if _debug_mode or verbose:
        logger.info(f, *args, **kwargs)
    else:
        logger.debug(f, *args, **kwargs)

