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

from loguru import _defaults
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from pydantic import BaseSettings

from typing import Type, Union, Optional, Any, List, Dict, Tuple, Callable

# Use this section to filter out warnings from other modules
os.environ['TF_CPP_MIN_LOG_LEVEL'] = os.getenv('TF_CPP_MIN_LOG_LEVEL', '3')
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
warnings.filterwarnings("ignore", message = "Unclosed client session")


STATUS_COLOR = {
    'enqueue': 'light-blue',
    'finish': 'green',
    'completed': 'green',
    'retry': 'yellow',
    'error': 'red',
    'abort': 'red',
    'process': 'cyan',
    'scheduled': 'yellow',
    'startup': 'green',
    'shutdown': 'red',
    'sweep': 'yellow',
    'dequeue': 'light-blue',
    'stats': 'light-blue',
    'reset': '\x1b[0m'

}
FALLBACK_STATUS_COLOR = 'magenta'

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
    '|gr|': '<gray>',
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


def _find_seps(msg: str) -> str:
    """
    Find any |a,b,c| and format them |a||b||c|

    ex:
      |em,b,u| -> |em||b||u|
      |em,b| -> |em||b|
      
    """
    # v2
    for sep_match in re.finditer('\|\w+,(\w+,*)+\|', msg):
        s = sep_match.group()
        # print(s)
        if len(s) >= 10: continue
        msg = msg.replace(s, "||".join(s.split(",")))
        # print(msg)
    return msg

    # v1
    # return re.sub(r'\|(\w+),(\w+)\|', r'|\1||\2|', msg)
    # return re.sub(r'\|(\w+)\|', r'|\1||', msg)

# Setup Default Logger
class Logger(_Logger):

    settings: Type[BaseSettings] = None
    conditions: Dict[str, Tuple[Union[Callable, bool], str]] = {}
    default_trace_depth: Optional[int] = None
    _colored_opts = None


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
    
    def _filter(self, record: logging.LogRecord, name: Optional[str] = None) -> bool:
        """
        Filters out messages based on conditions
        """
        if not self.conditions:
            return True
        if name is not None:
            return self._filter_if(name, record)[0]
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

    def get_log_mode(self, level: str = "info"):
        """
        Returns the log mode based on the level
        """
        return self.dev if level.upper() in {'DEV'} else getattr(self, level.lower())
    
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
        _is_part: Optional[bool] = False,
    ) -> str:  # sourcery skip: low-code-quality
        """
        Formats an item
        """
        # Primitive Types
        if isinstance(msg, str): return msg[:max_length] if max_length else msg
        if isinstance(msg, (float, int, bool, type(None))): return str(msg)[:max_length] if max_length else str(msg)
        if isinstance(msg, (list, set)):
            _msg = str(msg) if _is_part else "".join(f'- {item}\n' for item in msg)
            return _msg[:max_length] if max_length else _msg
        prefix = '|g|' if colored else ''
        suffix = '|e|' if colored else ''
        if isinstance(msg, dict):
            _msg = "\n"
            for key, value in msg.items():
                _value = f'{value}'
                if max_length and len(_value) > max_length:
                    _value = f'{_value[:max_length]}...'
                _msg += f'- {prefix}{key}{suffix}: {_value}\n'
            # _msg = "".join(f'- {prefix}{key}{suffix}: {self._format_item(value, max_length = max_length, colored = colored, _is_part = True)}\n' for key, value in msg.items())
            # return _msg[:max_length] if max_length else _msg
            return _msg.rstrip()
        if isinstance(msg, tuple):
            _msg = "".join(f'- {prefix}{key}{suffix}: {self._format_item(value, max_length = max_length, colored = colored,  _is_part = True)}\n' for key, value in zip(msg[0], msg[1]))
            return _msg[:max_length] if max_length else _msg

        # Complex Types
        if hasattr(msg, 'dict') and hasattr(msg, 'Config'):
            # Likely Pydantic Model
            _msg = f'{prefix}[{msg.__class__.__name__}]{suffix}'
            fields = msg.__fields__.keys()
            for field in fields:
                field_str = f'{prefix}{field}{suffix}'
                val_s = f'\n  {field_str}: {getattr(msg, field)!r}'
                if max_length is not None and len(val_s) > max_length:
                    val_s = f'{val_s[:max_length]}...'
                _msg += val_s
            return _msg
            # return self._format_item(msg.dict(), max_length = max_length, colored = colored, _is_part = _is_part)
        
        if hasattr(msg, 'dict'):
            return self._format_item(msg.dict(), max_length = max_length, colored = colored, _is_part = _is_part)

        if hasattr(msg, 'json'):
            return self._format_item(msg.json(), max_length = max_length, colored = colored, _is_part = _is_part)

        if hasattr(msg, '__dict__'):
            return self._format_item(msg.__dict__, max_length = max_length, colored = colored, _is_part = _is_part)
        
        return str(msg)[:max_length] if max_length else str(msg)


    def _format_message(
        self, 
        message: Any, 
        *args,
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
    ) -> str:
        """
        Formats the message

        "example |b|msg|e|"
        -> "example <blue>msg</><reset>"
        """
        _message = ""
        if prefix: _message += f'[{prefix}] '
        _message += self._format_item(message, max_length = max_length, colored = colored)
        if args:
            for arg in args:
                _message += "\n"
                _message += self._format_item(arg, max_length = max_length, colored = colored)
        if colored:
            # Add escape characters to prevent errors
            _message = _message.replace("<", "\<")
            _message = _find_seps(_message)
            # print(_message)
            for key, value in COLORED_MESSAGE_MAP.items():
                _message = _message.replace(key, value)
            _message += STATUS_COLOR['reset']

        return _message

    def log(
        self, 
        level: Union[str, int], 
        message: Any, 
        *args, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        colored: Optional[bool] = False,
        **kwargs
    ):  # noqa: N805
        """
        Log ``message.format(*args, **kwargs)`` with severity ``level``.
        """
        level = self._get_level(level)
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored)
        self._log(level, False, self._get_opts(colored = colored), message, args, kwargs)
        # self._log(level, False, __self._options, __message, args, kwargs)
        # return super().log(level, message, *args, **kwargs)
    
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
            # print(condition, clevel)
            return self.log((level or clevel), message, *args, **kwargs)
            # return super().log((level or clevel), message, *args, **kwargs)

    def info(
        self, 
        message: Any, 
        *args, 
        colored: Optional[bool] = False, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        **kwargs
    ):  # noqa: N805
        """
        Log ``message.format(*args, **kwargs)`` with severity ``'INFO'``.
        """
        message = self._format_message(message, *args, prefix = prefix, max_length = max_length, colored = colored)
        # self._log("INFO", False, self._options, message, args, kwargs)
        self._log("INFO", False, self._get_opts(colored = colored), message, args, kwargs)

    def success(
        self, 
        message, 
        *args, 
        colored: Optional[bool] = False, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        **kwargs
    ):  # noqa: N805
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'SUCCESS'``."""
        message = self._format_message(message, *args, prefix = prefix, max_length = max_length, colored = colored)
        # self._log("SUCCESS", False, self._options, message, args, kwargs)
        self._log("SUCCESS", False, self._get_opts(colored = colored), message, args, kwargs)
    

    def warning(
        self, 
        message, 
        *args, 
        colored: Optional[bool] = False, 
        prefix: Optional[str] = None,
        max_length: Optional[int] = None,
        **kwargs
    ):  # noqa: N805
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'WARNING'``."""
        message = self._format_message(message, prefix = prefix, max_length = max_length, colored = colored)
        # self._log("WARNING", False, self._options, message, args, kwargs)
        self._log("WARNING", False, self._get_opts(colored = colored), message, args, kwargs)


    def dev(self, message: Any, *args, **kwargs):
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'DEV'``."""
        # self._log('DEV', None, False, self._options, message, args, kwargs)
        self._log('DEV', None, False, self._get_opts(colored = True), message, args, kwargs)


    def trace(
        self, 
        msg: Union[str, Any], 
        error: Optional[Type[Exception]] = None, 
        level: str = "ERROR",
        depth: Optional[int] = None,
        chain: Optional[bool] = True,
    ) -> None:
        """
        This method logs the traceback of an exception.

        :param error: The exception to log.
        """
        _msg = msg if isinstance(msg, str) else pprint.pformat(msg)
        _msg += f": {traceback.format_exc(chain = chain, limit = (depth if depth is not None else self.default_trace_depth))}"
        if error: _msg += f" - {error}"
        _log = self.get_log_mode(level)
        _log(_msg)

    
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


    # def warning(__self, __message, *args, **kwargs):  # noqa: N805
    #     r"""Log ``message.format(*args, **kwargs)`` with severity ``'WARNING'``."""
    #     __self._log("WARNING", False, __self._options, __message, args, kwargs)

    # def error(__self, __message, *args, **kwargs):  # noqa: N805
    #     r"""Log ``message.format(*args, **kwargs)`` with severity ``'ERROR'``."""
    #     __self._log("ERROR", False, __self._options, __message, args, kwargs)

    # def critical(__self, __message, *args, **kwargs):  # noqa: N805
    #     r"""Log ``message.format(*args, **kwargs)`` with severity ``'CRITICAL'``."""
    #     __self._log("CRITICAL", False, __self._options, __message, args, kwargs)

    # def exception(__self, __message, *args, **kwargs):  # noqa: N805
    #     r"""Convenience method for logging an ``'ERROR'`` with exception information."""
    #     options = (True,) + __self._options[1:]
    #     __self._log("ERROR", False, options, __message, args, kwargs)


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



# < 0.7.0
try:
    logger = Logger(
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
    logger = Logger(
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

dev_level = logger.level(name='DEV', no=19, color="<blue>", icon="@")

if _defaults.LOGURU_AUTOINIT and sys.stderr:
    logger.add(sys.stderr)

_atexit.register(logger.remove)

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
        log.opt(
            depth=depth,
            exception=record.exc_info
        ).log(level, record.getMessage())


class CustomizeLogger:


    @classmethod
    def make_default_logger(
        cls, 
        level: Union[str, int] = "INFO",
        settings: Optional[Type[BaseSettings]] = None,
        format: Optional[Callable] = None,
        filter: Optional[Callable] = None,
        handlers: Optional[List[logging.Handler]] = None,
        **kwargs,
    ):
        # todo adjust this later to use a ConfigModel
        if isinstance(level, str): level = level.upper()
        logger.remove()
        logger.add(
            sys.stdout,
            enqueue = True,
            backtrace = True,
            colorize = True,
            level = level,
            format = format if format is not None else cls.logger_formatter,
            filter = filter if filter is not None else logger._filter,
        )

        logger.add_if_condition('dev', logger._is_dev_condition)

        logging.basicConfig(
            handlers = handlers or [InterceptHandler()], 
            level = 0
        )
        *options, extra = logger._options
        new_logger = Logger(logger._core, *options, {**extra})
        if settings: new_logger.settings = settings
        return new_logger


    @staticmethod
    def logger_formatter(record: dict) -> str:
        """
        To add a custom format for a module, add another `elif` clause with code to determine `extra` and `level`.

        From that module and all submodules, call logger with `logger.bind(foo='bar').info(msg)`.
        Then you can access it with `record['extra'].get('foo')`.
        """        
        extra = '<cyan>{name}</>:<cyan>{function}</>: '

        if record.get('extra'):
            if record['extra'].get('request_id'):
                extra = '<cyan>{name}</>:<cyan>{function}</>:<green>request_id: {extra[request_id]}</> '

            elif record['extra'].get('job_id') and record['extra'].get('queue_name') and record['extra'].get('kind'):
                status = record['extra'].get('status')
                color = STATUS_COLOR.get(status, FALLBACK_STATUS_COLOR)
                kind_color = STATUS_COLOR.get(record.get('extra', {}).get('kind'), FALLBACK_STATUS_COLOR)
                if not record['extra'].get('worker_name'):
                    record['extra']['worker_name'] = ''
                extra = '<cyan>{extra[queue_name]}</>:<bold><magenta>{extra[worker_name]}</></>:<bold><' + kind_color + '>{extra[kind]:<9}</></> <' + color + '>{extra[job_id]}</> '

            elif record['extra'].get('kind') and record['extra'].get('queue_name'):
                if not record['extra'].get('worker_name'):
                    record['extra']['worker_name'] = ''
                kind_color = STATUS_COLOR.get(record.get('extra', {}).get('kind'), FALLBACK_STATUS_COLOR)
                extra = '<cyan>{extra[queue_name]}</>:<b><magenta>{extra[worker_name]}</></>:<b><' + kind_color + '>{extra[kind]:<9}</></> '


        if 'result=tensor([' not in str(record['message']):
            return "<level>{level: <8}</> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</>: "\
                       + extra + "<level>{message}</level>\n"
        msg = str(record['message'])[:100].replace('{', '(').replace('}', ')')
        return "<level>{level: <8}</> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</>: "\
                   + extra + "<level>" + msg + f"</level>{STATUS_COLOR['reset']}\n"


if os.getenv('DEBUG_ENABLED') == 'True':
    logger_level = 'DEV'
else:
    logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()


get_logger = CustomizeLogger.make_default_logger
default_logger = CustomizeLogger.make_default_logger(level = logger_level)


def change_logger_level(
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
    global default_logger, logger_level
    if isinstance(level, str):
        level = level.upper()
    # Skip if the level is the same
    if level == logger_level: return
    if verbose: default_logger.info(f"Changing logger level from {logger_level} -> {level}")
    logger_level = level
    default_logger = get_logger(logger_level, **kwargs)


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



