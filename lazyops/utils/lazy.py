from __future__ import annotations

# Lazily handle stuff
import functools
import inspect
from typing import Any, Dict, Callable, Union, Optional, Type, TYPE_CHECKING


if TYPE_CHECKING:
    from lazyops.types import BaseModel


# Lazy Importing
_imported_strings: Dict[str, Any] = {}


def import_string(dotted_path: str) -> Any:
    """
    Taken from pydantic.utils.
    """
    from importlib import import_module
    try:
        module_path, class_name = dotted_path.strip(' ').rsplit('.', 1)
    except ValueError as e:
        raise ImportError(f'"{dotted_path}" doesn\'t look like a module path') from e

    module = import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as e:
        raise ImportError(f'Module "{module_path}" does not define a "{class_name}" attribute') from e


def lazy_import(
    dotted_path: str
) -> Any:
    """
    Lazily imports a string with caching to avoid repeated imports
    """
    global _imported_strings
    if dotted_path not in _imported_strings:
        _imported_strings[dotted_path] = import_string(dotted_path)
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


def fetch_property(
    obj: Union[Type['BaseModel'], Dict],
    key: str,
    default: Optional[Any] = None
):  
    """
    Fetches a property from a dict or object
    """
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


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
