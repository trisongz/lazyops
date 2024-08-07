from __future__ import annotations

import os
import sys
import threading
import atexit as _atexit
from loguru import _defaults
from loguru._logger import Core as _Core
from .base import Logger, InterceptHandler
from .formatters import LoggerFormatter
from .null_logger import NullLogger
from .utils import extract_module_name
from .state import run_record_patching_hook, register_logger_module
from .static import REVERSE_LOGLEVEL_MAPPING
from typing import Dict, Union, Any, TYPE_CHECKING, Optional, List, Callable

if TYPE_CHECKING:
    from pydantic_settings import BaseSettings
    from logging import Handler as LoggingHandler
    from logging import LogRecord

_lock = threading.Lock()
_logger_contexts: Dict[str, Logger] = {}

def create_global_logger(
    name: Optional[str] = 'lzl',
    level: Union[str, int] = "INFO",
    format: Optional[Callable] = None,
    filter: Optional[Callable] = None,
    handlers: Optional[List['LoggingHandler']] = None,
    settings: Optional['BaseSettings'] = None,
    **kwargs,
) -> Logger:
    """
    Creates the global logger
    """
    global _logger_contexts

    # < 0.7.0
    try:
        _logger = Logger(
            core=_Core(),
            exception=None,
            depth=0,
            record=False,
            lazy=False,
            colors=True,
            raw=False,
            capture=True,
            patcher=None,
            extra={},
        )
    # >= 0.7.0
    except Exception as e:
        _logger = Logger(
            core=_Core(),
            exception=None,
            depth=0,
            record=False,
            lazy=False,
            colors=False,
            raw=False,
            capture=True,
            patchers=[run_record_patching_hook],
            extra={},
        )

    _logger.name = 'lzl'
    _logger.is_global = True
    dev_level = _logger.level(name='DEV', no=19, color="<blue>", icon="@")

    if _defaults.LOGURU_AUTOINIT and sys.stderr: _logger.add(sys.stderr)
    _atexit.register(_logger.remove)

    _logger.remove()
    _logger.add_if_condition('dev', _logger._is_dev_condition)
    import logging
    logging.basicConfig(
        handlers = handlers or [InterceptHandler()],  level = 0
    )

    _logger.add(
        sys.stdout,
        enqueue = True,
        backtrace = True,
        colorize = True,
        level = level,
        format = format if format is not None else LoggerFormatter.default_formatter,
        filter = filter if filter is not None else _logger._filter,
        **kwargs,
    )
    if settings: _logger.settings = settings
    _logger_contexts[name] = _logger
    return _logger


def create_default_logger(
    name: Optional[str] = None,
    level: Union[str, int] = "INFO",
    format: Optional[Callable] = None,
    filter: Optional[Callable] = None,
    handlers: Optional[List['LoggingHandler']] = None,
    settings: Optional['BaseSettings'] = None,
    **kwargs,
) -> Logger:
    """
    Creates a default logger
    """
    global _logger_contexts
    if name:
        if name.upper() in REVERSE_LOGLEVEL_MAPPING:
            # If name is a level, then set level to name
            level = name
            name = None
        else:
            name = extract_module_name(name)
            
    if name is None: name = 'lzl'
    if name in _logger_contexts:
        return _logger_contexts[name]
    
    with _lock:
        if name == 'lzl':
            return create_global_logger(
                name = name,
                level = level,
                format = format,
                filter = filter,
                handlers = handlers,
                settings = settings,
            )
        
        if isinstance(level, str): level = level.upper()
        _logger = _logger_contexts['lzl']

        if name and format is not None:
            # Add a new handler
            def _filter_func(record: 'LogRecord') -> bool:
                """
                Filter out messages from other modules
                """
                return extract_module_name(record.name) == name
            
            _logger.add(
                sys.stdout,
                enqueue = True,
                backtrace = True,
                colorize = True,
                level = level,
                format = format,
                filter = _filter_func,
                **kwargs,
            )
            return _logger

        *options, extra = _logger._options
        new_logger = Logger(_logger._core, *options, {**extra})
        if name: 
            _logger_contexts[name] = new_logger
            new_logger.name = name
            register_logger_module(name)

        if settings: new_logger.settings = settings
        # if _is_global_logger: new_logger.is_global = True
        return new_logger


def change_logger_level(
    name: Optional[str] = None,
    level: Union[str, int] = 'INFO',
    verbose: bool = False,
    **kwargs,
):
    """
    Change the logger level for a specific logger

    args:
        level: str = 'INFO'
            The level to change the logger to
        verbose: bool = False
            Whether to print the change to the logger
    """
    global logger, logger_level
    if isinstance(level, str): level = level.upper()
    # Skip if the level is the same
    if level == logger_level: return
    name = name or 'lzl'
    name = name.split('.')[0]
    logger_level = level
    if name != 'lzl':
        __logger = get_logger(name, logger_level, **kwargs)
    else:
        __logger = logger
    if verbose: __logger.info(f"[{name}] Changing logger level from {logger_level} -> {level}")
    __logger._core.min_level = float(REVERSE_LOGLEVEL_MAPPING[logger_level.upper()])


if os.getenv('LOGGING_DEBUG_ENABLED', os.getenv('DEBUG_ENABLED')) == 'True':
    logger_level = 'DEBUG'
else:
    logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()


get_logger = create_default_logger
logger = create_default_logger('lzl', level = logger_level)
default_logger = logger
null_logger = NullLogger(name = 'null_logger')
