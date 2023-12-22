import json
from typing import Any, Dict, Optional, Union, Type
from lazyops.utils.lazy import lazy_import
from .base import BaseSerializer, ObjectValue, SchemaType, BaseModel, logger


class JsonSerializer(BaseSerializer):

    name: Optional[str] = "json"
    encoding: Optional[str] = "utf-8"
    jsonlib: Any = json

    def __init__(
        self, 
        jsonlib: Optional[Union[str, Any]] = None,
        compression_level: int | None = None, 
        encoding: str | None = None, 
        serialization_obj: Optional[Type[BaseModel]] = None,
        serialization_obj_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(compression_level, encoding, **kwargs)
        self.serialization_obj = serialization_obj
        self.serialization_obj_kwargs = serialization_obj_kwargs or {}
        if jsonlib is not None:
            if isinstance(jsonlib, str):
                jsonlib = lazy_import(jsonlib)
            assert hasattr(jsonlib, "dumps") and hasattr(jsonlib, "loads"), f"Invalid JSON Library: {jsonlib}"
            self.jsonlib = jsonlib
        self.jsonlib_name = self.jsonlib.__name__
    
    def encode_value(self, value: Union[Any, SchemaType], **kwargs) -> str:
        """
        Encode the value with the JSON Library
        """
        try:
            if hasattr(value, 'model_dump'): 
                value = value.model_dump(mode = 'json', round_trip = True, **self.serialization_obj_kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {value}', colored = True)
        try:
            return self.jsonlib.dumps(value, **kwargs)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = self.jsonlib_name)
            if self.raise_errors: raise e
        return None

    def decode_value(self, value: str, **kwargs) -> Union[SchemaType, Dict, Any]:
        """
        Decode the value with the JSON Library
        """
        try:
            value = self.jsonlib.loads(value, **kwargs)
            if self.serialization_obj is not None:
                value = self.serialization_obj.model_validate(value)
            return value
        except Exception as e:
            logger.info(f'Error Decoding Value: |r|({type(value)}) {e}|e| {value}', colored = True, prefix = self.jsonlib_name)
            if self.raise_errors: raise e
        return None
        
    
    

    




