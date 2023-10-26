import json
import inspect
from lazyops.utils.helpers import is_coro_func
from typing import Callable, Optional, List


def parse_to_list(value: Optional[str] = None) -> Optional[List[str]]:
    """
    Parses a string to a list
    """
    if value is None: return None
    if '[' in value and ']' in value: 
        if '"' in value or "'" in value:
            return json.loads(value)
        value = value.replace('[', '').replace(']', '')
    return next(
        (
            [v.strip() for v in value.split(sep) if v.strip()]
            for sep in [',', ';', '|']
            if sep in value
        ),
        [value],
    )


def create_function_wrapper(function: Callable):
    """
    Creates a function wrapper as a decorator for fastapi
    """
    def inner_wrapper(handler: Callable):
        """
        The inner wrapper
        """
        async def wrapper(*args, **kwargs):
            if is_coro_func(function):
                await function(*args, **kwargs)
            else:
                function(*args, **kwargs)
            return await handler(*args, **kwargs)

        wrapper.__signature__ = inspect.Signature(
            parameters = [
                # Use all parameters from handler
                *inspect.signature(handler).parameters.values(),

                # Skip *args and **kwargs from wrapper parameters:
                *filter(
                    lambda p: p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD),
                    inspect.signature(wrapper).parameters.values()
                )
            ],
            return_annotation = inspect.signature(handler).return_annotation,
        )

        return wrapper
    return inner_wrapper


def create_post_function_hook_wrapper(function: Callable):
    """
    Creates a function wrapper that executes after the function
    """

    def inner_wrapper(handler: Callable):
        """
        The inner wrapper
        """
        async def wrapper(*args, **kwargs):
            result = await handler(*args, **kwargs)
            if is_coro_func(function): await function(result, *args, **kwargs)
            else: function(result, *args, **kwargs)
            return result
        
        return wrapper
    
    return inner_wrapper

        