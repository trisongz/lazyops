from __future__ import annotations

"""Utility helpers that extend :mod:`httpx` with LazyOps ergonomics."""

import asyncio
import contextlib
import functools
import inspect
import typing as t

import httpx

from httpx._exceptions import HTTPError, HTTPStatusError

from lzl import load
from lzl.types import lazyproperty

if load.TYPE_CHECKING:
    import bs4
    import backoff
else:
    bs4 = load.LazyLoad("bs4", install_missing=True)
    backoff = load.LazyLoad("backoff", install_missing=True)


def fatal_http_exception(exc: Exception | HTTPError) -> bool:
    """Return ``True`` when the exception should *not* be retried."""

    if isinstance(exc, HTTPStatusError):
        # Retry on 5xxs and rate limits; other client errors are considered fatal
        return (400 <= exc.response.status_code < 500) and exc.response.status_code != 429
    # Network errors are treated as transient
    return False


http_retry_wrapper = functools.partial(
    backoff.on_exception,
    backoff.expo,
    exception=Exception,
    giveup=fatal_http_exception,
    factor=5,
)


def raise_for_status(self: httpx.Response) -> None:
    """Mirror :meth:`httpx.Response.raise_for_status` with richer messages."""
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
        if resp_text:
            message += f'\nResponse Payload: {resp_text}'
    raise httpx.HTTPStatusError(message, request=request, response=self)


def is_coro_func(obj: t.Any, func_name: str | None = None) -> bool:
    """Return ``True`` if *obj* or its named attribute is awaitable."""
    try:
        if inspect.iscoroutinefunction(obj): return True
        if inspect.isawaitable(obj): return True
        if func_name and hasattr(obj, func_name) and inspect.iscoroutinefunction(getattr(obj, func_name)):
            return True
        return bool(hasattr(obj, '__call__') and inspect.iscoroutinefunction(obj.__call__))

    except Exception:
        return False

background_tasks: t.Set[asyncio.Task[t.Any]] = set()


def run_in_background(coro: t.Coroutine[t.Any, t.Any, t.Any]) -> None:
    """Schedule *coro* for execution without awaiting it immediately."""
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


# Monkey patching httpx.Response to add soup property
# that way it is only called when the property is accessed
# rather than on every request

@lazyproperty
def soup_property(self: httpx.Response) -> t.Any:
    """Create a lazily-evaluated ``BeautifulSoup`` view of the response body."""

    with contextlib.suppress(Exception):
        return bs4.BeautifulSoup(self.text, 'html.parser')
    return None


def wrap_soup_response(response: httpx.Response) -> httpx.Response:
    """Attach the :func:`soup_property` accessor to *response*'s class."""

    setattr(response.__class__, 'soup', soup_property)
    return response
