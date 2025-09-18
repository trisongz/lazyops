"""Miscellaneous helper utilities used by :mod:`lzl.pool`."""

import asyncio
import contextlib


def is_in_async_loop() -> bool:
    """Return ``True`` when called from within a running event loop."""

    with contextlib.suppress(Exception):
        return asyncio.get_event_loop().is_running()
    return False
