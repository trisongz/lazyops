from .base import BaseSerializer, BinaryBaseSerializer, ObjectValue, SchemaType
from ._json import JsonSerializer
from ._pickle import PickleSerializer
from ._msgpack import MsgPackSerializer
from typing import Any, Dict, Optional, Union, Type

SerializerT = Union[JsonSerializer, PickleSerializer, MsgPackSerializer, BaseSerializer]

def get_serializer(
    serializer_type: Optional[str] = None,
    **kwargs
) -> SerializerT:
    """
    Returns a Serializer
    """
    serializer_type = serializer_type or "pickle"
    if serializer_type in {"json", "orjson", "ujson", "simdjson"}:
        if serializer_type != "json" and "jsonlib" not in kwargs:
            kwargs["jsonlib"] = serializer_type
        return JsonSerializer(**kwargs)
    if serializer_type in {"pickle", "dill", "cloudpickle"}:
        if serializer_type != "pickle" and "picklelib" not in kwargs:
            kwargs["picklelib"] = serializer_type
        return PickleSerializer(**kwargs)
    if serializer_type == "msgpack":
        return MsgPackSerializer(**kwargs)
    raise ValueError(f"Invalid Serializer Type: {serializer_type}")