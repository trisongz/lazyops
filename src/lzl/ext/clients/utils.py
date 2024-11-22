from __future__ import annotations

"""
Client Utilities
"""

import inspect
import backoff
import functools
import random
from lzl import load
from typing import Optional, Type, TypeVar, Union, Set, List, Any, Dict, Literal, Callable, TYPE_CHECKING

if load.TYPE_CHECKING:
    import aiohttpx
    from aiohttpx import HTTPStatusError
else:
    aiohttpx = load.LazyLoad("aiohttpx", install_missing=True)

def create_cachify_build_name_func(
    base_name: str,
    special_names: Optional[List[str]] = None,
    function_names: Optional[List[str]] = None,
    include_classname: Optional[bool] = True,
    include_http_methods: Optional[bool] = False,
) -> Callable[..., str]:
    """
    Creates a function that returns the build name
    """

    def build_name_func(func: Callable, *args, **kwargs) -> str:
        """
        Build the name function
        """
        nonlocal base_name
        func = inspect.unwrap(func)
        func_name = func.__qualname__ if include_classname else func.__name__

        if special_names:
            for name in special_names:
                if name in func_name.lower():
                    func_name = func_name.replace(f'a{name}_', '').replace(f'{name}_', '').replace('__', '_')
                    return f"{base_name}.{name}_{func_name}"
        
        if function_names:
            for name in function_names:
                if name in func_name.lower(): return f"{base_name}.{func_name}"
        
        if include_http_methods:
            for method in {'get', 'post', 'put', 'delete'}:
                if method in func_name.lower(): return f"{base_name}.{method}"
        return f"{base_name}.{func_name}"
    return build_name_func


def fatal_http_exception(exc: Union[Exception, 'HTTPStatusError']) -> bool:
    """
    Checks if the exception is fatal
    """
    if isinstance(exc, aiohttpx.HTTPStatusError):
        # retry on server errors and client errors
        # with 429 status code (rate limited),
        # don't retry on other client errors
        return (400 <= exc.response.status_code < 500) and exc.response.status_code != 429
    else:
        # retry on all other errors (eg. network)
        return False


http_retry_wrapper = functools.partial(
    backoff.on_exception,
    backoff.expo, 
    exception = Exception, 
    giveup = fatal_http_exception,
    factor = 5,
)

DefaultUserAgents = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.81",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.3",
]

def get_user_agent(*args, **kwargs) -> str:
    """
    Returns a user agent
    """
    try:
        from fake_useragent import UserAgent
        ua = UserAgent(*args, **kwargs)
        return ua.random
    except ImportError:
        return random.choice(DefaultUserAgents)

try:
    from browserforge.headers import HeaderGenerator
    _bheaders = True
    _bheader_gen: Optional[HeaderGenerator] = None
except ImportError:
    _bheaders = False
    _bheader_gen = None


def get_default_headers(browser: Optional[str] = 'chrome', **kwargs) -> Dict[str, str]:
    """
    Returns the default headers
    """
    global _bheader_gen
    if _bheaders:
        if _bheader_gen is None: _bheader_gen = HeaderGenerator()
        return _bheader_gen.generate(browser = browser, **kwargs)
    return {}

