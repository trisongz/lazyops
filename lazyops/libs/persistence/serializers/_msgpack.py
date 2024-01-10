from __future__ import annotations

"""
MsgPack Serializer
"""

from typing import Any, Dict, Optional, Union, Type
from lazyops.utils.lazy import lazy_import
from .base import BinaryBaseSerializer, BaseModel, SchemaType, ObjectValue, logger
from ._json import default_json
try:
    import msgpack
    _msgpack_available = True
except ImportError:
    _msgpack_available = False


class MsgPackSerializer(BinaryBaseSerializer):
    name: Optional[str] = "msgpack"
    encoding: Optional[str] = "utf-8"
    disable_object_serialization: Optional[bool] = False
    jsonlib: Any = default_json

    def __init__(
        self, 
        compression: Optional[str] = None,
        compression_level: int | None = None, 
        encoding: str | None = None, 
        serialization_obj: Optional[Type[BaseModel]] = None,
        serialization_obj_kwargs: Optional[Dict[str, Any]] = None,
        disable_object_serialization: Optional[bool] = None,
        **kwargs
    ):
        if not _msgpack_available:
            raise ImportError("MsgPack Serializer is not available. Please install msgpack")
        super().__init__(compression, compression_level, encoding, **kwargs)
        self.serialization_obj = serialization_obj
        self.serialization_obj_kwargs = serialization_obj_kwargs or {}
        self.serialization_schemas: Dict[str, Type[BaseModel]] = {}
        if disable_object_serialization is not None:
            self.disable_object_serialization = disable_object_serialization
        
    def default_serialization_hook(self, obj: ObjectValue):
        """
        Default Serialization Hook
        """
        if not isinstance(obj, BaseModel) and not hasattr(obj, 'model_dump'):
            logger.info(f'Invalid Object Type: |r|{type(obj)}|e| {obj}', colored = True, prefix = "msgpack")
            return obj
        
        if self.disable_object_serialization: 
            return obj.model_dump_json(**self.serialization_obj_kwargs)

        obj_class_name = self.fetch_object_classname(obj)
        if obj_class_name not in self.serialization_schemas:
            self.serialization_schemas[obj_class_name] = obj.__class__
        data = obj.model_dump(mode = 'json', **self.serialization_obj_kwargs)
        data['__class__'] = obj_class_name
        return msgpack.ExtType(2, self.jsonlib.dumps(data).encode(self.encoding))
    
    def default_deserialization_hook(self, code: int, data: Union[str, bytes]) -> ObjectValue:
        """
        Default Deserialization Hook
        """
        if code != 2: return data
        if isinstance(data, bytes): data = data.decode(self.encoding)
        try:
            data = self.jsonlib.loads(data)
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(data)}) {e}|e| {str(data)[:500]}', colored = True, prefix = "msgpack")
            if self.raise_errors: raise e
            return data
        if not self.disable_object_serialization:
            _class = data.pop('__class__', None)
            if _class is not None:
                if _class not in self.serialization_schemas:
                    self.serialization_schemas[_class] = lazy_import(_class)
                _class = self.serialization_schemas[_class]
                return _class.model_validate(data, **self.serialization_obj_kwargs)
        elif self.serialization_obj is not None:
            return self.serialization_obj.model_validate(data, **self.serialization_obj_kwargs)
        return data

    def encode_value(self, value: Union[Any, SchemaType], **kwargs) -> bytes:
        """
        Encode the value with the Pickle Library
        """
        if 'use_bin_type' not in kwargs: kwargs['use_bin_type'] = True
        if 'default' not in kwargs: kwargs['default'] = self.default_serialization_hook
        try:
            return msgpack.packb(value, **kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {str(value)[:500]}', colored = True, prefix = "msgpack")
            if self.raise_errors: raise e
        return None

    def decode_value(self, value: bytes, **kwargs) -> Union[SchemaType, Dict, Any]:
        """
        Decode the value with the Pickle Library
        """
        try:
            if 'raw' not in kwargs: kwargs['raw'] = False
            if 'ext_hook' not in kwargs: kwargs['ext_hook'] = self.default_deserialization_hook
            return msgpack.unpackb(value, **kwargs)
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {str(value)[:500]}', colored = True, prefix = "msgpack")
            if self.raise_errors: raise e
        return None