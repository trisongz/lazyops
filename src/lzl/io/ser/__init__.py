from __future__ import annotations

"""
Serialization I/O Modules
"""

from .base import BaseSerializer, BinaryBaseSerializer, ObjectValue, SchemaType, create_object_hash, create_hash_from_args_and_kwargs
from .defaults import default_json, default_pickle, default_msgpack
from .utils import serialize_object, deserialize_object, register_schema_mapping, get_object_class, get_object_classname
from ._json import JsonSerializer
from ._pickle import PickleSerializer
from ._msgpack import MsgPackSerializer
from types import ModuleType
from typing import Any, Dict, Optional, Union, Type, List, Literal, overload

SerT = Union[JsonSerializer, PickleSerializer, MsgPackSerializer, BaseSerializer, BinaryBaseSerializer]

RegisteredSerializers: Dict[str, Type[SerT]] = {
    "json": JsonSerializer,
    "pickle": PickleSerializer,
    "msgpack": MsgPackSerializer,
}

RegisteredSerializerLibs: Dict[str, List[str]] = {
    "json": ["orjson", "ujson", "simdjson", "cysimdjson"],
    "pickle": ["dill", "cloudpickle"],
}


DEFAULT_SERIALIZER = "json"

def get_default_serializer() -> str:
    """
    Returns the default serializer
    """
    return DEFAULT_SERIALIZER

def set_default_serializer(
    serializer: str,
) -> None:
    """
    Sets the default serializer

    :param serializer: The serializer to use
    """
    global DEFAULT_SERIALIZER
    DEFAULT_SERIALIZER = serializer


def register_serializer(
    name: str,
    serializer: Type[SerT],
    override: Optional[bool] = False,
    set_as_default: Optional[bool] = False,
) -> None:
    """
    Registers a Serializer
    """
    global RegisteredSerializers
    if name in RegisteredSerializers and not override:
        raise ValueError(f"Serializer `{name}` already registered with {RegisteredSerializers[name]} and override is False")
    RegisteredSerializers[name] = serializer
    if set_as_default: set_default_serializer(name)


def set_default_serializer_lib(
    serializer: str,
    lib: Union[ModuleType, str],
):
    """
    Sets the default library for a serializer
    """
    if serializer not in RegisteredSerializers:
        raise ValueError(f"Serializer `{serializer}` is not registered. Please register the serializer first")
    RegisteredSerializers[serializer].set_default_lib(lib)

def register_serializer_lib(
    serializer: str,
    lib: Union[ModuleType, str],
    set_as_default_lib: Optional[bool] = False,
):
    """
    Registers a serializer library such as
    - Json: orjson, ujson, simdjson
    - Pickle: dill, cloudpickle
    """
    global RegisteredSerializerLibs
    if serializer not in RegisteredSerializers:
        raise ValueError(f"Serializer `{serializer}` is not registered. Please register the serializer first")
    if serializer not in RegisteredSerializerLibs:
        RegisteredSerializerLibs[serializer] = []
    if isinstance(lib, ModuleType):
        lib = lib.__name__
    if lib not in RegisteredSerializerLibs[serializer]:
        RegisteredSerializerLibs[serializer].append(lib)
    if set_as_default_lib: RegisteredSerializers[serializer].set_default_lib(lib)

# We use this to create a singleton instance of the serializer
# so that get_serializer can be called repeatedly without risk of initializing multiple times
# if the same kwargs are passed in
_initialized_sers: Dict[str, SerT] = {}


@overload
def get_serializer(
    serializer: Literal['json'] = ...,
    jsonlib: Optional[Union[str, Any]] = ...,
    compression: Optional[str] = ...,
    compression_level: int | None = ..., 
    encoding: str | None = ..., 
    serialization_obj: Optional[Type] = ...,
    serialization_obj_kwargs: Optional[Dict[str, Any]] = ...,
    disable_object_serialization: Optional[bool] = ...,
    disable_nested_values: Optional[bool] = ...,
    verbosity: Optional[int] = ...,
    raise_errors: bool = ...,
    enforce_string_value: Optional[bool] = ...,
    enforce_byte_value: Optional[bool] = ...,
    ser_mode: Optional[SerMode] = ...,
    deprecated_compression: Optional[str] = ...,
    schema_map: Optional[Dict[str, str]] = ...,
    **kwargs
) -> JsonSerializer:
    """
    Returns a JSON Serializer

    Args:
        serializer: The serializer to use. Options are ``json``, ``pickle``, ``msgpack``, or ``auto``.
        jsonlib: The JSON library to use. This is ignored if ``serializer`` is set.
        compression: The compression to use. Options are ``gzip``, ``lz4``, ``zlib``, or ``auto``.
        compression_level: The compression level to use.
        encoding: The encoding to use. Defaults to ``utf-8``.
        serialization_obj: The serialization object to use. Defaults to ``lzl.io.serialization.DefaultSerializationObject``.
        serialization_obj_kwargs: The serialization object kwargs to use.
        disable_object_serialization: Whether to disable object serialization. Defaults to ``False``.
        disable_nested_values: Whether to disable nested values. Defaults to ``False``.
        verbosity: The verbosity level to use. Defaults to ``None``.
        raise_errors: Whether to raise errors. Defaults to ``True``.
        enforce_string_value: Whether to enforce string values. Defaults to ``False``.
        enforce_byte_value: Whether to enforce byte values. Defaults to ``False``.
        ser_mode: The serialization mode to use. Defaults to ``auto``.
        deprecated_compression: The deprecated compression to use. This is ignored if ``compression`` is set.
        schema_map: The schema map to use. Defaults to ``None``.
    """

        
def get_serializer(
    serializer: Optional[str] = None,
    **kwargs
) -> SerT:
    """
    Returns a Serializer
    """
    global _initialized_sers

    if serializer == 'auto':  serializer = None
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
            if f'{kind}lib' not in kwargs: kwargs[f'{kind}lib'] = serializer
            new = RegisteredSerializers[kind](**kwargs)
            _initialized_sers[ser_hash] = new
            return new
    raise ValueError(f"Invalid Serializer Type: {serializer}")
