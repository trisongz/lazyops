from __future__ import annotations

"""Helpers for managing IO-related registries.

This module centralises the lazily-evaluated serializers and the lifecycle of
temporary files.  Documenting the behaviour here helps keep downstream tooling
aware of the implicit global state that exists around serializer lookups and
file clean-up hooks.
"""

import contextlib
import typing as t

from lzl.proxied import ProxyObject

if t.TYPE_CHECKING:
    from lzl.io import FileLike
    from lzl.io.ser import JsonSerializer

__all__ = [
    "get_json_ser",
    "get_jsonb_ser",
    "json_ser",
    "jsonb_ser",
    "add_file_to_cleanup",
    "cleanup_files_on_exit",
    "acleanup_files_on_exit",
]


def get_json_ser(*args: t.Any, **kwargs: t.Any) -> "JsonSerializer":
    """Return the canonical JSON serializer instance.

    The function intentionally accepts arbitrary positional and keyword
    arguments so that it can be used as a drop-in replacement for serializer
    factories throughout the codebase.  Any provided values are ignored because
    the serializer configuration is controlled globally via LazyOps settings.
    """

    from lzl.io.ser import get_serializer

    return get_serializer("json")


def get_jsonb_ser(*args: t.Any, **kwargs: t.Any) -> "JsonSerializer":
    """Return a JSON serializer that emits byte values (`jsonb`).

    Similar to :func:`get_json_ser`, the arguments are accepted purely for API
    compatibility.  The serializer is configured to enforce byte output so it
    can be used with backends expecting binary payloads.
    """

    from lzl.io.ser import get_serializer

    return get_serializer("json", enforce_byte_value=True)


jsonb_ser: "JsonSerializer" = ProxyObject(obj_getter=get_jsonb_ser)
json_ser: "JsonSerializer" = ProxyObject(obj_getter=get_json_ser)

_registered_file_aexit: bool = False
_registered_file_exit: bool = False

_created_tempfiles: t.Set["FileLike"] = set()


def cleanup_files_on_exit() -> None:
    """Remove temporary files that were created through LazyOps IO helpers."""

    while _created_tempfiles:
        file_path = _created_tempfiles.pop()
        with contextlib.suppress(Exception):
            file_path.unlink(missing_ok=True)


async def acleanup_files_on_exit() -> None:
    """Asynchronous variant of :func:`cleanup_files_on_exit`."""

    while _created_tempfiles:
        file_path = _created_tempfiles.pop()
        with contextlib.suppress(Exception):
            await file_path.aunlink(missing_ok=True)


def register_file_exit(*_args: t.Any, **_kwargs: t.Any) -> None:
    """Register the clean-up hooks exactly once for the process lifecycle."""

    global _registered_file_exit, _registered_file_aexit
    if not _registered_file_exit:
        import atexit

        atexit.register(cleanup_files_on_exit)
        _registered_file_exit = True
    # TODO: add async clean-up hook when aioexit dependency is restored.
    _registered_file_aexit = _registered_file_aexit or False


def add_file_to_cleanup(file: "FileLike") -> None:
    """Track a file so it is safely removed when the interpreter exits."""

    register_file_exit()
    _created_tempfiles.add(file)
