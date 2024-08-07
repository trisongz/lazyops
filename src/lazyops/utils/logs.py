from __future__ import annotations

"""
Rework v3 of the logger

- Now imported from `lazyops.libs.logging` 
"""

from lazyops.libs.logging import (
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

    NullLogger,
    Logger,

    InterceptHandler,
    LoggerFormatter,

    register_logger_module,
    is_registered_logger_module,
    create_default_logger,

    get_logger,
    default_logger,
    null_logger,
    logger,

    change_logger_level,
    add_api_log_filters,
)