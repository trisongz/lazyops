"""
Base Import Handler
"""
import typing
import functools
from lazyops.utils.logs import default_logger as logger
from lazyops.utils.lazylib import LazyLib
from lazyops.utils.helpers import is_coro_func

def resolve_missing(
    modules: typing.Union[str, typing.List],
    required: bool = True,
):
    if not isinstance(modules, list):
        modules = [modules]
    kind = 'required' if required else 'optionally required'
    logger.info(f"{', '.join(modules)} are {kind}. Installing...")
    for module in modules:
        LazyLib.import_lib(module)

    
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