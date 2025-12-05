from __future__ import annotations

"""Factory helpers for configuring LazyOps logging.

The underlying implementation remains untouched – the adjustments here make the
intent of each entry-point explicit for generated documentation and downstream
integrations.
"""

import atexit as _atexit
import os
import sys
import threading
import typing as t

from loguru import _defaults
from loguru._logger import Core as _Core

from .base import InterceptHandler, Logger
from .formatters import LoggerFormatter
from .null_logger import NullLogger
from .state import register_logger_module, run_record_patching_hook
from .static import REVERSE_LOGLEVEL_MAPPING
from .utils import extract_module_name

if t.TYPE_CHECKING:
    from pydantic_settings import BaseSettings
    from logging import Handler as LoggingHandler
    from logging import LogRecord

_lock = threading.Lock()
_logger_contexts: t.Dict[str, Logger] = {}
_DISABLE_QUEUE = os.getenv('LZL_DISABLE_LOGURU_QUEUE', '0') == '1'

__all__ = [
    "create_global_logger",
    "create_default_logger",
    "change_logger_level",
    "get_logger",
    "logger",
    "default_logger",
    "null_logger",
]

def create_global_logger(
    name: str | None = "lzl",
    level: str | int = "INFO",
    format: t.Callable[["LogRecord"], str] | None = None,
    filter: t.Callable[["LogRecord"], bool] | None = None,
    handlers: t.Sequence["LoggingHandler"] | None = None,
    settings: "BaseSettings" | None = None,
    **kwargs: t.Any,
) -> Logger:
    """Instantiate the shared global Loguru logger used across LazyOps.

    Args:
        name: Registry key for the logger instance.  Defaults to ``"lzl"``.
        level: Log level for newly attached handlers.  Accepts both string and
            numeric values recognised by Loguru.
        format: Optional callable used to format log records.
        filter: Optional predicate used to filter records.
        handlers: Additional :mod:`logging` handlers to bridge into Loguru.
        settings: Optional settings object attached to the logger for runtime
            reference.
        **kwargs: Additional keyword arguments forwarded to
            :meth:`loguru.Logger.add`.

    Returns:
        Logger: The configured Loguru logger instance.
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
        enqueue = not _DISABLE_QUEUE,
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
    name: str | None = None,
    level: str | int = "INFO",
    format: t.Callable[["LogRecord"], str] | None = None,
    filter: t.Callable[["LogRecord"], bool] | None = None,
    handlers: t.Sequence['LoggingHandler'] | None = None,
    settings: 'BaseSettings' | None = None,
    **kwargs: t.Any,
) -> Logger:
    """Return a named logger that proxies calls to the global instance.

    Args:
        name: Optional logger namespace.  If omitted the global logger is
            returned.
        level: Minimum log level once the logger is registered.
        format: Formatter applied when a dedicated handler is configured.
        filter: Optional filtering callable.
        handlers: Additional logging handlers to attach.
        settings: Optional settings object attached to the logger for runtime
            reference.
        **kwargs: Extra keyword arguments forwarded to the Loguru ``add`` call.

    Returns:
        Logger: Either the global logger or a namespaced proxy.
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
                enqueue = not _DISABLE_QUEUE,
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
    name: str | None = None,
    level: str | int = "INFO",
    verbose: bool = False,
    **kwargs: t.Any,
) -> None:
    """Update the minimum level for the global or named logger."""
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
