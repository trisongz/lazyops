import os
import sys
import logging
import typing
import warnings
import atexit as _atexit
import functools

from loguru import _defaults
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from typing import Any, Union

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

}
FALLBACK_STATUS_COLOR = 'magenta'


# Setup Default Logger
class Logger(_Logger):

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
        self._log(level.upper(), None, False, self._options, __message.strip(), args, kwargs)

    def __call__(self, message: Any, *args, level: str = 'info', **kwargs):
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'INFO'``."""
        if isinstance(message, list):
            __message = "".join(f'- {item}\n' for item in message)
        elif isinstance(message, dict):
            __message = "".join(f'- {key}: {value}\n' for key, value in message.items())
        else:
            __message = str(message)
        self._log(level.upper(), None, False, self._options, __message.strip(), args, kwargs)

    def dev(self, message: Any, *args, **kwargs):
        r"""Log ``message.format(*args, **kwargs)`` with severity ``'DEV'``."""
        self._log('DEV', None, False, self._options, message, args, kwargs)


logger = Logger(
    core=_Core(),
    exception=None,
    depth=0,
    record=False,
    lazy=False,
    colors=False,
    raw=False,
    capture=True,
    patcher=None,
    extra={},
)

if _defaults.LOGURU_AUTOINIT and sys.stderr:
    logger.add(sys.stderr)

_atexit.register(logger.remove)

class InterceptHandler(logging.Handler):
    loglevel_mapping = {
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

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = self.loglevel_mapping[record.levelno]
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

    # @classmethod
    # def make_default_logger(cls, level: Union[str, int] = "INFO"):
    #     # todo adjust this later to use a ConfigModel
    #     if isinstance(level, str):
    #         level = level.upper()
    #     logger.remove()
    #     logging.basicConfig(handlers=[InterceptHandler()], level=0)

    #     *options, extra = logger._options
    #     new_logger = Logger(logger._core, *options, {**extra})
    #     new_logger.configure(
    #         handlers=[
    #             {
    #                 "sink": sys.stdout,
    #                 "format": cls.logger_formatter,
    #                 "enqueue": True,
    #                 "backtrace": True,
    #                 "colorize": True,
    #                 "level": level,
    #             },
    #         ],
    #         levels = [{
    #             "name": "DEV",
    #             "no": 19,
    #             "color": "<blue>",
    #             "icon": "@"
    #         }]
    #     )
    #     return new_logger


        # if not hasattr(logger.__class__, 'dev'):
        # try:
        #     dev_level = logger.level(name='DEV', no=19, color="<blue>", icon="@")
        #     logger.__class__.dev = functools.partialmethod(logger.__class__.log, 'DEV')
        #     logger.add(
        #         sys.stdout,
        #         enqueue=True,
        #         backtrace=True,
        #         colorize=True,
        #         level=19,
        #         format=cls.logger_formatter,
        #     )
        # except Exception as e:
        #     pass
        # #     print("Error adding DEV level to logger: ", e) 
        # #     # pass
        # logger.add(
        #     sys.stdout,
        #     enqueue=True,
        #     backtrace=True,
        #     colorize=True,
        #     level=level,
        #     format=cls.logger_formatter,
        # )
        # logging.basicConfig(handlers=[InterceptHandler()], level=0)
        # *options, extra = logger._options
        # return Logger(logger._core, *options, {**extra})

    @classmethod
    def make_default_logger(cls, level: Union[str, int] = "INFO"):
        # todo adjust this later to use a ConfigModel
        if isinstance(level, str):
            level = level.upper()
        logger.remove()
        # if not hasattr(logger.__class__, 'dev'):
        try:
            dev_level = logger.level(name='DEV', no=19, color="<blue>", icon="@")
            logger.__class__.dev = functools.partialmethod(logger.__class__.log, 'DEV')
            logger.add(
                sys.stdout,
                enqueue=True,
                backtrace=True,
                colorize=True,
                level=19,
                format=cls.logger_formatter,
            )
        except Exception as e:
            pass
        #     print("Error adding DEV level to logger: ", e) 
        #     # pass
        logger.add(
            sys.stdout,
            enqueue=True,
            backtrace=True,
            colorize=True,
            level=level,
            format=cls.logger_formatter,
        )
        logging.basicConfig(handlers=[InterceptHandler()], level=0)
        *options, extra = logger._options
        return Logger(logger._core, *options, {**extra})

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
                extra = '<cyan>{extra[queue_name]}</>:<' + kind_color + '>{extra[kind]:<9}</><' + color + '>{extra[job_id]}</> '

            elif record['extra'].get('kind') and record['extra'].get('queue_name'):
                kind_color = STATUS_COLOR.get(record.get('extra', {}).get('kind'), FALLBACK_STATUS_COLOR)
                extra = '<cyan>{extra[queue_name]}</>:<' + kind_color + '>{extra[kind]:<9}</> '

        if 'result=tensor([' not in str(record['message']):
            return "<level>{level: <8}</> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</>: "\
                       + extra + "<level>{message}</level>\n"
        msg = str(record['message'])[:100].replace('{', '(').replace('}', ')')
        return "<level>{level: <8}</> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</>: "\
                   + extra + "<level>" + msg + "</level>\n"


logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()

get_logger = CustomizeLogger.make_default_logger
default_logger = CustomizeLogger.make_default_logger(level = logger_level)


def change_logger_level(
    level: Union[str, int] = 'INFO',
    verbose: bool = False,
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
    default_logger = get_logger(logger_level)


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



