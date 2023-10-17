"""
Base Import Handler
"""
import typing
import functools
import pathlib
import importlib.util
from lazyops.utils.logs import default_logger as logger
from lazyops.utils.lazylib import LazyLib
from lazyops.utils.helpers import is_coro_func

def resolve_missing(
    modules: typing.Union[str, typing.List],
    packages: typing.Union[str, typing.List] = None,
    required: bool = True,
):
    if not isinstance(modules, list):
        modules = [modules]
    if packages is not None and not isinstance(packages, list):
        packages = [packages]
    elif packages is None:
        packages = modules
    kind = 'required' if required else 'optionally required'
    logger.info(f"{', '.join(modules)} are {kind}. Installing...")
    for module, pkg in zip(modules, packages):
        LazyLib.import_lib(module, pkg)


def resolve_missing_custom(
    modules: typing.Union[str, typing.List],
    packages: typing.Union[str, typing.List] = None,
    required: bool = True,
):
    """
    Handles custom use cases like `torch` where we need to
    have a extra index to install from
    """
    if not isinstance(modules, list):
        modules = [modules]
    if packages is not None and not isinstance(packages, list):
        packages = [packages]
    elif packages is None:
        packages = modules
    
    module_names = [module.split(' ', 1)[0] for module in modules]
    kind = 'required' if required else 'optionally required'
    logger.info(f"{', '.join(module_names)} are {kind}. Installing...")
    for module, pkg in zip(modules, packages):
        module_name = LazyLib.get_requirement(module, True)
        if LazyLib.is_available(module_name):
            continue
        LazyLib.install_library(pkg)

    
def require_missing_wrapper(
    resolver: typing.Callable,
    func: typing.Callable,
    **resolver_kwargs,
):
    """
    Helper function to wrap the resolve async or sync funcs
    """
    if is_coro_func(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            resolver(**resolver_kwargs)
            return await func(*args, **kwargs)
    else:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            resolver(**resolver_kwargs)
            return func(*args, **kwargs)

    return wrapper


@functools.lru_cache()
def get_module_path(
    module_name: str, 
    **kwargs
) -> pathlib.Path:
    """
    Get the path to the module.

    args:
        module_name: name of the module to import from (e.g. 'lazyops')
    
    Use it like this:

    >>> get_module_path('lazyops')
    """
    module_spec = importlib.util.find_spec(module_name)
    if not module_spec:
        raise ValueError(f"Module {module_name} not found")
    
    for path in module_spec.submodule_search_locations:
        module_path = pathlib.Path(path)
        if module_path.exists(): return module_path
    
    raise ValueError(f"Module {module_name} cant be found in the path")

