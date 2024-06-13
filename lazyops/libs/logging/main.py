from __future__ import annotations

"""
Standalone Logging Module that doesn't depend on any other modules
"""


import re
import os
import sys
import logging
import typing
import traceback
import warnings
import pprint
import atexit as _atexit
import functools
import threading
from enum import Enum

from loguru import _defaults
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from typing import Type, Union, Optional, Any, List, Dict, Tuple, Callable, Set, TYPE_CHECKING

# Use this section to filter out warnings from other modules
os.environ['TF_CPP_MIN_LOG_LEVEL'] = os.getenv('TF_CPP_MIN_LOG_LEVEL', '3')
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings("ignore", message = "Unclosed client session")

if TYPE_CHECKING:
    from lazyops.types.models import BaseSettings




DEFAULT_STATUS_COLORS = {
    'debug': '<fg #D9ED92>',
    'info': '<fg #34A0A4>',
    'success': '<fg #52B69A>',
    'warning': '<fg #F48C06>',
    'error': '<fg #DC2F02>',
    'critical': '<fg #9D0208>',
}
    

QUEUE_STATUS_COLORS = {
    'new': '<fg #D9ED92>',
    'deferred': '<fg #B5E48C>',
    'queued': '<fg #99D98C>',
    'active': '<fg #76C893>',
    'complete': '<fg #52B69A>',

    # Error Colors
    'aborted': '<fg #FFBA08>',
    'failed': '<fg #9D0208>',

    # Other Colors
    'enqueue': '<fg #168AAD>',
    'finish': '<fg #52B69A>',
    'completed': '<fg #52B69A>',
    'error': '<fg #DC2F02>',
    'abort': '<fg #DC2F02>',

    'retry': '<fg #F48C06>',
    'scheduled': '<fg #34A0A4>',
    'reschedule': '<fg #34A0A4>',
    'startup': '<fg #168AAD>',
    'shutdown': '<fg #6A040F>',
    'process': '<fg #184E77>',
    'sweep': '<fg #B5E48C>',
    'stats': '<fg #B5E48C>',
    'dequeue': '<fg #168AAD>',

    'stuck': '<fg #DC2F02>',
}

STATUS_COLOR = QUEUE_STATUS_COLORS

FALLBACK_STATUS_COLOR = '<fg #99D98C>'

# DEFAULT_FUNCTION_COLOR = '<fg #457b9d>'
DEFAULT_FUNCTION_COLOR = '<fg #219ebc>'
DEFAULT_CLASS_COLOR = '<fg #a8dadc>'

RESET_COLOR = '\x1b[0m'

LOGLEVEL_MAPPING = {
    50: 'CRITICAL',
    40: 'ERROR',
    30: 'WARNING',
    20: 'INFO',
    19: 'DEV',
    10: 'DEBUG',
    5: 'CRITICAL',
    4: 'ERROR',
    3: 'WARNING',
    2: 'INFO',
    1: 'DEBUG',
    0: 'NOTSET',
}
REVERSE_LOGLEVEL_MAPPING = {v: k for k, v in LOGLEVEL_MAPPING.items()}

COLORED_MESSAGE_MAP = {
    '|bld|': '<bold>',
    '|reset|': '</>',
    '|eee|': '</></></>',
    '|em|': '<bold>',
    '|ee|': '</></>',
    '|lr|': '<light-red>',
    '|lb|': '<light-blue>',
    '|lm|': '<light-magenta>',
    '|lc|': '<light-cyan>',
    '|lw|': '<light-white>',
    # '|gr|': '<gray>',
    # '|gr|': "\033[90m",
    '|gr|': '<fg #808080>',
    '|lk|': '<light-black>',
    '|br|': "\x1b[31;1m", # Bold Red
    '|k|': '<black>',
    '|r|': '<red>',
    '|m|': '<magenta>',
    '|c|': '<cyan>',
    '|u|': '<underline>',
    '|i|': '<italic>',
    '|s|': '<strike>',
    '|e|': '</>',
    '|g|': '<green>',
    '|y|': '<yellow>',
    '|b|': '<blue>',
    '|w|': '<white>',
}


def find_and_format_seps(msg: str) -> str:
    """
    Find any |a,b,c| and format them |a||b||c|

    ex:
      |em,b,u| -> |em||b||u|
      |em,b| -> |em||b|
      
    """
    # v2
    for sep_match in re.finditer('\|\w+,(\w+,*)+\|', msg):
        s = sep_match.group()
        if len(s) >= 10: continue
        msg = msg.replace(s, "||".join(s.split(",")))
    return msg

def extract_module_name(name: str) -> str:
    """
    Extracts the module name from a name
    """
    return name.split('.')[0]



class NullLoggerV1(logging.Logger):
    """
    A logger that does nothing except pass through the log calls to hooks
    """

    def info(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def critical(self, *args, **kwargs): pass
    def exception(self, *args, **kwargs): pass
    def log(self, *args, **kwargs): pass
    def trace(self, *args, **kwargs): pass
    def success(self, *args, **kwargs): pass



class NullLogger(logging.Logger):
    """
    A logger that does nothing except pass through the log calls to hooks
    """

    def _format_item(
        self,
        msg: Any,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        level: Optional[str] = None,
        _is_part: Optional[bool] = False,
    ) -> str:  # sourcery skip: extract-duplicate-method, low-code-quality, split-or-ifs
        """
        Formats an item
        """
        # Primitive Types
        if isinstance(msg, str): return msg[:max_length] if max_length else msg
        if isinstance(msg, (float, int, bool, type(None))): return str(msg)[:max_length] if max_length else str(msg)
        if isinstance(msg, (list, set)):
            _msg = str(msg) if _is_part else "\n" + "".join(f'- {item}\n' for item in msg)
            return _msg[:max_length] if max_length else _msg
        
        prefix, suffix = '', ''
        if colored:
            prefix = '|g|'
            if level:
                level = level.lower()
                prefix = DEFAULT_STATUS_COLORS.get(level, '|g|')
            suffix = '|e|'

        if isinstance(msg, dict):
            _msg = "\n"
            for key, value in msg.items():
                _value = f'{value}'
                if max_length and len(_value) > max_length:
                    _value = f'{_value[:max_length]}...'
                _msg += f'- {prefix}{key}{suffix}: {_value}\n'
            return _msg.rstrip()
        
        if isinstance(msg, tuple):
            _msg = "".join(f'- {prefix}{key}{suffix}: {self._format_item(value, max_length = max_length, colored = colored, level = level,  _is_part = True)}\n' for key, value in zip(msg[0], msg[1]))
            return _msg[:max_length] if max_length else _msg

        # Complex Types
        if (hasattr(msg, 'dict') and hasattr(msg, 'Config')) or hasattr(msg, 'fields'):
            # Likely Pydantic Model
            _msg = f'{prefix}[{msg.__class__.__name__}]{suffix}'
            fields = msg.fields.keys() if hasattr(msg, 'fields') else msg.__fields__.keys()
            for field in fields:
                field_str = f'{prefix}{field}{suffix}'
                val_s = f'\n  {field_str}: {getattr(msg, field)!r}'
                if max_length is not None and len(val_s) > max_length:
                    val_s = f'{val_s[:max_length]}...'
                _msg += val_s
            return _msg
            # return self._format_item(msg.dict(), max_length = max_length, colored = colored, _is_part = _is_part)
        
        if hasattr(msg, 'model_dump'):
            return self._format_item(msg.model_dump(mode = 'json'), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

        if hasattr(msg, 'dict'):
            return self._format_item(msg.dict(), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

        if hasattr(msg, 'json'):
            return self._format_item(msg.json(), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

        if hasattr(msg, '__dict__'):
            return self._format_item(msg.__dict__, max_length = max_length, colored = colored, level = level, _is_part = _is_part)
        
        return str(msg)[:max_length] if max_length else str(msg)


    def _format_message(
        self, 
        message: Any, 
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
        _message = ""
        if prefix: 
            if colored and '|' not in prefix: 
                base_color = '|g|'
                if level:
                    level = level.lower()
                    base_color = DEFAULT_STATUS_COLORS.get(level, '|g|')
                prefix = f'{base_color}{prefix}|e|'
            _message += f'[{prefix}] '
        _message += self._format_item(message, max_length = max_length, colored = colored, level = level)
        if args:
            for arg in args:
                _message += "\n"
                _message += self._format_item(arg, max_length = max_length, colored = colored, level = level)
        if colored:
            # Add escape characters to prevent errors
            _message = _message.replace("<fg", ">|fg")
            _message = _message.replace("<", "\</")
            _message = find_and_format_seps(_message)
            # print(_message)
            for key, value in COLORED_MESSAGE_MAP.items():
                _message = _message.replace(key, value)
            _message = _message.replace(">|fg", "<fg")
            _message = _message.replace("\</", "\<")
            _message += RESET_COLOR
        return _message
    
    def _get_level(self, level: Union[str, int]) -> str:
        """
        Returns the log level
        """
        if isinstance(level, str): level = level.upper()
        elif isinstance(level, int): level = LOGLEVEL_MAPPING.get(level, 'INFO')
        return level
    
    def log(
        self, 
        level: Union[str, int], 
        message: Any, 
        *args, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        hook: Optional[Callable] = None,
        **kwargs
    ):  # noqa: N805
        """
        Log ``message.format(*args, **kwargs)`` with severity ``level``.
        """
        if not hook: return
        level = self._get_level(level)
        message = self._format_message(message, *args, prefix = prefix, max_length = max_length, colored = colored, level = level)
        hook(message)

    def info(self, *args, **kwargs):
        return self.log('INFO', *args, **kwargs)
    
    def debug(self, *args, **kwargs):
        return self.log('DEBUG', *args, **kwargs)
    
    def warning(self, *args, **kwargs):
        return self.log('WARNING', *args, **kwargs)
    
    def error(self, *args, **kwargs):
        return self.log('ERROR', *args, **kwargs)
    
    def trace(self, msg: Union[str, Any], error: Optional[Type[Exception]] = None, level: str = "ERROR", limit: Optional[int] = None, chain: Optional[bool] = True, colored: Optional[bool] = False, prefix: Optional[str] = None, max_length: Optional[int] = None, hook: Optional[Callable] = None, **kwargs):
        """
        This method logs the traceback of an exception.

        :param error: The exception to log.
        """
        if not hook: return
        _depth = kwargs.pop('depth', None)
        if _depth is not None: limit = _depth
        _msg = msg if isinstance(msg, str) else self._format_message(msg, colored = True, prefix = prefix, max_length = max_length)
        # pprint.pformat(msg)
        _msg += f"\n{traceback.format_exc(chain = chain, limit = limit)}"
        if error: _msg += f" - {error}"
        hook(_msg)

    def exception(self, *args, **kwargs):
        return self.log('ERROR', *args, **kwargs)
    
    def success(self, *args, **kwargs):
        return self.log('SUCCESS', *args, **kwargs)



# Setup Default Logger
class Logger(_Logger):

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
        if isinstance(level, str): level = level.upper()
        elif isinstance(level, int): level = LOGLEVEL_MAPPING.get(level, 'INFO')
        return level

    def _format_item(
        self,
        msg: Any,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        level: Optional[str] = None,
        _is_part: Optional[bool] = False,
    ) -> str:  # sourcery skip: extract-duplicate-method, low-code-quality, split-or-ifs
        """
        Formats an item
        """
        # Primitive Types
        if isinstance(msg, str): return msg[:max_length] if max_length else msg
        if isinstance(msg, (float, int, bool, type(None))): return str(msg)[:max_length] if max_length else str(msg)
        if isinstance(msg, (list, set)):
            _msg = str(msg) if _is_part else "\n" + "".join(f'- {item}\n' for item in msg)
            return _msg[:max_length] if max_length else _msg
        
        prefix, suffix = '', ''
        if colored:
            prefix = '|g|'
            if level:
                level = level.lower()
                prefix = DEFAULT_STATUS_COLORS.get(level, '|g|')
            suffix = '|e|'

        if isinstance(msg, dict):
            _msg = "\n"
            for key, value in msg.items():
                _value = f'{value}'
                if max_length and len(_value) > max_length:
                    _value = f'{_value[:max_length]}...'
                _msg += f'- {prefix}{key}{suffix}: {_value}\n'
            return _msg.rstrip()
        
        if isinstance(msg, tuple):
            _msg = "".join(f'- {prefix}{key}{suffix}: {self._format_item(value, max_length = max_length, colored = colored, level = level,  _is_part = True)}\n' for key, value in zip(msg[0], msg[1]))
            return _msg[:max_length] if max_length else _msg

        # Complex Types
        if (hasattr(msg, 'dict') and hasattr(msg, 'Config')) or hasattr(msg, 'fields'):
            # Likely Pydantic Model
            _msg = f'{prefix}[{msg.__class__.__name__}]{suffix}'
            fields = msg.fields.keys() if hasattr(msg, 'fields') else msg.__fields__.keys()
            for field in fields:
                field_str = f'{prefix}{field}{suffix}'
                val_s = f'\n  {field_str}: {getattr(msg, field)!r}'
                if max_length is not None and len(val_s) > max_length:
                    val_s = f'{val_s[:max_length]}...'
                _msg += val_s
            return _msg
            # return self._format_item(msg.dict(), max_length = max_length, colored = colored, _is_part = _is_part)
        
        if hasattr(msg, 'model_dump'):
            return self._format_item(msg.model_dump(mode = 'json'), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

        if hasattr(msg, 'dict'):
            return self._format_item(msg.dict(), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

        if hasattr(msg, 'json'):
            return self._format_item(msg.json(), max_length = max_length, colored = colored, level = level, _is_part = _is_part)

        if hasattr(msg, '__dict__'):
            return self._format_item(msg.__dict__, max_length = max_length, colored = colored, level = level, _is_part = _is_part)
        
        return str(msg)[:max_length] if max_length else str(msg)


    def _format_message(
        self, 
        message: Any, 
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
        _message = ""
        if prefix: 
            if colored and '|' not in prefix: 
                base_color = '|g|'
                if level:
                    level = level.lower()
                    base_color = DEFAULT_STATUS_COLORS.get(level, '|g|')
                prefix = f'{base_color}{prefix}|e|'
            _message += f'[{prefix}] '
        _message += self._format_item(message, max_length = max_length, colored = colored, level = level)
        if args:
            for arg in args:
                _message += "\n"
                _message += self._format_item(arg, max_length = max_length, colored = colored, level = level)
        if colored:
            # Add escape characters to prevent errors
            _message = _message.replace("<fg", ">|fg")
            _message = _message.replace("<", "\</")
            _message = find_and_format_seps(_message)
            # print(_message)
            for key, value in COLORED_MESSAGE_MAP.items():
                _message = _message.replace(key, value)
            _message = _message.replace(">|fg", "<fg")
            _message = _message.replace("\</", "\<")
            _message += RESET_COLOR
        return _message

    
    def log_if(
        self, 
        name: str, 
        message: Any, 
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
        message: Any, 
        *args, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        hook: Optional[Callable] = None,
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
        if hook: hook(message)

    def info(
        self, 
        message: Any, 
        *args, 
        colored: Optional[bool] = False, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Callable] = None,
        **kwargs
    ):  # noqa: N805
        """
        Log ``message.format(*args, **kwargs)`` with severity ``'INFO'``.
        """
        message = self._format_message(message, *args, prefix = prefix, max_length = max_length, colored = colored, level = 'INFO')
        try:
            self._log("INFO", False, self._get_opts(colored = colored), message, args, kwargs)
        except TypeError:
            # Compatibility with < 0.6.0
            self._log("INFO", 20, False, self._get_opts(colored = colored), message, args, kwargs)
        if hook: hook(message)

    def success(
        self, 
        message, 
        *args, 
        colored: Optional[bool] = False, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Callable] = None,
        **kwargs
    ):  # noqa: N805
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'SUCCESS'``."""
        message = self._format_message(message, *args, prefix = prefix, max_length = max_length, colored = colored, level = 'SUCCESS')
        try:
            self._log("SUCCESS", False, self._get_opts(colored = colored), message, args, kwargs)
        except TypeError:
            # Compatibility with < 0.6.0
            self._log("SUCCESS", 20, False, self._get_opts(colored = colored), message, args, kwargs)
        if hook: hook(message)

    def warning(
        self, 
        message, 
        *args, 
        colored: Optional[bool] = False, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Callable] = None,
        **kwargs
    ):  # noqa: N805
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'WARNING'``."""
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored, level = 'WARNING')
        try:
            self._log("WARNING", False, self._get_opts(colored = colored), message, args, kwargs)
        except TypeError:
            # Compatibility with < 0.6.0
            self._log("WARNING", 30, False, self._get_opts(colored = colored), message, args, kwargs)
        if hook: hook(message)

    def error(
        self,
        message: Any,
        *args,
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        hook: Optional[Callable] = None,
        **kwargs
    ) -> None:
        """
        Log ``message.format(*args, **kwargs)`` with severity ``'ERROR'``.
        """
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored, level = 'ERROR')
        try:
            self._log("ERROR", False, self._get_opts(colored = colored), message, args, kwargs)
        except TypeError:
            self._log("ERROR", 40, False, self._get_opts(colored = colored), message, args, kwargs)
        if hook: hook(message)

    def trace(
        self, 
        msg: Union[str, Any], 
        error: Optional[Type[Exception]] = None, 
        level: str = "ERROR",
        limit: Optional[int] = None,
        chain: Optional[bool] = True,
        colored: Optional[bool] = False,
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Callable] = None,
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
        if hook: hook(_msg)

    def exception(
        self,
        message: Any,
        *args,
        colored: Optional[bool] = False,
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        hook: Optional[Callable] = None,
        **kwargs
    ):
        """
        Log ``message.format(*args, **kwargs)`` with severity ``'ERROR'``.
        """
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored, level = 'ERROR')
        super().exception(message, *args, **kwargs)
        if hook: hook(message)

    
    def __call__(self, message: Any, *args, level: str = 'info', **kwargs):
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
    def render(
        self,
        objs: Union[Any, List[Any]],
        level: str = 'INFO',
        **kwargs,
    ) -> None:
        """
        Tries to render an object with pformat
        """
        if not isinstance(objs, list):
            objs = [objs]
        _log = self.get_log_mode(level)
        for obj in objs:
            try:
                _log('\n' + pprint.pformat(obj, **kwargs))
            except Exception as e:
                _log('\n' + obj)

    def render_yaml(
        self,
        objs: Union[Any, List[Any]],
        level: str = 'INFO',
        **kwargs,
    ) -> None:
        """
        Tries to render a yaml object.
        """
        _log = self.get_log_mode(level)
        try:
            from fileio.io import Yaml
            _log('\n' + Yaml.dumps(objs, **kwargs))
        
        except Exception as e:
            import yaml
            _log('\n' + yaml.dump(objs, **kwargs))

    def display_crd(self, message: Any, *args, level: str = 'info', **kwargs):
        """
        Display CRD information in the log.

        Parameters
        ----------
        message : Any
            The message to display.
        level : str
            The log level to use.
        """
        __message = ""
        if isinstance(message, list):
            for m in message:
                if isinstance(m, dict):
                    __message += "".join(f'- <light-blue>{key}</>: {value}\n' for key, value in m.items())
                else:
                    __message += f'- <light-blue>{m}</>\n'
        elif isinstance(message, dict):
            __message = "".join(f'- <light-blue>{key}</>: {value}\n' for key, value in message.items())
        else:
            __message = str(message)
        _log = self.get_log_mode(level)
        _log(__message.strip(), *args, **kwargs)


    def mute_logger(self, modules: Optional[Union[str, List[str]]], level: str = 'WARNING'):
        """
        Helper to mute a logger from another module.
        """
        if not isinstance(modules, list):
            modules = [modules]
        for module in modules:
            logging.getLogger(module).setLevel(logging.getLevelName(level))

    def mute_warning(self, action: str = 'ignore', category: Type[Warning] = Warning, module: str = None, **kwargs):
        """
        Helper to mute a warning from another module.
        """
        if module:
            warnings.filterwarnings(action, category=category, module=module, **kwargs)
        else:
            warnings.filterwarnings(action, category=category, **kwargs)
    
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

    
    def add_healthz_filter(
        self,
        loggers: Optional[Union[str, List[str]]] = None,
        paths: Optional[Union[str, List[str]]] = None,
    ):
        """
        Adds a filter to the logger to filter out healthz requests.

        Parameters
        ----------
        loggers : Optional[Union[str, List[str]]]
            The loggers to add the filter to.
            defaults to ['gunicorn.glogging.Logger', 'uvicorn.access']
        paths : Optional[Union[str, List[str]]]
            The paths to filter out.
            defaults to ['/healthz', '/health']
        """
        if not loggers: loggers = ['gunicorn.glogging.Logger', 'uvicorn.access']
        if not paths: paths = ['/healthz', '/health']
        if not isinstance(loggers, list): loggers = [loggers]
        if not isinstance(paths, list): paths = [paths]

        def _healthz_filter(record: logging.LogRecord) -> bool:
            if 'path' in record.args:
                # if record.args.get('path'):
                return record.args['path'] not in paths
            return all(path not in record.args for path in paths)

        for logger in loggers:
            logging.getLogger(logger).addFilter(_healthz_filter)

    def mute_module(
        self,
        module: str,
        **kwargs,
    ):
        """
        Efectively mutes a module
            
            - `module`: The module to mute
        """
        def _mute_filter(record: logging.LogRecord) -> bool:
        
            return record.module == module
        
        logging.getLogger(module).addFilter(_mute_filter)
    

class InterceptHandler(logging.Handler):
    loglevel_mapping = LOGLEVEL_MAPPING

    def emit(self, record):
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



class LoggerFormatter:

    max_extra_lengths: Dict[str, int] = {}

    @classmethod
    def get_extra_length(cls, key: str, value: str) -> int:
        """
        Returns the max length of an extra key
        """
        if key not in cls.max_extra_lengths:
            cls.max_extra_lengths[key] = len(key)
        if len(value) > cls.max_extra_lengths[key]:
            cls.max_extra_lengths[key] = len(value)
        return cls.max_extra_lengths[key]

    @classmethod
    def queue_logger_formatter(cls, record: Dict[str, Union[Dict[str, Any], Any]]) -> str:
        """
        Formats the log message for the queue.
        """
        _extra: Dict[str, Union[Dict[str, Any], Any]] = record.get('extra', {})
        if not record['extra'].get('worker_name'):
            record['extra']['worker_name'] = ''
        
        status = _extra.get('status')
        kind: str = _extra.get('kind')
        if status and isinstance(status, Enum): status = status.name
        
        kind_color = QUEUE_STATUS_COLORS.get(kind.lower(), FALLBACK_STATUS_COLOR)
        if '<' not in kind_color: kind_color = f'<{kind_color}>'
        extra = kind_color + '{extra[kind]}</>:'
        if _extra.get('queue_name'):
            queue_name_length = cls.get_extra_length('queue_name', _extra['queue_name'])
            extra += '<b><fg #006d77>{extra[queue_name]:<' + str(queue_name_length) + '}</></>:'
        if _extra.get('worker_name'):
            worker_name_length = cls.get_extra_length('worker_name', _extra['worker_name'])
            extra += '<fg #83c5be>{extra[worker_name]:<' + str(worker_name_length) + '}</>:'
        # extra += '<fg #83c5be>{extra[worker_name]}</>:<b><fg #006d77>{extra[queue_name]:<18}</></>:'
        if _extra.get('job_id'):
            extra += '<fg #005f73>{extra[job_id]}</>'
        if status:
            status_color = QUEUE_STATUS_COLORS.get(status.lower(), FALLBACK_STATUS_COLOR)
            if '<' not in status_color: status_color = f'<{status_color}>'
            extra += f':{status_color}' + '{extra[status]}</>: '
        # extra += RESET_COLOR
        # print(extra)
        return extra


    @classmethod
    def default_formatter(cls, record: Dict[str, Union[Dict[str, Any], Any]]) -> str:
        """
        To add a custom format for a module, add another `elif` clause with code to determine `extra` and `level`.

        From that module and all submodules, call logger with `logger.bind(foo='bar').info(msg)`.
        Then you can access it with `record['extra'].get('foo')`.
        """        
        _extra = record.get('extra', {})
        extra = DEFAULT_CLASS_COLOR + '{name}</>:' + DEFAULT_FUNCTION_COLOR + '{function}</>: '
        if _extra.get('worker_name') or _extra.get('queue_name'):
            extra = cls.queue_logger_formatter(record)
        
        if 'result=tensor([' not in str(record['message']):
            return "<level>{level: <8}</> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</>: " \
                       + extra + "<level>{message}</level>" + RESET_COLOR + "\n"
        
        msg = str(record['message'])[:100].replace('{', '(').replace('}', ')')
        return "<level>{level: <8}</> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</>: "\
                   + extra + "<level>" + msg + f"</level>{RESET_COLOR}\n"



_registered_logger_modules: Set[str] = set()

def register_logger_module(module: str):
    """
    Registers a logger module
    """
    global _registered_logger_modules
    module = extract_module_name(module)
    _registered_logger_modules.add(module)
    # print('Registered logger module: ', module)


@functools.lru_cache(maxsize=1000)
def is_registered_logger_module(name: str) -> bool:
    """
    Returns whether a logger module is registered
    """
    module_name = extract_module_name(name)
    return module_name in _registered_logger_modules



_lock = threading.Lock()
_logger_contexts: Dict[str, Logger] = {
    # 'lazyops': _logger,
}

def create_global_logger(
    name: Optional[str] = 'lazyops',
    level: Union[str, int] = "INFO",
    format: Optional[Callable] = None,
    filter: Optional[Callable] = None,
    handlers: Optional[List[logging.Handler]] = None,
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
            patchers=[],
            extra={},
        )

    _logger.name = 'lazyops'
    _logger.is_global = True
    dev_level = _logger.level(name='DEV', no=19, color="<blue>", icon="@")

    if _defaults.LOGURU_AUTOINIT and sys.stderr: _logger.add(sys.stderr)
    _atexit.register(_logger.remove)

    _logger.remove()
    _logger.add_if_condition('dev', _logger._is_dev_condition)
    
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
    handlers: Optional[List[logging.Handler]] = None,
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
            
    if name is None: name = 'lazyops'
    if name in _logger_contexts:
        return _logger_contexts[name]
    
    with _lock:
        if name == 'lazyops':
            return create_global_logger(
                name = name,
                level = level,
                format = format,
                filter = filter,
                handlers = handlers,
                settings = settings,
            )
        
        if isinstance(level, str): level = level.upper()
        # print(f"[{name}] Creating logger with level: {level}")
        _logger = _logger_contexts['lazyops']

        if name and format is not None:
            # Add a new handler
            def _filter_func(record: logging.LogRecord) -> bool:
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



if os.getenv('DEBUG_ENABLED') == 'True':
    logger_level = 'DEV'
else:
    logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()



get_logger = create_default_logger
logger = create_default_logger(__name__, level = logger_level)

default_logger = logger
null_logger = NullLogger(name = 'null_logger')


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
    name = name or 'lazyops'
    name = name.split('.')[0]
    logger_level = level
    if name != 'lazyops':
        __logger = get_logger(name, logger_level, **kwargs)
    else:
        __logger = logger
    if verbose: __logger.info(f"[{name}] Changing logger level from {logger_level} -> {level}")
    __logger._core.min_level = float(REVERSE_LOGLEVEL_MAPPING[logger_level.upper()])
    

def add_api_log_filters(
    modules: typing.Optional[typing.Union[typing.List[str], str]] = ['gunicorn', 'uvicorn'],
    routes: typing.Optional[typing.Union[typing.List[str], str]] = ['/healthz'],
    status_codes: typing.Optional[typing.Union[typing.List[int], int]] = None,
    verbose: bool = False,
):  # sourcery skip: default-mutable-arg
    """
    Add filters to the logger to remove health checks and other unwanted logs

    args:

        modules: list of modules to filter [default: ['gunicorn', 'uvicorn']
        routes: list of routes to filter [default: ['/healthz']]
        status_codes: list of status codes to filter [default: None]
        verbose: bool = False [default: False]
    """

    if not isinstance(modules, list): modules = [modules]
    if routes and not isinstance(routes, list): routes = [routes]
    if status_codes and not isinstance(status_codes, list): status_codes = [status_codes]

    def filter_api_record(record: logging.LogRecord) -> bool:
        """
        Filter out health checks and other unwanted logs
        """
        if routes:
            for route in routes:
                if route in record.args: return False
        if status_codes:
            for sc in status_codes:
                if sc in record.args: return False
        return True
    
    for module in modules:
        if module == 'gunicorn': module = 'gunicorn.glogging.Logger'
        elif module == 'uvicorn': module = 'uvicorn.logging.Logger'
        _apilogger = logging.getLogger(module)
        if verbose: default_logger.info(f"Adding API filters to {module} for routes: {routes} and status_codes: {status_codes}")
        _apilogger.addFilter(filter_api_record)
