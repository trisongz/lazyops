
import random
import inspect
import backoff
import functools
import aiohttpx
from typing import Callable, List, Optional, TypeVar, TYPE_CHECKING

try:
    from async_lru import alru_cache
except ImportError:
    import sys
    if sys.version_info >= (3, 8):
        from typing import ParamSpec
    else:
        from typing_extensions import ParamSpec

    RT = TypeVar('RT')
    PT = ParamSpec('PT')

    def alru_cache(*args, **kwargs):
        def decorator(func: Callable[PT, RT]) -> Callable[PT, RT]:
            return func
        return decorator

        

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
    # from .logs import logger
    # logger.info(f"Creating build name function for {base_name}")

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

        # logger.info(f"Failed to find a special name for {base_name}.{func_name}")
        return f"{base_name}.{func_name}"
    
    return build_name_func


@functools.lru_cache(500)
def extract_domain(url: str) -> str:
    """
    Returns the domain
    """
    try:
        import tldextract
        return tldextract.extract(url).registered_domain
    except ImportError:
        from urllib.parse import urlparse
        return urlparse(url).netloc

@functools.lru_cache()
def get_root_domain(url: str, attempts: Optional[int] = None) -> str:
    """
    Returns the root domain after redirection
    """
    if not url.startswith('http'): url = f'https://{url}'
    try:
        with aiohttpx.Client(follow_redirects = True, verify = False) as client:
            r = client.get(url, timeout = 5)
        r.raise_for_status()
        return str(r.url).rstrip('/')
    except (aiohttpx.ConnectTimeout, aiohttpx.ReadTimeout) as e:
        return url
    except aiohttpx.HTTPStatusError as e:
        return str(e.response.url).rstrip('/') if e.response.status_code < 500 else url
    except Exception as e:
        attempts = attempts + 1 if attempts else 1
        if attempts > 2:
            return None
        new_url = f'https://{extract_domain(url)}'
        return get_root_domain(new_url, attempts = attempts)


@alru_cache(maxsize=1200)
async def aget_root_domain(url: str, attempts: Optional[int] = None) -> str:
    """
    Returns the root domain after redirection
    """
    if not url.startswith('http'): url = f'https://{url}'
    try:
        async with aiohttpx.Client(follow_redirects = True, verify = False) as client:
            r = await client.async_get(url, timeout = 5)
        r.raise_for_status()
        return str(r.url).rstrip('/')
    except (aiohttpx.ConnectTimeout, aiohttpx.ReadTimeout) as e:
        return url
    except aiohttpx.HTTPStatusError as e:
        return str(e.response.url).rstrip('/') if e.response.status_code < 500 else url
    except Exception as e:
        attempts = attempts + 1 if attempts else 1
        if attempts > 2:
            return None
        new_url = f'https://{extract_domain(url)}'
        return await aget_root_domain(new_url, attempts = attempts)


def fatal_http_exception(exc):
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

    
