from __future__ import annotations

# Lazily handle stuff
import sys
import copy
import pathlib
import inspect
import functools
import importlib.util
from typing import Any, Dict, Callable, Union, Optional, Type, TypeVar, List, Tuple, cast, TYPE_CHECKING
from types import ModuleType

if TYPE_CHECKING:
    from lazyops.types import BaseModel
    from aiokeydb import KeyDBSession


# Lazy Importing
_imported_strings: Dict[str, Any] = {}


def import_string(dotted_path: str, is_module: Optional[bool] = None, allow_module: Optional[bool] = False) -> Any:
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
) -> Any:
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


_valid_class_init_kwarg: Dict[str, List[str]] = {}

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



MT = TypeVar("MT", bound="BaseModel")

_extracted_base_model_kws: Dict[str, List[str]] = {}

def extract_base_model_kws(
    model: MT,
    kwargs: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Extracts the kwargs from the resource and returns the kwargs and the model kwargs
    """
    global _extracted_base_model_kws

    base_model_name = f"{model.__module__}.{model.__name__}"
    if base_model_name not in _extracted_base_model_kws:
        from lazyops.types.models import get_pyd_field_names
        resource_kws = get_pyd_field_names(model)
        # resource_kws = list(model.__fields__.keys())
        _extracted_base_model_kws[base_model_name] = resource_kws
    model_kwargs = {
        key: kwargs.pop(key) for key in kwargs if key in _extracted_base_model_kws[base_model_name]
    }
    return kwargs, model_kwargs


# Lazy KeyDB Sessions

_keydb_sessions: Dict[str, 'KeyDBSession'] = {}
_keydb_enabled: Optional[bool] = None

def get_keydb_enabled() -> bool:
    """
    Gets whether or not keydb is enabled
    """
    if _keydb_enabled is None:
        get_keydb_session(validate_active = True)
    return _keydb_enabled

def get_keydb_session(
    name: Optional[str] = "default",
    validate_active: Optional[bool] = None,
    **kwargs
) -> Optional["KeyDBSession"]:
    """
    Get the KeyDB Session
    """
    global _keydb_sessions, _keydb_enabled
    if not _keydb_sessions.get(name):
        try:
            from aiokeydb import KeyDBClient
            _keydb_sessions[name] = KeyDBClient.get_session(name = name, verbose = False, **kwargs)
        except Exception as e:
            from .logs import logger
            logger.warning('KeyDB is not available. Disabling')
            _keydb_enabled = False
            return None
    if validate_active and _keydb_enabled is None:
        try:
            _keydb_enabled = _keydb_sessions[name].ping()
        except Exception as e:
            from .logs import logger
            logger.warning(f"KeyDB Session {name} is not active: {e}")
            _keydb_enabled = False
    if validate_active and not _keydb_enabled:
        return None
    return _keydb_sessions[name]


"""
Lazily Handle Classes and Imports
"""

def import_code(
    code: str,
    add_to_sys: Optional[bool] = True,
    name: Optional[str] = None,
    ref: Optional[str] = None,
    module_name: Optional[str] = None,
) -> ModuleType:
    """
    Import dynamically generated code as a module. code is the
    object containing the code (a string, a file handle or an
    actual compiled code object, same types as accepted by an
    exec statement). The name is the name to give to the module,
    and the final argument says wheter to add it to sys.modules
    or not. If it is added, a subsequent import statement using
    name will return this module. If it is not added to sys.modules
    import will try to load it in the normal fashion. 
    """
    assert name or ref, 'Must provide either a name or a ref'
    name = name or ref
    module = ModuleType(name)
    module.__module__ = module_name or 'lazyops.types.dynamic'
    exec(code, module.__dict__)
    if add_to_sys:
        sys.modules[name] = module
    return module


DynamicT = TypeVar('DynamicT')
_DynamicClasses: Dict[str, DynamicT] = {}


def create_new_class(
    code: str,
    cls: DynamicT,
    ref: Optional[str] = None,
    module_name: Optional[str] = None,
) -> DynamicT:
    """
    Create a new class
    """
    global _DynamicClasses
    module_name = module_name or "lazyops.types.dynamic"
    from .serialization import create_hash_key
    code_hash = create_hash_key(kwargs = {'ref': ref, 'cls': cls, 'module_name': module_name, 'code': code})
    if code_hash in _DynamicClasses:
        return _DynamicClasses[code_hash]
    run_code = import_code(code, add_to_sys = True, ref = ref or cls.__name__, module_name = module_name)
    new_cls = copy.deepcopy(cls)
    for prop_or_func in dir(run_code):
        setattr(new_cls, prop_or_func, getattr(run_code, prop_or_func))
    _DynamicClasses[code_hash] = new_cls
    return new_cls


def load_module_from_file(
    file: Union[str, pathlib.Path], 
    module_name: str,
    add_to_sys: Optional[bool] = False,
) -> ModuleType:
    """
    Loads a module from a file
    """
    if isinstance(file, str):
        file = pathlib.Path(file)
    spec = importlib.util.spec_from_file_location(module_name, file.as_posix())
    module = importlib.util.module_from_spec(spec)
    if add_to_sys: sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def import_from_file(
    file: Union[str, pathlib.Path],
    cls_name: str,
) -> ModuleType:
    """
    Import a file
    """
    return load_module_from_file(file = file, module_name = cls_name)

def create_new_class_from_file(
    file: Union[str, pathlib.Path],
    cls_name: str,
    cls: DynamicT,
) -> DynamicT:
    """
    Import a file and create a new class
    """

    module_spec = load_module_from_file(file = file, module_name = cls_name)
    cls_spec = getattr(module_spec, cls_name)
    cls_spec = cast(cls, cls_spec)
    return cls_spec