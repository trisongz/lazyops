from __future__ import annotations

"""Convenience exports for LazyOps lazy-loading utilities.

The package provides a small façade around :class:`LazyLoad` and supporting
helpers so downstream modules can defer importing heavy dependencies until
absolutely necessary.  Behaviour matches the original implementation, but the
public interface is now documented for automated reference generation.
"""

import typing as t

from .main import LazyLoad, lazy_load, load
from .wrappers import lazy_function_wrapper
from .utils import (
    import_from_string,
    import_function,
    import_string,
    is_coro_func,
    lazy_function,
    lazy_import,
    validate_callable,
)

__all__ = [
    "LazyLoad",
    "lazy_load",
    "load",
    "lazy_function_wrapper",
    "lazy_import",
    "lazy_function",
    "is_coro_func",
    "import_string",
    "import_function",
    "import_from_string",
    "validate_callable",
    "TYPE_CHECKING",
]

TYPE_CHECKING = t.TYPE_CHECKING
