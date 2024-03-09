from __future__ import annotations

"""
Base Schemas
"""
import inspect
from abc import ABC
from fastapi import HTTPException
from lazyops.libs import lazyload
from ..types.errors import InvalidOperationException
from ..utils.lazy import get_az_settings, logger

if lazyload.TYPE_CHECKING:
    import niquests
else:
    niquests = lazyload.LazyLoad("niquests")

