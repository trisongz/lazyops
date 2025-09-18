from __future__ import annotations

"""Serialization façade for LazyOps IO helpers.

This module centralises serializer registrations and exposes convenience
functions used across the codebase.  The implementation remains unchanged; we
focus on providing richer typing information and descriptive docstrings so that
Mintlify and other documentation tools can surface the available serializers
and helpers accurately.
"""

import typing as t
from types import ModuleType

from .base import (
    BaseSerializer,
    BinaryBaseSerializer,
    ObjectValue,
    SchemaType,
    create_object_hash,
    create_hash_from_args_and_kwargs,
)
from .defaults import default_json, default_msgpack, default_pickle
from .utils import (
    SerMode,
    deserialize_object,
    get_object_class,
    get_object_classname,
    register_schema_mapping,
    serialize_object,
)
from ._json import JsonSerializer
from ._msgpack import MsgPackSerializer
from ._pickle import PickleSerializer

SerT = t.Union[JsonSerializer, PickleSerializer, MsgPackSerializer, BaseSerializer, BinaryBaseSerializer]
SerializerFactory = t.Type[BaseSerializer]

RegisteredSerializers: dict[str, SerializerFactory] = {
    "json": JsonSerializer,
    "pickle": PickleSerializer,
    "msgpack": MsgPackSerializer,
}

RegisteredSerializerLibs: dict[str, list[str]] = {
    "json": ["orjson", "ujson", "simdjson", "cysimdjson"],
    "pickle": ["dill", "cloudpickle"],
}

DEFAULT_SERIALIZER = "json"


def get_default_serializer() -> str:
    """Return the globally configured default serializer name."""

    return DEFAULT_SERIALIZER


def set_default_serializer(serializer: str) -> None:
    """Update the global default serializer.

    Args:
        serializer: Name used when resolving serializers via :func:`get_serializer`.
    """

    global DEFAULT_SERIALIZER
    DEFAULT_SERIALIZER = serializer


def register_serializer(
    name: str,
    serializer: SerializerFactory,
    override: bool | None = False,
    set_as_default: bool | None = False,
) -> None:
    """Register a :class:`BaseSerializer` factory for use throughout LazyOps.

    Args:
        name: Identifier that callers pass into :func:`get_serializer`.
        serializer: Concrete serializer class implementing the
            :class:`BaseSerializer` contract.
        override: When ``True`` replace an existing registration with the same
            ``name``; otherwise a :class:`ValueError` is raised.
        set_as_default: When ``True`` call :func:`set_default_serializer` with
            ``name`` to make the serializer the global default.
    """

    global RegisteredSerializers
    if name in RegisteredSerializers and not override:
        existing = RegisteredSerializers[name]
        raise ValueError(
            f"Serializer `{name}` already registered with {existing} and override is False"
        )
    RegisteredSerializers[name] = serializer
    if set_as_default:
        set_default_serializer(name)


def set_default_serializer_lib(serializer: str, lib: ModuleType | str) -> None:
    """Set the preferred underlying library for a known serializer."""

    if serializer not in RegisteredSerializers:
        raise ValueError(
            f"Serializer `{serializer}` is not registered. Please register the serializer first"
        )
    RegisteredSerializers[serializer].set_default_lib(lib)


def register_serializer_lib(
    serializer: str,
    lib: ModuleType | str,
    set_as_default_lib: bool | None = False,
) -> None:
    """Register a library backend that a serializer implementation understands.

    Args:
        serializer: Name of the serializer to attach the backend to.
        lib: Either the module object or its dotted import path.
        set_as_default_lib: When ``True`` update the serializer so that ``lib``
            is used as the default backend for subsequent serializer instances.
    """

    global RegisteredSerializerLibs
    if serializer not in RegisteredSerializers:
        raise ValueError(
            f"Serializer `{serializer}` is not registered. Please register the serializer first"
        )
    if serializer not in RegisteredSerializerLibs:
        RegisteredSerializerLibs[serializer] = []
    if isinstance(lib, ModuleType):
        lib = lib.__name__
    if lib not in RegisteredSerializerLibs[serializer]:
        RegisteredSerializerLibs[serializer].append(lib)
    if set_as_default_lib:
        RegisteredSerializers[serializer].set_default_lib(lib)


_initialized_sers: dict[str, SerT] = {}


@t.overload
def get_serializer(
    serializer: t.Literal["json"] = ...,
    jsonlib: str | ModuleType | None = ...,
    compression: str | None = ...,
    compression_level: int | None = ...,
    encoding: str | None = ...,
    serialization_obj: t.Type[object] | None = ...,
    serialization_obj_kwargs: dict[str, t.Any] | None = ...,
    disable_object_serialization: bool | None = ...,
    disable_nested_values: bool | None = ...,
    verbosity: int | None = ...,
    raise_errors: bool = ...,
    enforce_string_value: bool | None = ...,
    enforce_byte_value: bool | None = ...,
    ser_mode: SerMode | None = ...,
    deprecated_compression: str | None = ...,
    schema_map: dict[str, str] | None = ...,
    **kwargs: t.Any,
) -> JsonSerializer:
    ...


def get_serializer(serializer: str | None = None, **kwargs: t.Any) -> SerT:
    """Return a serializer instance matching ``serializer`` and ``kwargs``.

    The helper caches instances keyed by their configuration so the same
    serializer can be reused across the process without repeatedly
    instantiating identical objects.
    """

    global _initialized_sers

    if serializer == "auto":
        serializer = None
    serializer = serializer or get_default_serializer()
    ser_hash = create_hash_from_args_and_kwargs(serializer, **kwargs)
    if ser_hash in _initialized_sers:
        return _initialized_sers[ser_hash]

    if serializer in RegisteredSerializers:
        new = RegisteredSerializers[serializer](**kwargs)
        _initialized_sers[ser_hash] = new
        return new

    for kind, libs in RegisteredSerializerLibs.items():
        if serializer in libs:
            if f"{kind}lib" not in kwargs:
                kwargs[f"{kind}lib"] = serializer
            new = RegisteredSerializers[kind](**kwargs)
            _initialized_sers[ser_hash] = new
            return new
    raise ValueError(f"Invalid Serializer Type: {serializer}")


__all__ = [
    "BaseSerializer",
    "BinaryBaseSerializer",
    "JsonSerializer",
    "MsgPackSerializer",
    "PickleSerializer",
    "SerT",
    "SerializerFactory",
    "DEFAULT_SERIALIZER",
    "get_serializer",
    "register_serializer",
    "set_default_serializer",
    "set_default_serializer_lib",
    "register_serializer_lib",
    "default_json",
    "default_pickle",
    "default_msgpack",
    "serialize_object",
    "deserialize_object",
    "register_schema_mapping",
    "get_object_class",
    "get_object_classname",
    "create_object_hash",
    "create_hash_from_args_and_kwargs",
]
