from __future__ import annotations

"""
This module should generally not be used directly. 
It's only used when the module is known to be installed to provide
a consistent interface for the user.
"""

from lzl import load
load.LazyLoad("niquests", install_missing = True).__load__()
from niquests.exceptions import (
    ConnectionError,
    ConnectTimeout,
    FileModeWarning,
    HTTPError,
    JSONDecodeError,
    ReadTimeout,
    RequestException,
    RequestsDependencyWarning,
    Timeout,
    TooManyRedirects,
    URLRequired,
)


__all__ = [
    "ConnectionError",
    "ConnectTimeout",
    "FileModeWarning",
    "HTTPError",
    "JSONDecodeError",
    "ReadTimeout",
    "RequestException",
    "RequestsDependencyWarning",
    "Timeout",
    "TooManyRedirects",
    "URLRequired",
]