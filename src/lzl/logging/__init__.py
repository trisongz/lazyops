from __future__ import annotations

"""Public façade for LazyOps logging helpers.

The logging package wraps Loguru with project-specific defaults, colour
configuration, and filtering utilities.  This module re-exports the key entry
points so downstream consumers can import everything from a single location –
particularly useful when generating documentation via Mintlify.
"""

from .static import (
    DEFAULT_STATUS_COLORS,
    QUEUE_STATUS_COLORS,
    STATUS_COLOR,
    FALLBACK_STATUS_COLOR,
    DEFAULT_FUNCTION_COLOR,
    DEFAULT_CLASS_COLOR,
    RESET_COLOR,
    LOGLEVEL_MAPPING,
    REVERSE_LOGLEVEL_MAPPING,
    COLORED_MESSAGE_MAP,
)
from .state import (
    register_logger_module,
    is_registered_logger_module,
    add_api_log_filters,
    set_global_muted,
)
from .main import (
    NullLogger,
    Logger,
    create_default_logger,
    change_logger_level,
    get_logger,
    default_logger,
    null_logger,
    logger,
)

__all__ = [
    "DEFAULT_STATUS_COLORS",
    "QUEUE_STATUS_COLORS",
    "STATUS_COLOR",
    "FALLBACK_STATUS_COLOR",
    "DEFAULT_FUNCTION_COLOR",
    "DEFAULT_CLASS_COLOR",
    "RESET_COLOR",
    "LOGLEVEL_MAPPING",
    "REVERSE_LOGLEVEL_MAPPING",
    "COLORED_MESSAGE_MAP",
    "register_logger_module",
    "is_registered_logger_module",
    "add_api_log_filters",
    "set_global_muted",
    "NullLogger",
    "Logger",
    "create_default_logger",
    "change_logger_level",
    "get_logger",
    "default_logger",
    "null_logger",
    "logger",
]
