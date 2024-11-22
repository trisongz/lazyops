from __future__ import annotations


import functools
import typing as t
from temporalio.api.common.v1 import Payload
# from temporalio.api.sdk.v1.enhanced_stack_trace_pb2 import EnhancedStackTrace
from google.protobuf import reflection as _reflection
from lzl.io.ser import get_serializer, JsonSerializer
from lzl.io.ser.utils import is_primitive

_json = get_serializer("json", enforce_byte_value = True, verbosity = -1)

def is_serializable(value: t.Any) -> bool:
    """
    Returns whether the value is serializable
    """
    # if isinstance(value, EnhancedStackTrace): return False
    if isinstance(value, Exception): return False
    if isinstance(value, _reflection.GeneratedProtocolMessageType): return False
    return False if value is None else not is_primitive(value)

    
@functools.lru_cache()
def build_json_meta(
    encoding: t.Optional[str] = None,
    converter: t.Optional[str] = None,
    jsonlib: t.Optional[str] = None,
    compression: t.Optional[str] = None,
    compression_level: t.Optional[int] = None,
) -> t.Dict[str, bytes]:
    """
    Builds the JSON metadata
    """
    meta = {
        "encoding": encoding,
        "encoder": "json",
        "jsonlib": jsonlib,
        "converter": converter,
        "compression_name": compression,
        "compression_level": compression_level,
    }
    meta = {k:v for k,v in meta.items() if v is not None}
    return {k: v.encode() if isinstance(v, str) else v for k,v in meta.items()}
    

def get_json_meta(
    encoding: t.Optional[str] = None,
    converter: t.Optional[str] = None,
    js: JsonSerializer = _json,
) -> t.Dict[str, bytes]:
    """
    Returns the JSON metadata
    """
    return build_json_meta(
        encoding = encoding,
        converter = converter,
        jsonlib = js.jsonlib_name,
        compression = js.compressor.name if js.compression_enabled else None,
        compression_level = js.compression_level,
    )


def get_json_loader(
    payload: Payload,
) -> JsonSerializer:
    """
    Returns the JSON payload loader
    """
    if not payload.metadata.get('compression_name'):  return _json
    return get_serializer(
        "json",
        enforce_byte_value = True,
        verbosity = -1,
        jsonlib = payload.metadata.get('jsonlib').decode(),
        compression = payload.metadata.get('compression_name').decode(),
        compression_level = int(payload.metadata.get('compression_level').decode()) if payload.metadata.get('compression_level') else None,
    )

