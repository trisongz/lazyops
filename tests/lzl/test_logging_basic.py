import logging

from lzl.logging import (
    add_api_log_filters,
    get_logger,
    null_logger,
    register_logger_module,
    set_global_muted,
)
from lzl.logging.state import is_global_muted, is_registered_logger_module


def test_get_logger_returns_same_instance() -> None:
    first = get_logger("tests.logging.module", level="INFO")
    second = get_logger("tests.logging.module")
    assert first is second


def test_register_logger_module_marks_name() -> None:
    register_logger_module("tests.logging.another")
    assert is_registered_logger_module("tests.logging.another.submodule")


def test_set_global_muted_toggles_flag() -> None:
    set_global_muted(True)
    assert is_global_muted() is True
    set_global_muted(False)
    assert is_global_muted() is False


def test_add_api_log_filters_blocks_configured_routes() -> None:
    logger_name = "tests.logging.api"
    target_logger = logging.getLogger(logger_name)
    original_filters = list(target_logger.filters)
    for flt in original_filters:
        target_logger.removeFilter(flt)

    add_api_log_filters(modules=logger_name, routes="/healthz")

    new_filters = [flt for flt in target_logger.filters if flt not in original_filters]
    assert new_filters, "expected add_api_log_filters to attach at least one filter"

    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="GET %s",
        args=("/healthz",),
        exc_info=None,
    )
    assert any(
        (flt.filter(record) if hasattr(flt, "filter") else flt(record)) is False
        for flt in new_filters
    )

    for flt in new_filters:
        target_logger.removeFilter(flt)
    for flt in original_filters:
        target_logger.addFilter(flt)


def test_null_logger_invokes_hooks() -> None:
    captured: list[str] = []

    null_logger.log("INFO", "hello", hook=captured.append)
    null_logger.trace("trace message", hook=captured.append)

    assert any("hello" in entry for entry in captured)
    assert any("trace message" in entry for entry in captured)
