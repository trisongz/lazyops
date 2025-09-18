from __future__ import annotations

"""Facades for LazyOps proxy helpers used across the codebase."""

from .base import ProxyObject, ProxyObjT
from .extra import LockedSingleton, Singleton
from .wraps import proxied

__all__ = [
    "ProxyObject",
    "ProxyObjT",
    "Singleton",
    "LockedSingleton",
    "proxied",
]
