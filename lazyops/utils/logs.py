import os
import sys
import logging
import warnings
import atexit as _atexit

from loguru import _defaults
from loguru._logger import Core as _Core
from loguru._logger import Logger as _Logger
from typing import Any

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

    @classmethod
    def make_default_logger(cls, level: str = "INFO"):
        # todo adjust this later to use a ConfigModel
        logger.remove()
        logger.add(
            sys.stdout,
            enqueue=True,
            backtrace=True,
            colorize=True,
            level=level.upper(),
            format=cls.logger_formatter,
        )
        logging.basicConfig(handlers=[InterceptHandler()], level=0)
        *options, extra = logger._options
        return Logger(logger._core, *options, {**extra})
        # return logger

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


get_logger = CustomizeLogger.make_default_logger
default_logger = CustomizeLogger.make_default_logger()

