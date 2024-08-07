"""
Seperated logging module for lazyops to prevent circular imports for 3rd party modules.
"""
from __future__ import annotations

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

