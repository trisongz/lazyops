from __future__ import annotations

from typing import Any, Dict, Optional, Union, Type
from lzl.load import lazy_import
from .base import BaseSerializer, ObjectValue, SchemaType, BaseModel, logger, ThreadPool, ModuleType
from .defaults import default_json, JsonLibT

class JsonSerializer(BaseSerializer):

    name: Optional[str] = "json"
    encoding: Optional[str] = "utf-8"
    jsonlib: JsonLibT = default_json
    disable_object_serialization: Optional[bool] = False
    allow_failed_import: Optional[bool] = False

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
        super().__init__(compression = compression, compression_level = compression_level, encoding = encoding, **kwargs)
        self.serialization_obj = serialization_obj
        self.serialization_obj_kwargs = serialization_obj_kwargs or {}
        self.serialization_schemas: Dict[str, Type[BaseModel]] = {}
        if disable_object_serialization is not None:
            self.disable_object_serialization = disable_object_serialization
        if jsonlib is not None:
            if isinstance(jsonlib, str):
                jsonlib = lazy_import(jsonlib, is_module=True)
            assert hasattr(jsonlib, "dumps") and hasattr(jsonlib, "loads"), f"Invalid JSON Library: {jsonlib}"
            self.jsonlib = jsonlib
        self.jsonlib_name = self.jsonlib.__name__

    @classmethod
    def set_default_lib(cls, lib: Union[str, JsonLibT, ModuleType]) -> None:
        """
        Sets the default JSON library
        """
        global default_json
        if isinstance(lib, str):
            lib = lazy_import(lib, is_module=True)
        assert hasattr(lib, "dumps") and hasattr(lib, "loads"), f"Invalid JSON Library: {lib}"
        cls.jsonlib = lib
        default_json = lib

        
    def encode_value(self, value: Union[Any, SchemaType], **kwargs) -> str:
        """
        Encode the value with the JSON Library
        """
        try:
            value_dict = self.serialize_obj(value, **kwargs, **self.serialization_obj_kwargs)
            encoded = self.jsonlib.dumps(value_dict, **kwargs)
            return self.coerce_output_value(encoded)

        except Exception as e:
            logger.trace(f'Error Encoding Value: |r|({type(value)})|e| {str(value)[:1000]}', e, colored = True)
        try:
            encoded = self.jsonlib.dumps(value, **kwargs)
            return self.coerce_output_value(encoded)
        except Exception as e:
            logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {str(value)[:1000]}', colored = True, prefix = self.jsonlib_name)
            if self.raise_errors: raise e
        return None


    def decode(self, value: Union[str, bytes], schema_map: Optional[Dict[str, str]] = None, raise_errors: Optional[bool] = None, **kwargs) -> ObjectValue:
        """
        Decodes the value
        """
        try:
            decompressed_value = self.decompress_value(value, **kwargs)
            if decompressed_value is not None:
                value = decompressed_value
        except Exception as e:
            logger.info(f'Error Decompressing Value: |r|({type(value)}) {e}|e| {str(value)[:100]}', colored = True, prefix = self.jsonlib_name)
            if raise_errors or self.raise_errors: raise ValueError(f"[{self.name}] Error in Decompression: {str(value)[:100]}") from e
            # return self.decode_value(value, **kwargs)
        return self.decode_value(value, schema_map = schema_map, raise_errors = raise_errors, **kwargs)
    
    
    def decode_value(self, value: str, schema_map: Optional[Dict[str, str]] = None, raise_errors: Optional[bool] = None, **kwargs) -> Union[SchemaType, Dict, Any]:
        """
        Decode the value with the JSON Library
        """
        if value is None: return None
        if isinstance(value, (str, bytes)):
            try:
                # value = self.check_encoded_value(value)
                value = self.jsonlib.loads(value, **kwargs)
            except Exception as e:
                if isinstance(value, str) and 'Exception' in value or 'Traceback (most recent call last):' in value:
                    return value
                str_value = str(value)
                if not schema_map: str_value = str_value[:1000]
                logger.info(f'Error JSON Decoding Value: |r|({type(value)}) {e}|e| {str_value}', colored = True, prefix = self.jsonlib_name)
                if raise_errors or self.raise_errors: raise e
        try:
            return self.deserialize_obj(value, schema_map = schema_map, allow_failed_import = self.allow_failed_import)
        except Exception as e:
            str_value = str(value)
            if not schema_map: str_value = str_value[:1000]
            logger.trace(f'Error Deserializing Object: ({type(value)}) {str_value}', e, prefix = self.jsonlib_name)
            if raise_errors or self.raise_errors: raise e
        return None


    async def adecode(self, value: Union[str, bytes], schema_map: Optional[Dict[str, str]] = None, raise_errors: Optional[bool] = None, **kwargs) -> ObjectValue:
        """
        Decodes the value asynchronously
        """
        return await ThreadPool.arun(self.decode, value, schema_map = schema_map, raise_errors = raise_errors, **kwargs)

        
    
    

    




