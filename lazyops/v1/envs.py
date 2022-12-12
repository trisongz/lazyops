import os
import sys
import signal
import threading
import logging
from dataclasses import dataclass
from functools import partialmethod
from typing import Optional, Any, Dict, List
from .mp_utils import _CPU_CORES, _MAX_THREADS, _MAX_PROCS
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
# Ignore Some Loggers
logging.getLogger('aiocache').setLevel(logging.ERROR)


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

    def get_logger(self, module=None):
        if module:
            return self.logger.getChild(module)
        return self.logger
    
    def debug(self, msg, *args, **kwargs):
        return self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        return self.logger.info(msg, *args, **kwargs)
    
    def warn(self, msg, *args, **kwargs):
        return self.logger.warn(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        return self.logger.error(msg, *args, **kwargs)
    
    def exception(self, msg, *args, **kwargs):
        return self.logger.exception(msg, *args, **kwargs)
    
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
        'log_line_template': f"%(color_on)s[{name}] %(name)-5s %(funcName)-5s%(color_off)s: %(message)s",
        'clear_handlers': clear_handlers,
        'quiet_loggers': quiet_loggers,
        'propagate': propagate
    }
    return LazyOpsLogger(logger_config)

IsLazyAlive = True

class EnvChecker:
    is_colab = _colab
    is_notebook = _notebook
    is_jpy = _notebook
    cpu_cores = _CPU_CORES
    max_threads = _MAX_THREADS
    max_procs = _MAX_PROCS
    loggers: Optional[Dict[str, ThreadSafeHandler]] = {}
    handlers: Optional[Dict[str, Any]] = {}
    watcher_enabled: Optional[bool] = False
    threads: Optional[List[threading.Thread]] = []
    sigs: Optional[Dict[str, signal.signal]] = {}
    
    
    @classmethod
    def get_logger(cls, name = 'LazyOps', module=None, *args, **kwargs):
        if not EnvChecker.loggers.get(name):
            EnvChecker.loggers[name] = ThreadSafeHandler()
        if module:
            return EnvChecker.loggers[name].get(setup_new_logger, name=name, *args, **kwargs).get_logger(module=module)
        return EnvChecker.loggers[name].get(setup_new_logger, name=name, *args, **kwargs)
    
    @property
    def alive(self):
        return IsLazyAlive
    
    @property
    def killed(self):
        return not IsLazyAlive
    
    @property
    def is_threadsafe(self):
        return bool(threading.current_thread() is threading.main_thread())
    
    @classmethod
    def set_state(cls, state: bool):
        global IsLazyAlive
        IsLazyAlive = state
    

    set_alive = partialmethod(set_state, True)
    set_dead = partialmethod(set_state, False)

    @classmethod
    def exit_handler(cls, signum, frame):
        logger = EnvChecker.loggers['LazyWatch']
        logger.error("Received SIGINT or SIGTERM! Gracefully Exiting.")
        if EnvChecker.handlers:
            for handler, func in EnvChecker.handlers.items():
                logger.error(f'Calling Exit for {handler}')
                func()
        if EnvChecker.threads:
            for thread in EnvChecker.threads:
                thread.join()
        EnvChecker.set_dead()
        sys.exit(0)

    @classmethod
    def enable_watcher(cls):
        if EnvChecker.watcher_enabled:
            return
        EnvChecker.sigs['sigint'] = signal.signal(signal.SIGINT, EnvChecker.exit_handler)
        EnvChecker.sigs['sigterm'] = signal.signal(signal.SIGTERM, EnvChecker.exit_handler)
        EnvChecker.loggers['LazyWatch'] = EnvChecker.get_logger(name='LazyWatch')
        EnvChecker.watcher_enabled = True

    @classmethod
    def add_thread(cls, t):
        EnvChecker.threads.append(t)

    @classmethod
    def set_multiparams(cls, max_procs: int = None, max_threads: int = None):
        if max_procs is not None: EnvChecker.max_procs = max_procs
        if max_threads is not None: EnvChecker.max_threads = max_threads

    @classmethod
    def add_exit_handler(cls, name, func):
        if name not in EnvChecker.handlers:
            EnvChecker.handlers[name] = func


    @classmethod
    def getset(cls, name, val=None, default=None, set_if_none=False):
        eval = os.environ.get(name, default=default)
        if (not eval and set_if_none) or (eval and eval != val):
            os.environ[name] = str(val)
            return os.environ.get(name)
        if not val or not set_if_none:
            return eval
        return eval

    def __call__(self, name, val=None, default=None, set_if_none=None, *args, **kwargs):
        return EnvChecker.getset(name, val=None, default=None, set_if_none=None, *args, **kwargs)
    
    def __exit__(self, type, value, traceback, *args, **kwargs):
        if EnvChecker.watcher_enabled:
            if self.killed:
                sys.exit(0)
            signal.signal(signal.SIGINT, EnvChecker.sigs['sigint'])
            signal.signal(signal.SIGTERM, EnvChecker.sigs['sigterm'])
        EnvChecker.set_dead()


    def watch(self):
        self.enable_watcher()
        return self

        

LazyEnv = EnvChecker()
get_logger = LazyEnv.get_logger
logger = get_logger()
lazywatcher = LazyEnv.watch


def lazywatch(name, *args, **kwargs):
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.info(f'Adding {name} to Exit Handlers')
            LazyEnv.add_exit_handler(name, func)
            return func(*args, **kwargs)
        return wrapper
    return decorator