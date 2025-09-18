from __future__ import annotations

"""Shared state and registration helpers for LazyOps logging."""

import functools
import logging
import threading
import typing as t

from .utils import extract_module_name

if t.TYPE_CHECKING:
    from logging import LogRecord

_registered_logger_modules: set[str] = set()
_module_name_mapping: dict[str, str] = {}
_module_name_mapping_relative: dict[str, bool] = {}

_is_global_muted: bool | None = None


def set_global_muted(muted: bool) -> None:
    """Toggle a process-wide muted flag checked by LazyOps loggers."""

    global _is_global_muted
    _is_global_muted = muted


def is_global_muted() -> bool:
    """Return ``True`` when the global mute flag is enabled."""

    return bool(_is_global_muted)


def register_logger_module(module: str) -> None:
    """Record ``module`` as having an explicit LazyOps logger configured."""

    _registered_logger_modules.add(extract_module_name(module))


@functools.lru_cache(maxsize=1000)
def is_registered_logger_module(name: str) -> bool:
    """Return ``True`` when ``name`` (or its root) has been registered."""

    module_name = extract_module_name(name)
    return module_name in _registered_logger_modules


def register_module_name(module_name: str, module: str, is_relative: bool = False) -> None:
    """Store a friendly mapping used when patching log records."""

    _module_name_mapping[module_name] = module
    _module_name_mapping_relative[module_name] = is_relative


def run_record_patching_hook(record: t.Union[logging.LogRecord, dict[str, t.Any]]) -> t.Union[logging.LogRecord, dict[str, t.Any]]:
    """Attach resolved module names to Loguru records when available."""

    if record["name"] in _module_name_mapping:
        record["extra"]["module_name"] = _module_name_mapping[record["name"]]
    elif any(record["name"].startswith(module) for module in _module_name_mapping):
        matching_module = next(
            (module for module in _module_name_mapping if record["name"].startswith(module)),
            None,
        )
        if matching_module and _module_name_mapping_relative.get(matching_module, False):
            module = record["name"].replace(matching_module, _module_name_mapping[matching_module]).strip()
            register_module_name(record["name"], module, is_relative=False)
            record["extra"]["module_name"] = _module_name_mapping[record["name"]]
    return record


def add_api_log_filters(
    modules: t.Optional[t.Union[t.Sequence[str], str]] = ("gunicorn", "uvicorn"),
    routes: t.Optional[t.Union[t.Sequence[str], str]] = ("/healthz",),
    status_codes: t.Optional[t.Union[t.Sequence[int], int]] = None,
    verbose: bool = False,
) -> None:  # sourcery skip: default-mutable-arg
    """Attach filters to common HTTP server loggers to hide noisy endpoints."""

    modules_list = [modules] if isinstance(modules, str) else list(modules or [])
    routes_list = [routes] if isinstance(routes, str) else list(routes or [])
    status_list = [status_codes] if isinstance(status_codes, int) else list(status_codes or [])

    def filter_api_record(record: logging.LogRecord) -> bool:
        if routes_list:
            for route in routes_list:
                if route in record.args:
                    return False
        if status_list:
            for sc in status_list:
                if sc in record.args:
                    return False
        return True

    for module in modules_list:
        target = module
        if module == "gunicorn":
            target = "gunicorn.glogging.Logger"
        elif module == "uvicorn":
            target = "uvicorn.logging.Logger"
        api_logger = logging.getLogger(target)
        from .main import default_logger

        if verbose:
            default_logger.info(
                "Adding API filters to %s for routes=%s status_codes=%s",
                target,
                routes_list or None,
                status_list or None,
            )
        api_logger.addFilter(filter_api_record)


__all__ = [
    "set_global_muted",
    "is_global_muted",
    "register_logger_module",
    "is_registered_logger_module",
    "register_module_name",
    "run_record_patching_hook",
    "add_api_log_filters",
]
