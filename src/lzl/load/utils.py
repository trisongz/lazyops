from __future__ import annotations

"""
Lazy Loading Utilities
"""

import inspect
import functools
from typing import Any, Dict, Callable, Union, Optional, Type, TypeVar, List, Tuple, cast, TYPE_CHECKING
from types import ModuleType


_imported_strings: Dict[str, Any] = {}
_valid_class_init_kwarg: Dict[str, List[str]] = {}


MT = TypeVar("MT", bound=ModuleType)
OT = TypeVar("OT", bound=object)
CT = TypeVar("CT", bound=Callable)

_ImportType = Union[MT, OT, CT]

class ImportFromStringError(Exception):
    pass


def import_from_string(import_str: Any) -> Any:
    """
    Import a dotted module path and return the attribute specified by the
    last name in the path (e.g. getattr(import_from_string('xml.etree.ElementTree'), 'parse')).
    """
    
    if not isinstance(import_str, str):
        return import_str

    module_str, _, attrs_str = import_str.partition(":")
    if not module_str or not attrs_str:
        message = (
            'Import string "{import_str}" must be in format "<module>:<attribute>".'
        )
        raise ImportFromStringError(message.format(import_str=import_str))

    import importlib
    try:
        module = importlib.import_module(module_str)
    except ImportError as exc:
        if exc.name != module_str:
            raise exc from None
        message = 'Could not import module "{module_str}".'
        raise ImportFromStringError(message.format(module_str=module_str)) from exc

    instance = module
    try:
        for attr_str in attrs_str.split("."):
            instance = getattr(instance, attr_str)
    except AttributeError as exc:
        message = 'Attribute "{attrs_str}" not found in module "{module_str}".'
        raise ImportFromStringError(
            message.format(attrs_str=attrs_str, module_str=module_str)
        ) from exc

    return instance

def import_string(dotted_path: str, is_module: Optional[bool] = None, allow_module: Optional[bool] = False) -> _ImportType:
    """
    Taken from pydantic.utils.
    """
    from importlib import import_module
    if is_module:
        return import_module(dotted_path)
    try:
        module_path, class_name = dotted_path.strip(' ').rsplit('.', 1)
    except ValueError as e:
        raise ImportError(f'"{dotted_path}" doesn\'t look like a module path') from e

    module = import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as e:
        if allow_module: return module
        raise ImportError(f'Module "{module_path}" does not define a "{class_name}" attribute') from e


def lazy_import(
    dotted_path: str,
    is_module: Optional[bool] = None,
    allow_module: Optional[bool] = False,
) -> _ImportType:
    """
    Lazily imports a string with caching to avoid repeated imports
    """
    global _imported_strings
    if dotted_path not in _imported_strings:
        _imported_strings[dotted_path] = import_string(dotted_path, is_module = is_module, allow_module = allow_module)
    return _imported_strings[dotted_path]


@functools.lru_cache()
def import_function(func: Union[str, Callable]) -> Callable:
    """
    Imports a function from a string
    """
    return func if callable(func) else lazy_import(func)


def validate_callable(value: Optional[Union[str, Callable]]) -> Optional[Callable]:
    """
    Validates if the value is a callable
    """
    if value is None: return None
    return lazy_import(value) if isinstance(value, str) else value


def is_coro_func(obj, func_name: str = None):
    """
    This is probably in the library elsewhere but returns bool
    based on if the function is a coro
    """
    try:
        if inspect.iscoroutinefunction(obj): return True
        if inspect.isawaitable(obj): return True
        if func_name and hasattr(obj, func_name) and inspect.iscoroutinefunction(getattr(obj, func_name)):
            return True
        return bool(hasattr(obj, '__call__') and inspect.iscoroutinefunction(obj.__call__))

    except Exception:
        return False


def lazy_function(
    validator: Callable,
    function: Callable,
    *args,
    **kwargs,
):
    """
    Creates an empty function wrapper
    args:
        validator: function to validate the arguments
        func: function to call
        
    """
    def wrapper_func(func):
        if not validator():
            return func
        
        if is_coro_func(func):
            @functools.wraps(func)
            async def wrapped_func(*args, **kwargs):
                return await function(*args, **kwargs)
        
        else:
            @functools.wraps(func)
            def wrapped_func(*args, **kwargs):
                return function(*args, **kwargs)
        return wrapped_func
    return wrapper_func



def get_obj_class_name(obj: Any, is_parent: Optional[bool] = None) -> str:
    """
    Returns the module name + class name of an object

    args:
        obj: the object to get the class name of
        is_parent: if True, then it treats the object as unitialized and gets the class name of the parent
    """
    if is_parent is None: is_parent = inspect.isclass(obj)
    if is_parent: return f'{obj.__module__}.{obj.__name__}'
    return f'{obj.__class__.__module__}.{obj.__class__.__name__}'

def get_function_name(func: Callable) -> str:
    """
    Returns the module name + function name of a function
    """
    func = inspect.unwrap(func)
    return f'{func.__module__}.{func.__name__}'

def extract_obj_init_kwargs(obj: object) -> List[str]:
    """
    Extracts the kwargs that are valid for an object
    """
    global _valid_class_init_kwarg
    obj_name = get_obj_class_name(obj)
    if obj_name not in _valid_class_init_kwarg:
        argspec = inspect.getfullargspec(obj.__init__)
        _args = list(argspec.args)
        _args.extend(iter(argspec.kwonlyargs))
        # Check if subclass of Connection
        if hasattr(obj, "__bases__"):
            for base in obj.__bases__:
                _args.extend(extract_obj_init_kwargs(base))
        _valid_class_init_kwarg[obj_name] = list(set(_args))
    return _valid_class_init_kwarg[obj_name]
