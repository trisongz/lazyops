from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union, Type
from lazyops.utils.lazy import lazy_import
from .base import BaseSerializer, ObjectValue, SchemaType, BaseModel, logger

try:
    import orjson
    _orjson_available = True
except ImportError:
    _orjson_available = False

try:
    import simdjson
    _simdjson_available = True
except ImportError:
    _simdjson_available = False

try:
    import ujson
    _ujson_available = True
except ImportError:
    _ujson_available = False


if _simdjson_available:
    default_json = simdjson

elif _orjson_available:
    default_json = orjson

elif _ujson_available:
    default_json = ujson

else:
    default_json = json


class JsonSerializer(BaseSerializer):

    name: Optional[str] = "json"
    encoding: Optional[str] = "utf-8"
    jsonlib: Any = default_json
    disable_object_serialization: Optional[bool] = False

    def __init__(
        self, 
        jsonlib: Optional[Union[str, Any]] = None,
        compression: Optional[str] = None,
        compression_level: int | None = None, 
        encoding: str | None = None, 
        serialization_obj: Optional[Type[BaseModel]] = None,
        serialization_obj_kwargs: Optional[Dict[str, Any]] = None,
        disable_object_serialization: Optional[bool] = None,
        **kwargs
    ):
        super().__init__(compression, compression_level, encoding, **kwargs)
        self.serialization_obj = serialization_obj
        self.serialization_obj_kwargs = serialization_obj_kwargs or {}
        self.serialization_schemas: Dict[str, Type[BaseModel]] = {}
        if disable_object_serialization is not None:
            self.disable_object_serialization = disable_object_serialization
        if jsonlib is not None:
            if isinstance(jsonlib, str):
                jsonlib = lazy_import(jsonlib)
            assert hasattr(jsonlib, "dumps") and hasattr(jsonlib, "loads"), f"Invalid JSON Library: {jsonlib}"
            self.jsonlib = jsonlib
        self.jsonlib_name = self.jsonlib.__name__
    

    def encode_one(self, value: Union[Any, SchemaType], **kwargs) -> str:
        """
        Encode the value with the JSON Library
        """
        try:
            if hasattr(value, 'model_dump'): 
                if not self.disable_object_serialization:
                    obj_class_name = self.fetch_object_classname(value)
                    if obj_class_name not in self.serialization_schemas:
                        self.serialization_schemas[obj_class_name] = value.__class__
                value = value.model_dump(mode = 'json', round_trip = True, **self.serialization_obj_kwargs)
                if not self.disable_object_serialization:
                    value['__class__'] = obj_class_name
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {str(value)[:1000]}', colored = True)
        try:
            return self.jsonlib.dumps(value, **kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {str(value)[:1000]}', colored = True, prefix = self.jsonlib_name)
            if self.raise_errors: raise e
        return None
        
    def encode_value(self, value: Union[Any, SchemaType], **kwargs) -> str:
        """
        Encode the value with the JSON Library
        """
        if isinstance(value, list):
            values = [self.encode_one(v, **kwargs) for v in value]
            value_dict = {
                '__type__': 'list',
                'values': values,
            }
            return self.jsonlib.dumps(value_dict, **kwargs)
        return self.encode_one(value, **kwargs)


    def decode_one(self, value: str, **kwargs) -> Union[SchemaType, Dict, Any]:
        """
        Decode the value with the JSON Library
        """
        try:
            value = self.jsonlib.loads(value, **kwargs)
            if not self.disable_object_serialization and isinstance(value, dict) and '__class__' in value:
                obj_class_name = value.pop('__class__')
                if obj_class_name not in self.serialization_schemas:
                    self.serialization_schemas[obj_class_name] = lazy_import(obj_class_name)
                obj_class = self.serialization_schemas[obj_class_name]
                value = obj_class.model_validate(value)
            elif self.serialization_obj is not None:
                value = self.serialization_obj.model_validate(value)
            return value
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {str(value)[:1000]}', colored = True, prefix = self.jsonlib_name)
            if self.raise_errors: raise e
        return None

    def decode_value(self, value: str, **kwargs) -> Union[SchemaType, Dict, Any]:
        """
        Decode the value with the JSON Library
        """
        value = self.decode_one(value, **kwargs)
        if isinstance(value, dict) and '__type__' in value and value['__type__'] == 'list':
            return [self.decode_one(v, **kwargs) for v in value['values']]
        return value

        
    
    

    




