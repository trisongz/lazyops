from __future__ import annotations

"""Utility helpers that underpin LazyOps lazy-loading features."""

import functools
import importlib
import inspect
import typing as t
from types import ModuleType

_ImportedObject = t.TypeVar("_ImportedObject")
_FunctionT = t.TypeVar("_FunctionT", bound=t.Callable[..., t.Any])
_ModuleT = t.TypeVar("_ModuleT", bound=ModuleType)
_ObjectT = t.TypeVar("_ObjectT")

_Importable = t.Union[_ModuleT, _ObjectT, _FunctionT]

_imported_strings: dict[str, t.Any] = {}
_valid_class_init_kwarg: dict[str, list[str]] = {}


class ImportFromStringError(Exception):
    """Raised when ``import_from_string`` cannot resolve the requested object."""


def import_from_string(import_str: t.Any) -> t.Any:
    """Resolve ``"module:attribute"`` style import strings.

    The function mirrors patterns popularised by frameworks such as Celery and
    Pydantic.  When ``import_str`` is not a string the value is returned
    unchanged to preserve legacy call sites.
    """

    if not isinstance(import_str, str):
        return import_str

    module_str, _, attrs_str = import_str.partition(":")
    if not module_str or not attrs_str:
        message = 'Import string "{import_str}" must be in format "<module>:<attribute>".'
        raise ImportFromStringError(message.format(import_str=import_str))

    try:
        module = importlib.import_module(module_str)
    except ImportError as exc:  # pragma: no cover - passthrough for clarity
        if exc.name != module_str:
            raise exc
        message = 'Could not import module "{module_str}".'
        raise ImportFromStringError(message.format(module_str=module_str)) from exc

    instance: t.Any = module
    try:
        for attr_str in attrs_str.split("."):
            instance = getattr(instance, attr_str)
    except AttributeError as exc:
        message = 'Attribute "{attrs_str}" not found in module "{module_str}".'
        raise ImportFromStringError(
            message.format(attrs_str=attrs_str, module_str=module_str)
        ) from exc

    return instance


def import_string(
    dotted_path: str,
    is_module: bool | None = None,
    allow_module: bool | None = False,
) -> _Importable:
    """Import a dotted path and return either the module or attribute requested."""

    if is_module:
        return importlib.import_module(dotted_path)

    try:
        module_path, class_name = dotted_path.strip().rsplit(".", 1)
    except ValueError as exc:
        raise ImportError(f'"{dotted_path}" doesn\'t look like a module path') from exc

    module = importlib.import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        if allow_module:
            return module
        raise ImportError(
            f'Module "{module_path}" does not define a "{class_name}" attribute'
        ) from exc


def lazy_import(
    dotted_path: str,
    is_module: bool | None = None,
    allow_module: bool | None = False,
) -> _Importable:
    """Import ``dotted_path`` once and cache the resolved object for reuse."""

    if dotted_path not in _imported_strings:
        _imported_strings[dotted_path] = import_string(
            dotted_path,
            is_module=is_module,
            allow_module=allow_module,
        )
    return _imported_strings[dotted_path]


@functools.lru_cache()
def import_function(func: str | t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    """Return a callable from either a dotted import path or the callable itself."""

    return func if callable(func) else t.cast(t.Callable[..., t.Any], lazy_import(func))


def validate_callable(value: str | t.Callable[..., t.Any] | None) -> t.Callable[..., t.Any] | None:
    """Return a callable object when ``value`` is either ``None`` or a string."""

    if value is None:
        return None
    return lazy_import(value) if isinstance(value, str) else value


def is_coro_func(obj: t.Any, func_name: str | None = None) -> bool:
    """Return ``True`` when ``obj`` or ``obj.func_name`` is awaitable."""

    try:
        if inspect.iscoroutinefunction(obj) or inspect.isawaitable(obj):
            return True
        if func_name and hasattr(obj, func_name):
            maybe_func = getattr(obj, func_name)
            if inspect.iscoroutinefunction(maybe_func):
                return True
        return bool(hasattr(obj, "__call__") and inspect.iscoroutinefunction(obj.__call__))
    except Exception:  # pragma: no cover - mirrors legacy lenient behaviour
        return False


def lazy_function(
    validator: t.Callable[[], bool],
    function: t.Callable[..., t.Any],
    *args: t.Any,
    **kwargs: t.Any,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    """Decorator factory that defers wrapper creation until validation passes."""

    def wrapper_func(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        if not validator():  # pragma: no cover - guarded branch maintained for compatibility
            return func

        if is_coro_func(func):
            @functools.wraps(func)
            async def wrapped_func(*f_args: t.Any, **f_kwargs: t.Any) -> t.Any:
                return await function(*f_args, **f_kwargs)
        else:
            @functools.wraps(func)
            def wrapped_func(*f_args: t.Any, **f_kwargs: t.Any) -> t.Any:
                return function(*f_args, **f_kwargs)
        return wrapped_func

    return wrapper_func


def get_obj_class_name(obj: t.Any, is_parent: bool | None = None) -> str:
    """Return ``module.Class`` for an object or class."""

    if is_parent is None:
        is_parent = inspect.isclass(obj)
    if is_parent:
        return f"{obj.__module__}.{obj.__name__}"
    return f"{obj.__class__.__module__}.{obj.__class__.__name__}"


def get_function_name(func: t.Callable[..., t.Any]) -> str:
    """Return ``module.function`` for ``func`` after unwrapping decorators."""

    func = inspect.unwrap(func)
    return f"{func.__module__}.{func.__name__}"


def extract_obj_init_kwargs(obj: t.Any) -> list[str]:
    """Return constructor keyword arguments for ``obj`` including base classes."""

    obj_name = get_obj_class_name(obj, is_parent=None)
    if obj_name not in _valid_class_init_kwarg:
        argspec = inspect.getfullargspec(obj.__init__)  # type: ignore[attr-defined]
        params: list[str] = list(argspec.args)
        params.extend(iter(argspec.kwonlyargs))
        if hasattr(obj, "__bases__"):
            for base in obj.__bases__:
                params.extend(extract_obj_init_kwargs(base))
        _valid_class_init_kwarg[obj_name] = list(set(params))
    return _valid_class_init_kwarg[obj_name]
