from __future__ import annotations

"""
Standalone Logging Module that doesn't depend on any other modules
"""

import re
import os
import sys
import abc
import logging
import typing
import traceback
import warnings
import pprint
import atexit as _atexit
import functools
import threading
import contextlib
from enum import Enum

from loguru import _defaults
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from .static import DEFAULT_STATUS_COLORS, QUEUE_STATUS_COLORS, STATUS_COLOR, FALLBACK_STATUS_COLOR, DEFAULT_FUNCTION_COLOR, DEFAULT_CLASS_COLOR, RESET_COLOR, LOGLEVEL_MAPPING, REVERSE_LOGLEVEL_MAPPING, COLORED_MESSAGE_MAP
from .utils import format_item, format_message, get_logging_level
from .state import is_registered_logger_module, is_global_muted
from .formatters import LoggerFormatter
from .mixins import LoggingMixin
from typing import Type, Union, Optional, Any, List, Dict, Tuple, Callable, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .utils import MsgItem

# Use this section to filter out warnings from other modules
os.environ['TF_CPP_MIN_LOG_LEVEL'] = os.getenv('TF_CPP_MIN_LOG_LEVEL', '3')
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings("ignore", message = "Unclosed client session")

if TYPE_CHECKING:
    from pydantic_settings import BaseSettings


# Setup Default Logger
class Logger(_Logger, LoggingMixin):

    name: str = None
    settings: Type['BaseSettings'] = None
    conditions: Dict[str, Tuple[Union[Callable, bool], str]] = {}
    default_trace_depth: Optional[int] = None
    is_global: bool = False
    _colored_opts = None
    _current_level: Optional[str] = None

    @property
    def colored_opts(self):
        """
        Returns the colored options
        """
        if not self._colored_opts:
            (exception, depth, record, lazy, colors, raw, capture, patchers, extra) = self._options
            self._colored_opts = (exception, depth, record, lazy, True, raw, capture, patchers, extra)
        return self._colored_opts

    def _get_opts(self, colored: Optional[bool] = False, **kwargs):
        """
        Returns the options
        """
        return self.colored_opts if colored else self._options

    def get_log_mode(self, level: str = "info"):
        """
        Returns the log mode based on the level
        """
        return self.dev if level.upper() in {'DEV'} else getattr(self, level.lower())

    def add_if_condition(
        self, 
        name: str, 
        condition: Union[Callable, bool],
        level: Optional[Union[str, int]] = 'INFO',
    ):
        """
        Adds a condition to the logger
        """
        self.conditions[name] = (condition, self._get_level(level))
    
    def remove_if_condition(self, name: str):
        """
        Removes a condition from the logger
        """
        if name in self.conditions:
            del self.conditions[name]

    def _is_dev_condition(self, record: logging.LogRecord) -> bool:
        """
        Returns whether the dev condition is met
        """
        if not self.settings: return True
        if record.levelname == 'DEV':
            for key in {'api_dev_mode', 'debug_enabled'}:
                if (
                    hasattr(self.settings, key)
                    and getattr(self.settings, key) is False
                ):
                    return False
        return True

    def _filter_if(self, name: str, record: Optional[logging.LogRecord] = None, message: Optional[Any] = None, level: Optional[Union[str, int]] = None) -> Tuple[bool, str]:
        """
        Filters out messages based on conditions
        """
        if name in self.conditions:
            condition, clevel = self.conditions[name]
            if isinstance(condition, bool):
                return condition, clevel
            elif isinstance(condition, type(None)):
                return False, clevel
            elif isinstance(condition, Callable):
                return condition(record or message), clevel
        return True, (record.levelname if record else self._get_level(level or 'INFO'))
    
    def _filter_module_name(self, name: str) -> bool:
        """
        Filter based on module name

        - True if the module is not registered and is_global is False 
        - False if the module is registered and is_global is False
        """
        _is_registered = is_registered_logger_module(name)
        if self.is_global: 
            return _is_registered is not False
        return _is_registered is False


    def _filter(self, record: logging.LogRecord, name: Optional[str] = None) -> bool:
        """
        Filters out messages based on conditions

        - True if the message should be filtered out
        - False if the message should be logged
        """
        if self.check_silenced(record):
            return True
        if self._filter_module_name(record['name']): 
            return True
        
        if name is not None:
            return self._filter_if(name, record)[0]
        if not self.conditions: return False
        return not any(
            isinstance(value, bool)
            and value is False
            or not isinstance(value, bool)
            and isinstance(value, Callable)
            and value(record) is False
            for key, value in self.conditions.items()
        )

    def _filter_dev(self, record: logging.LogRecord, **kwargs):
        if not self.settings:
            return True
        if record.levelname == 'DEV':
            for key in {'api_dev_mode', 'debug_enabled'}:
                if (
                    hasattr(self.settings, key)
                    and getattr(self.settings, key) is False
                ):
                    return False
        return True
    
    def opt(
        self,
        *,
        exception=None,
        record=False,
        lazy=False,
        colors=False,
        raw=False,
        capture=True,
        depth=0,
        ansi=False
    ):
        """
        Return a new logger with the specified options changed.
        """
        if ansi: colors = True
        args = self._options[-2:]
        return type(self)(self._core, exception, depth, record, lazy, colors, raw, capture, *args)



    """
    Newly Added APIs
    """

    def _get_level(self, level: Union[str, int]) -> str:
        """
        Returns the log level
        """
        return get_logging_level(level)

    def _format_item(
        self,
        msg: 'MsgItem',
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        level: Optional[str] = None,
        _is_part: Optional[bool] = False,
    ) -> str:  # sourcery skip: extract-duplicate-method, low-code-quality, split-or-ifs
        """
        Formats an item
        """
        return format_item(msg, max_length = max_length, colored = colored, level = level, _is_part = _is_part)


    def _format_message(
        self, 
        message: 'MsgItem',
        *args,
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        level: Optional[str] = None,
        colored: Optional[bool] = False,
    ) -> str:
        """
        Formats the message

        "example |b|msg|e|"
        -> "example <blue>msg</><reset>"
        """
        return format_message(message, max_length = max_length, colored = colored, level = level, prefix = prefix, *args)
    
    def log_if(
        self, 
        name: str, 
        message: 'MsgItem',
        *args, 
        level: Optional[Union[str, int]] = None, 
        **kwargs
    ):  # noqa: N805
        """
        Log ``message.format(*args, **kwargs)`` with severity ``level`` if condition is met.
        """
        condition, clevel = self._filter_if(name, message = message, level = level)
        if condition:
            return self.log((level or clevel), message, *args, **kwargs)

    def log(
        self, 
        level: Union[str, int], 
        message: 'MsgItem',
        *args, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        hook: Optional[Union[Callable, List[Callable]]] = None,
        **kwargs
    ):  # noqa: N805
        """
        Log ``message.format(*args, **kwargs)`` with severity ``level``.
        """
        level = self._get_level(level)
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored, level = level)
        try:
            self._log(level, False, self._get_opts(colored = colored), message, args, kwargs)
        except TypeError:
            # Compatibility with < 0.6.0
            # level_id, static_level_no, from_decorator, options, message, args, kwargs
            static_log_no = REVERSE_LOGLEVEL_MAPPING.get(level, 20)
            self._log(level, static_log_no, False, self._get_opts(colored = colored), message, args, kwargs)
        self.run_logging_hooks(message, hook = hook)

    def info(
        self, 
        message: 'MsgItem',
        *args, 
        colored: Optional[bool] = None, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Union[Callable, List[Callable]]] = None,
        **kwargs
    ):  # noqa: N805
        """
        Log ``message.format(*args, **kwargs)`` with severity ``'INFO'``.
        """
        if colored is None and isinstance(message, str) and '|e|' in message: colored = True
        message = self._format_message(message, *args, prefix = prefix, max_length = max_length, colored = colored, level = 'INFO')
        if not is_global_muted():
            try:
                self._log("INFO", False, self._get_opts(colored = colored), message, args, kwargs)
            except TypeError:
                # Compatibility with < 0.6.0
                self._log("INFO", 20, False, self._get_opts(colored = colored), message, args, kwargs)
        self.run_logging_hooks(message, hook = hook)

    def success(
        self, 
        message: 'MsgItem', 
        *args, 
        colored: Optional[bool] = False, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Union[Callable, List[Callable]]] = None,
        **kwargs
    ):  # noqa: N805
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'SUCCESS'``."""
        message = self._format_message(message, *args, prefix = prefix, max_length = max_length, colored = colored, level = 'SUCCESS')
        if not is_global_muted():
            try:
                self._log("SUCCESS", False, self._get_opts(colored = colored), message, args, kwargs)
            except TypeError:
                # Compatibility with < 0.6.0
                self._log("SUCCESS", 20, False, self._get_opts(colored = colored), message, args, kwargs)
        self.run_logging_hooks(message, hook = hook)

    def warning(
        self, 
        message, 
        *args, 
        colored: Optional[bool] = False, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Union[Callable, List[Callable]]] = None,
        **kwargs
    ):  # noqa: N805
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'WARNING'``."""
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored, level = 'WARNING')
    
        try:
            self._log("WARNING", False, self._get_opts(colored = colored), message, args, kwargs)
        except TypeError:
            # Compatibility with < 0.6.0
            self._log("WARNING", 30, False, self._get_opts(colored = colored), message, args, kwargs)
        self.run_logging_hooks(message, hook = hook)

    def error(
        self,
        message: Any,
        *args,
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        hook: Optional[Union[Callable, List[Callable]]] = None,
        exc_info: Optional[bool] = False,
        **kwargs
    ) -> None:
        """
        Log ``message.format(*args, **kwargs)`` with severity ``'ERROR'``.
        """
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored, level = 'ERROR')
        if exc_info: message += f"\n{traceback.format_exc()}"

        try:
            self._log("ERROR", False, self._get_opts(colored = colored), message, args, kwargs)
        except TypeError:
            self._log("ERROR", 40, False, self._get_opts(colored = colored), message, args, kwargs)
        self.run_logging_hooks(message, hook = hook)

    def trace(
        self, 
        msg: 'MsgItem',
        error: Optional[Type[Exception]] = None, 
        level: str = "ERROR",
        limit: Optional[int] = None,
        chain: Optional[bool] = True,
        colored: Optional[bool] = False,
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Union[Callable, List[Callable]]] = None,
        **kwargs,
    ) -> None:
        """
        This method logs the traceback of an exception.

        :param error: The exception to log.
        """
        _depth = kwargs.pop('depth', None)
        if _depth is not None: limit = _depth
        _msg = msg if isinstance(msg, str) else self._format_message(msg, colored = colored, level = level, prefix = prefix, max_length = max_length)
        # pprint.pformat(msg)
        _msg += f"\n{traceback.format_exc(chain = chain, limit = limit)}"
        if error: _msg += f" - {error}"
        
        try:
            self._log(level, False, self._get_opts(colored = colored), _msg, (), {})
        except TypeError:
            static_log_no = REVERSE_LOGLEVEL_MAPPING.get(level, 40)
            self._log(level, static_log_no, False, self._get_opts(colored = colored), _msg, (), {})
        self.run_logging_hooks(_msg, hook = hook)

    def exception(
        self,
        message: 'MsgItem',
        *args,
        colored: Optional[bool] = False,
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Union[Callable, List[Callable]]] = None,
        **kwargs
    ):
        """
        Log ``message.format(*args, **kwargs)`` with severity ``'ERROR'``.
        """
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored, level = 'ERROR')
        super().exception(message, *args, **kwargs)
        self.run_logging_hooks(message, hook = hook)

    
    def __call__(self, message: 'MsgItem', *args, level: str = 'info', **kwargs):
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'INFO'``."""
        if isinstance(message, list):
            __message = "".join(f'- {item}\n' for item in message)
        elif isinstance(message, dict):
            __message = "".join(f'- {key}: {value}\n' for key, value in message.items())
        else:
            __message = str(message)
        _log = self.get_log_mode(level)
        _log(__message.strip(), *args, **kwargs)
    
    def _logcompat(
        self, level, from_decorator, options, message, args, kwargs
    ):
        """
        Compatible to < 0.6.0
        """
        try:
            self._log(level, from_decorator, options, message, args, kwargs)
        except TypeError:
            # Compatibility with < 0.6.0
            # level_id, static_level_no, from_decorator, options, message, args, kwargs
            static_log_no = REVERSE_LOGLEVEL_MAPPING.get(level, 20)
            self._log(level, static_log_no, from_decorator, options, message, args, kwargs)


    """
    Utilties
    """

    def change_logger_level(
        self,
        level: str,
    ):
        """
        Changes the logger level

        :TODO
        """
        return
        # self._core.configure(levels = [level])

    

class InterceptHandler(logging.Handler):
    loglevel_mapping = LOGLEVEL_MAPPING

    def emit(self, record):
        try:
            from .main import logger
        except ImportError:
            return
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = self.loglevel_mapping.get(record.levelno, 'DEBUG')
        # if "Unclosed client session" in record.message:
        #     print('Has unclosed client session')
        #     return
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        log = logger.bind(request_id=None)
        log.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


