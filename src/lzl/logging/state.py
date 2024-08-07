from __future__ import annotations

import threading
import functools
import typing

from .utils import extract_module_name
from typing import Set, Dict, Union, Any, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import logging
    from .base import Logger

_registered_logger_modules: Set[str] = set()
_module_name_mapping: Dict[str, str] = {}

def register_logger_module(module: str):
    """
    Registers a logger module
    """
    global _registered_logger_modules
    module = extract_module_name(module)
    _registered_logger_modules.add(module)

@functools.lru_cache(maxsize=1000)
def is_registered_logger_module(name: str) -> bool:
    """
    Returns whether a logger module is registered
    """
    module_name = extract_module_name(name)
    return module_name in _registered_logger_modules


def register_module_name(module_name: str, module: str):
    """
    Registers a module name
    """
    global _module_name_mapping
    _module_name_mapping[module_name] = module


def run_record_patching_hook(record: Union['logging.LogRecord', Dict[str, Any]]):
    """
    Runs the patching hook
    """
    if record['name'] in _module_name_mapping:
        record['extra']['module_name'] = _module_name_mapping[record['name']]
    return record



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
        from .main import default_logger
        if verbose: default_logger.info(f"Adding API filters to {module} for routes: {routes} and status_codes: {status_codes}")
        _apilogger.addFilter(filter_api_record)


