"""Logging helpers specific to the :mod:`lzl.api.aiohttpx` package."""

import logging
import os
import typing as t

from lzl.logging import Logger, NullLogger, change_logger_level, get_logger, null_logger

__all__ = [
    "logger",
    "mute_httpx_logger",
    "change_logger_level",
    "null_logger",
    "Logger",
    "NullLogger",
]

# Keep module-level logger creation simple to avoid recursive import issues.
logger_level = os.getenv('LOGGER_LEVEL', 'INFO').upper()
logger: Logger = get_logger(logger_level)
logger.set_module_name('lzl.api.aiohttpx', 'aiohttpx', is_relative=True)

_muted_httpx: t.Optional[bool] = None


def mute_httpx_logger() -> None:
    """Ensure the upstream ``httpx`` logger only logs warnings or higher once."""

    global _muted_httpx
    if _muted_httpx is not None:
        return
    _muted_httpx = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
