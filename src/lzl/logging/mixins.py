from __future__ import annotations

import abc
import logging
import warnings
import pprint
import contextlib
from .state import register_module_name
from typing import Optional, Set, Callable, TYPE_CHECKING, Union, List, Type, Tuple, Any, Dict

if TYPE_CHECKING:
    from .base import Logger


def temp_silence_filter(record: logging.LogRecord) -> int:
    """
    Temporary silence filter
    """
    return 0

class LoggingMixin(abc.ABC):
    """
    A mixin class for logging hooks
    """

    _logging_hooks: Optional[Set[Callable]] = set()
    _silenced_modules: Optional[Set[str]] = set()
    _temp_silenced_modules: Dict[str, str] = {}
    _temp_silenced_loggers: Dict[str, Tuple[logging.Logger, int]] = {}

    if TYPE_CHECKING:
        def get_log_mode(self, level: Union[str, int]) -> str:
            ...

    def add_logging_hook(self, *hooks: Callable):
        """
        Adds a logging hook
        """
        for hook in hooks:
            self._logging_hooks.add(hook)

    def remove_logging_hook(self, *hooks: Callable):
        """
        Removes a logging hook
        """
        for hook in hooks:
            self._logging_hooks.remove(hook)

    def add_silenced_modules(self, *modules: str):
        """
        Adds a list of modules to the silenced modules
        """
        for module in modules:
            self._silenced_modules.add(module)

    def remove_silenced_modules(self, *modules: str):
        """
        Removes a list of modules from the silenced modules
        """
        for module in modules:
            self._silenced_modules.remove(module)
            self.remove_temp_silence_from_logging_module(module)
    
    def run_logging_hooks(self, message: str, hook: Optional[Callable] = None):
        """
        Runs the logging hooks
        """
        for log_hook in self._logging_hooks:
            log_hook(message)
        if hook: hook(message)

    @contextlib.contextmanager
    def hooks(self, *hooks: Callable):
        """
        Adds a logging hook
        """
        self.add_logging_hook(*hooks)
        try:
            yield
        finally:
            self.remove_logging_hook(*hooks)

    @contextlib.contextmanager
    def silenced(self, *modules: str):
        """
        Adds a list of modules to the silenced modules
        """
        self.add_silenced_modules(*modules)
        try:
            yield
        finally:
            self.remove_silenced_modules(*modules)

    def set_module_name(self, src_name: str, module_name: str):
        """
        Sets the module name
        """
        register_module_name(src_name, module_name)

    """
    This part still doesn't work atm.
    """
    def is_silenced_record(self, record: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Checks if the record is silenced
        """
        if '.' in record['name']:
            src_module = record['name'].split('.')[0]
            return src_module, src_module in self._silenced_modules
        return record['name'], record['name'] in self._silenced_modules

    def add_temp_silence_to_logging_module(self, src_module: str, module: str):
        """
        Adds a module to the temp silenced modules
        """
        _logger = logging.getLogger(src_module)
        # _logger.addFilter(temp_silence_filter)
        self._temp_silenced_loggers[src_module] = (_logger, _logger.level)
        _logger.setLevel(logging.ERROR)

    def remove_temp_silence_from_logging_module(self, src_module: str):
        """
        Removes a module from the temp silenced modules
        """
        # module = self._temp_silenced_modules.pop(src_module, None)
        (_logger, level) = self._temp_silenced_loggers.pop(src_module, (None, None))
        if not _logger: return
        _logger.setLevel(level)
        # if not module: return
        # _logger = logging.getLogger(module)
        # _logger.removeFilter(temp_silence_filter)

    def check_silenced(self, record: Dict[str, Any]) -> bool:
        """
        Checks if the record is silenced
        """
        src_module, is_silenced = self.is_silenced_record(record)
        if is_silenced and src_module not in self._temp_silenced_loggers:
            self.add_temp_silence_to_logging_module(src_module, record['name'])
        return is_silenced


    """
    Rendering Utilities
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
        if not isinstance(objs, list): objs = [objs]
        _log = self.get_log_mode(level)
        for obj in objs:
            try: _log('\n' + pprint.pformat(obj, **kwargs))
            except Exception as e: _log('\n' + obj)

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



    """
    Logging Utilities
    """

    def mute_logger(self, modules: Optional[Union[str, List[str]]], level: str = 'WARNING'):
        """
        Helper to mute a logger from another module.
        """
        if not isinstance(modules, list): modules = [modules]
        for module in modules:
            logging.getLogger(module).setLevel(logging.getLevelName(level))

    def mute_warning(self, action: str = 'ignore', category: Type[Warning] = Warning, module: str = None, **kwargs):
        """
        Helper to mute a warning from another module.
        """
        if module: warnings.filterwarnings(action, category=category, module=module, **kwargs)
        else: warnings.filterwarnings(action, category=category, **kwargs)
    
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
    