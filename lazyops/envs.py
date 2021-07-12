
import sys
import threading
import logging
from dataclasses import dataclass
from typing import Optional, Any, Dict

try:
    from google.colab import auth
    _colab = True
except ImportError:
    _colab = False

_notebook = sys.argv[-1].endswith('json')

_logging_levels = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARN,
    'warning': logging.WARNING,
    'error': logging.ERROR,
}

class ThreadSafeHandler:
    def __init__(
        self, 
        lock_mode: str = 'lock',
        handler: Optional[Any] = None):
        self.lock_mode = lock_mode
        self.handler = handler
        self.lock = threading.RLock()  if self.lock_mode == 'rlock' else threading.Lock()

    def get(self, init_func: Any = None, *args, **kwargs):
        if self.lock_mode == 'rlock': self.lock.acquire()
        with self.lock:
            if not self.handler:
                self.handler = init_func(*args, **kwargs)
            return self.handler


class LogFormatter(logging.Formatter):
    COLOR_CODES = {
        logging.CRITICAL: "\033[38;5;196m", # bright/bold magenta
        logging.ERROR:    "\033[38;5;9m", # bright/bold red
        logging.WARNING:  "\033[38;5;11m", # bright/bold yellow
        logging.INFO:     "\033[38;5;111m", # white / light gray
        logging.DEBUG:    "\033[1;30m"  # bright/bold black / dark gray
    }

    RESET_CODE = "\033[0m"
    def __init__(self, color, *args, **kwargs):
        super(LogFormatter, self).__init__(*args, **kwargs)
        self.color = color

    def format(self, record, *args, **kwargs):
        if (self.color == True and record.levelno in self.COLOR_CODES):
            record.color_on  = self.COLOR_CODES[record.levelno]
            record.color_off = self.RESET_CODE
        else:
            record.color_on  = ""
            record.color_off = ""
        return super(LogFormatter, self).format(record, *args, **kwargs)

class LazyOpsLogger:
    def __init__(self, config):
        self.config = config
        self.logger = self.setup_logging()
    
    def setup_logging(self):
        logger = logging.getLogger(self.config['name'])
        logger.setLevel(_logging_levels[self.config.get('log_level', 'info')])

        console_log_output = sys.stdout if _notebook or _colab else sys.stderr        
        console_handler = logging.StreamHandler(console_log_output)
        console_handler.setLevel(self.config["console_log_level"].upper())
        console_formatter = LogFormatter(fmt=self.config["log_line_template"], color=self.config["console_log_color"])
        console_handler.setFormatter(console_formatter)
        if self.config.get('clear_handlers', False) and logger.hasHandlers():
            logger.handlers.clear()
        logger.addHandler(console_handler)
        if self.config.get('quiet_loggers'):
            to_quiet = self.config['quiet_loggers']
            if isinstance(to_quiet, str): to_quiet = [to_quiet]
            for clr in to_quiet:
                clr_logger = logging.getLogger(clr)
                clr_logger.setLevel(logging.ERROR)

        logger.propagate = self.config.get('propagate', False)
        return logger

    def get_logger(self):
        return self.logger
    
    def debug(self, msg, *args, **kwargs):
        return self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        return self.logger.info(msg, *args, **kwargs)
    
    def warn(self, msg, *args, **kwargs):
        return self.logger.warn(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        return self.logger.error(msg, *args, **kwargs)
    
    def __call__(self, msg, *args, **kwargs):
        return self.logger.info(msg, *args, **kwargs)


def setup_new_logger(name, log_level='info', quiet_loggers=None, clear_handlers=False, propagate=True):
    logger_config = {
        'name': name,
        'log_level': log_level,
        'console_log_output': "stdout", 
        'console_log_level': "info",
        'console_log_color': True,
        'logfile_file': None,
        'logfile_log_level': "debug",
        'logfile_log_color': False,
        'log_line_template': f"%(color_on)s[{name}] %(funcName)-5s%(color_off)s: %(message)s",
        'clear_handlers': clear_handlers,
        'quiet_loggers': quiet_loggers,
        'propagate': propagate
    }
    return LazyOpsLogger(logger_config)


class EnvChecker:
    is_colab = _colab
    is_notebook = _notebook
    is_jpy = _notebook
    loggers: Optional[Dict[str, ThreadSafeHandler]] = {}

    def get_logger(self, name = 'LazyOps', *args, **kwargs):
        if not EnvChecker.loggers.get(name):
            EnvChecker.loggers[name] = ThreadSafeHandler()
        return EnvChecker.loggers[name].get(setup_new_logger, name=name, *args, **kwargs)
    

LazyEnv = EnvChecker()
get_logger = LazyEnv.get_logger
logger = get_logger()
