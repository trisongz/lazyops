from __future__ import annotations

import functools
import dataclasses
import typing as t
import temporalio.converter
from temporalio.api.common.v1 import Payload
from lzl.proxied import ProxyObject
from temporalio.converter import (
    DataConverter,
    CompositePayloadConverter,
    DefaultPayloadConverter,
    EncodingPayloadConverter,
)
from lzl.types import eproperty
from lzl.io.ser.utils import is_primitive
from .utils import get_json_meta, get_serializer, get_json_loader, is_serializable


class SerializedEncodingPayloadConverter(EncodingPayloadConverter):
    
    def __init__(
        self, 
        jsonlib: t.Optional[str] = None,
        compression: t.Optional[str] = None, 
        compression_level: t.Optional[int] = None
    ):
        self._extra: t.Dict[str, t.Any] = {}
        self.jlib = get_serializer("json", enforce_byte_value = True, verbosity = -1, jsonlib = jsonlib, compression = compression, compression_level = compression_level)
        
    @eproperty
    def encoding(self) -> str:
        """
        Returns the encoding
        """
        # return "text/plain"
        return "json/object"
        # if self.jlib.compression_enabled: return f"{self.jlib.jsonlib_name}/compressed"
        # return f"{self.jlib.jsonlib_name}/plain"


    def to_payload(self, value: t.Any) -> t.Optional[Payload]:
        """
        Serializes the value
        """
        if not is_serializable(value): return None
        # print(f'{type(value)} to payload: ', value)
        # print('---' * 10)
        return Payload(
            metadata = get_json_meta(self.encoding, "serialized", self.jlib),
            data = self.jlib.dumps(
                value, 
                separators = (",", ":"), 
                sort_keys = True, 
            ),
        )

    def from_payload(self, payload: Payload, type_hint: t.Optional[t.Type] = None) -> t.Any:
        """
        Deserializes the value
        """
        if payload.metadata.get('converter') != b'serialized': return None
        # print('from payload: ', payload)
        # print('---' * 10)
        ser = get_json_loader(payload)
        return ser.loads(payload.data)


class SerializedPayloadConverter(CompositePayloadConverter):
    def __init__(self, jsonlib: t.Optional[str] = None, compression: t.Optional[str] = None, compression_level: t.Optional[int] = None, **kwargs) -> None:
        # Just add ours as first before the defaults
        super().__init__(
            SerializedEncodingPayloadConverter(jsonlib = jsonlib, compression = compression, compression_level = compression_level, **kwargs),
            *DefaultPayloadConverter.default_encoding_payload_converters,
        )


def get_serialized_data_converter(
    jsonlib: t.Optional[str] = None,
    compression: t.Optional[str] = None,
    compression_level: t.Optional[int] = None,
    **kwargs
) -> DataConverter:
    """
    Creates a data converter that uses the serialized payload converter
    """
    from lzl.ext.temporal.settings import config
    if config.data_jsonlib is not None and jsonlib is None: jsonlib = config.data_jsonlib
    if config.data_compression is not None and compression is None: compression = config.data_compression
    if config.data_compression_level is not None and compression_level is None: compression_level = config.data_compression_level
    newobj = functools.partial(
        SerializedPayloadConverter,
        jsonlib = jsonlib,
        compression = compression,
        compression_level = compression_level,
        **kwargs
    )
    return dataclasses.replace(
        temporalio.converter.default(),
        payload_converter_class = newobj,
    )


serialized_data_converter: DataConverter = ProxyObject(
    obj_getter = get_serialized_data_converter,
)