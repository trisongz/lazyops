from __future__ import annotations

"""
Extra Types for PGSQL ORM
"""


from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.sql import operators
from sqlalchemy.types import TypeDecorator, Text, String, DateTime, LargeBinary
from sqlalchemy_json import NestedMutableJson, MutableDict, mutable_json_type
from sqlalchemy.ext.indexable import index_property
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, JSON
from lazyops.utils.serialization import Json
from kvdb.io.serializers import get_serializer, JsonSerializer
from typing import Any, Optional, Union, Type, Dict, List
# from types import TypeDecorator

try:
    from fileio import File, FileLike
except ImportError:
    File = Path
    FileLike = Path


class FileField(TypeDecorator):

    impl = Text
    cache_ok = True

    def coerce_compared_value(self, op, value):
        """
        Coerce the value to be compared.
        """
        return Text() if op in (operators.like_op, operators.not_like_op) else self

    def process_bind_param(self, value: Optional[Union[str, FileLike]], dialect): # type: ignore
        """
        Return the value to be stored in the database.
        """
        if value is None: return None
        if isinstance(value, str): return value
        return value.as_posix() \
            if hasattr(value, 'as_posix') \
                else str(value)

    def process_result_value(self, value: Optional[Union[str, Any]], dialect):
        """
        Process the value retrieved from the database.
        """
        return File(value) if value is not None else None


class JsonString(TypeDecorator):
    """Enables JSON storage by encoding and decoding on the fly."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        Bind the value to be stored in the database.
        """
        if value is not None: value = Json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        """
        Process the value retrieved from the database.
        """
        if value is not None: value = Json.loads(value)
        return value
    
    def coerce_compared_value(self, op, value):
        """
        Coerce the value to be compared.
        """
        return Text() \
            if op in (operators.like_op, operators.not_like_op) \
                else self


class pg_json_property(index_property):
    def __init__(self, attr_name, index, cast_type):
        super(pg_json_property, self).__init__(attr_name, index)
        self.cast_type = cast_type

    def expr(self, model):
        expr = super(pg_json_property, self).expr(model)
        return expr.astext.cast(self.cast_type)


JsonStringField: Type[MutableDict] = mutable_json_type(dbtype = JsonString, nested=True)
JsonStringNestedField: Type[NestedMutableJson] = mutable_json_type(dbtype = JsonString, nested = True) # type: ignore


JSONBField: Type[MutableDict] = mutable_json_type(dbtype = JSONB)
JSONBNestedField: Type[NestedMutableJson] = mutable_json_type(dbtype = JSONB, nested = True) # type: ignore

DateTimeUTC: DateTime = DateTime(timezone = True)

StringList: ARRAY = ARRAY(Text, dimensions = 1)
DateTimeUTCList: ARRAY = ARRAY(DateTimeUTC, dimensions = 1)



_type_serializer: Optional[JsonSerializer] = None

def get_type_serializer() -> JsonSerializer:
    """
    Returns the type serializer
    """
    global _type_serializer
    if _type_serializer is None:
        _type_serializer = get_serializer(
            serializer = 'json', 
            compression = 'zstd',
            compression_level = 19,
        )
    return _type_serializer


class ZstdJson(TypeDecorator):
    """
    Enables JSON storage by encoding and decoding on the fly.
    with Zstd compression.
    """

    impl = LargeBinary
    cache_ok = True
    hashable = True

    def load_dialect_impl(self, dialect):
        """
        Load the dialect implementation.
        """
        return dialect.type_descriptor(self.impl)

    def process_bind_param(self, value, dialect) -> Optional[bytes]:
        """
        Process the value to be stored in the database.
        """
        if value is not None:
            t = get_type_serializer()
            value = t.dumps(value)
        return value

    def process_result_value(self, value, dialect) ->  Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Process the value retrieved from the database.
        """
        if value is not None:
            t = get_type_serializer()
            value = t.loads(value)
        return value
    

class RawZstdJson(TypeDecorator):
    """
    Enables JSON storage by encoding and decoding on the fly.
    with Zstd compression.
    """

    impl = LargeBinary
    cache_ok = True
    hashable = True

    def load_dialect_impl(self, dialect):
        """
        Load the dialect implementation.
        """
        return dialect.type_descriptor(self.impl)

    def process_bind_param(self, value: Union[str, bytes, Any], dialect) -> Optional[bytes]:
        """
        Process the value to be stored in the database.
        """
        if value is not None:
            if isinstance(value, bytes): return value
            if isinstance(value, str): return value.encode()
            t = get_type_serializer()
            value = t.dumps(value)
        return value

    def process_result_value(self, value, dialect) ->  Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Process the value retrieved from the database.
        """
        if value is not None:
            t = get_type_serializer()
            value = t.loads(value)
        return value