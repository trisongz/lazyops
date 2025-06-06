from __future__ import annotations

import httpx
import functools
import contextlib
import asyncio
import inspect
import typing as t
from lzl import load
from lzl.types import lazyproperty
from httpx._exceptions import HTTPError, HTTPStatusError

if load.TYPE_CHECKING:
    import bs4
    import backoff
else:
    bs4 = load.LazyLoad("bs4", install_missing=True)
    backoff = load.LazyLoad("backoff", install_missing=True)


def fatal_http_exception(exc: Exception | HTTPError) -> bool:
    """
    Checks if the exception is fatal
    """
    if isinstance(exc, HTTPStatusError):
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


def raise_for_status(self: 'httpx.Response') -> None:
    """
    Raise the `HTTPStatusError` if one occurred.
    """
    request = self._request
    if request is None:
        raise RuntimeError(
            "Cannot call `raise_for_status` as the request "
            "instance has not been set on this response."
        )

    if self.is_success:
        return

    if self.has_redirect_location:
        message = (
            "{error_type} '{0.status_code} {0.reason_phrase}' for url '{0.url}'\n"
            "Redirect location: '{0.headers[location]}'\n"
            "For more information check: https://httpstatuses.com/{0.status_code}"
        )
    else:
        message = (
            "{error_type} '{0.status_code} {0.reason_phrase}' for url '{0.url}'\n"
            "For more information check: https://httpstatuses.com/{0.status_code}"
        )

    status_class = self.status_code // 100
    error_types = {
        1: "Informational response",
        3: "Redirect response",
        4: "Client error",
        5: "Server error",
    }
    error_type = error_types.get(status_class, "Invalid status code")
    message = message.format(self, error_type=error_type)
    with contextlib.suppress(Exception):
        resp_text = self.text
        if resp_text: message += f'\nResponse Payload: {resp_text}'
    raise httpx.HTTPStatusError(message, request=request, response=self)


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

background_tasks = set()

def run_in_background(coro: t.Coroutine):
    """
    Runs a coroutine in the background
    """
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


# Monkey patching httpx.Response to add soup property
# that way it is only called when the property is accessed
# rather than on every request

@lazyproperty
def soup_property(self: 'httpx.Response'):
    with contextlib.suppress(Exception):
        return bs4.BeautifulSoup(self.text, 'html.parser')

def wrap_soup_response(response: httpx.Response) -> 'httpx.Response':
    setattr(response.__class__, 'soup', soup_property)
    return response
