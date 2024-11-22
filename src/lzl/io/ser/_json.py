from __future__ import annotations

from typing import Any, Dict, Optional, Union, Type, Tuple, TYPE_CHECKING
from lzl.load import lazy_import
from .base import BaseSerializer, ObjectValue, SchemaType, SerializableObject, BaseModel, logger, ThreadPool, ModuleType
from .utils import serialize_object
from .defaults import default_json, JsonLibT

class JsonSerializer(BaseSerializer):

    name: Optional[str] = "json"
    encoding: Optional[str] = "utf-8"
    jsonlib: JsonLibT = default_json
    disable_object_serialization: Optional[bool] = False
    disable_nested_values: Optional[bool] = None
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
        disable_nested_values: Optional[bool] = None,
        verbosity: Optional[int] = None,
        **kwargs
    ):
        super().__init__(compression = compression, compression_level = compression_level, encoding = encoding, **kwargs)
        self.serialization_obj = serialization_obj
        self.serialization_obj_kwargs = serialization_obj_kwargs or {}
        self.serialization_schemas: Dict[str, Type[BaseModel]] = {}
        if disable_object_serialization is not None:
            self.disable_object_serialization = disable_object_serialization
        if disable_nested_values is not None:
            self.disable_nested_values = disable_nested_values
        if jsonlib is not None:
            if isinstance(jsonlib, str):
                jsonlib = lazy_import(jsonlib, is_module=True)
            assert hasattr(jsonlib, "dumps") and hasattr(jsonlib, "loads"), f"Invalid JSON Library: {jsonlib}"
            self.jsonlib = jsonlib
        self.verbosity = verbosity
        self.jsonlib_name: str = self.jsonlib.__name__
        if 'bindings' in self.jsonlib_name.lower():
            self.jsonlib_name = self.jsonlib_name.rsplit('_', 1)[-1]

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

    @property
    def _is_verbose(self) -> bool:
        """
        Returns whether the serializer is verbose
        """
        return self.verbosity is None or self.verbosity >= 1

    @property
    def _is_silenced(self) -> bool:
        """
        Returns whether the serializer is verbose
        """
        return self.verbosity and self.verbosity < 0
        
    def serialize_obj(self, obj: SerializableObject, mode: Optional[SerMode] = None, **kwargs) -> Union[str, bytes]:
        """
        Serializes the object
        """
        mode = mode or self.ser_mode
        if 'disable_nested_values' not in kwargs and self.disable_nested_values is not None:
            kwargs['disable_nested_values'] = self.disable_nested_values
        return serialize_object(obj, mode = mode, **kwargs)
    

    def encode_value(self, value: Union[Any, SchemaType], **kwargs) -> str:
        """
        Encode the value with the JSON Library
        """
        try:
            value_dict = self.serialize_obj(value, **kwargs, **self.serialization_obj_kwargs)
            encoded = self.jsonlib.dumps(value_dict, **kwargs)
            return self.coerce_output_value(encoded)

        except Exception as e:
            if not self._is_silenced: logger.trace(f'Error Encoding Value: |r|({type(value)})|e| {str(value)[:1000]}', e, colored = True)
        try:
            encoded = self.jsonlib.dumps(value, **kwargs)
            return self.coerce_output_value(encoded)
        except Exception as e:
            if not self._is_silenced: logger.info(f'Error Encoding Value: |r|({type(value)}) {e}|e| {str(value)[:1000]}', colored = True, prefix = self.jsonlib_name)
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
            if not self._is_silenced: logger.info(f'Error Decompressing Value: |r|({type(value)}) {e}|e| {str(value)[:100]}', colored = True, prefix = self.jsonlib_name)
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
                if self._is_verbose: logger.info(f'Error JSON Decoding Value: |r|({type(value)}) {e}|e| {str_value}', colored = True, prefix = self.jsonlib_name)
                if raise_errors or self.raise_errors: raise e
        try:
            return self.deserialize_obj(value, schema_map = schema_map, allow_failed_import = self.allow_failed_import)
        except Exception as e:
            str_value = str(value)
            if not schema_map: str_value = str_value[:1000]
            if not self._is_silenced: logger.trace(f'Error Deserializing Object: ({type(value)}) {str_value}', e, prefix = self.jsonlib_name)
            if raise_errors or self.raise_errors: raise e
        return None


    async def adecode(self, value: Union[str, bytes], schema_map: Optional[Dict[str, str]] = None, raise_errors: Optional[bool] = None, **kwargs) -> ObjectValue:
        """
        Decodes the value asynchronously
        """
        return await ThreadPool.arun(self.decode, value, schema_map = schema_map, raise_errors = raise_errors, **kwargs)

        
    if TYPE_CHECKING:
        def dumps(
            self, 
            value: ObjectValue, 
            skipkeys: bool = False, 
            ensure_ascii: bool = True, 
            check_circular: bool = True,
            allow_nan: bool = True, 
            cls: Optional[Any] = None, 
            indent: Optional[int] = None, 
            separators: Optional[Tuple[str, str]] = None,
            default: Optional[Any] = None, 
            sort_keys: bool = False,
            **kwargs
        ) -> Union[str, bytes]:
            """Serialize ``obj`` to a JSON formatted ``str``.

            If ``skipkeys`` is true then ``dict`` keys that are not basic types
            (``str``, ``int``, ``float``, ``bool``, ``None``) will be skipped
            instead of raising a ``TypeError``.

            If ``ensure_ascii`` is false, then the return value can contain non-ASCII
            characters if they appear in strings contained in ``obj``. Otherwise, all
            such characters are escaped in JSON strings.

            If ``check_circular`` is false, then the circular reference check
            for container types will be skipped and a circular reference will
            result in an ``RecursionError`` (or worse).

            If ``allow_nan`` is false, then it will be a ``ValueError`` to
            serialize out of range ``float`` values (``nan``, ``inf``, ``-inf``) in
            strict compliance of the JSON specification, instead of using the
            JavaScript equivalents (``NaN``, ``Infinity``, ``-Infinity``).

            If ``indent`` is a non-negative integer, then JSON array elements and
            object members will be pretty-printed with that indent level. An indent
            level of 0 will only insert newlines. ``None`` is the most compact
            representation.

            If specified, ``separators`` should be an ``(item_separator, key_separator)``
            tuple.  The default is ``(', ', ': ')`` if *indent* is ``None`` and
            ``(',', ': ')`` otherwise.  To get the most compact JSON representation,
            you should specify ``(',', ':')`` to eliminate whitespace.

            ``default(obj)`` is a function that should return a serializable version
            of obj or raise TypeError. The default simply raises TypeError.

            If *sort_keys* is true (default: ``False``), then the output of
            dictionaries will be sorted by key.

            To use a custom ``JSONEncoder`` subclass (e.g. one that overrides the
            ``.default()`` method to serialize additional types), specify it with
            the ``cls`` kwarg; otherwise ``JSONEncoder`` is used.

            """
            ...

    

    




