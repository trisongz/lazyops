from __future__ import annotations

import logging
import traceback
from .mixins import LoggingMixin
from .utils import format_item, format_message, get_logging_level, extract_module_name
from typing import Optional, Set, Union, Any, Callable, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .utils import MsgItem
    from .base import Logger


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



class NullLogger(logging.Logger, LoggingMixin):
    """
    A logger that does nothing except pass through the log calls to hooks
    """

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
        return format_message(message, max_length = max_length, colored = colored, level = level, *args)
    
    def _get_level(self, level: Union[str, int]) -> str:
        """
        Returns the log level
        """
        return get_logging_level(level)
    
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
        self.run_logging_hooks(message, hook = hook)

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
        self.run_logging_hooks(_msg, hook = hook)

    def exception(self, *args, **kwargs):
        return self.log('ERROR', *args, **kwargs)
    
    def success(self, *args, **kwargs):
        return self.log('SUCCESS', *args, **kwargs)

