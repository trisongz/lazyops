from __future__ import annotations

"""
Extra Types for ORM
"""

from pathlib import Path
from sqlalchemy.sql import operators
from sqlalchemy.types import TypeDecorator, Text, String, DateTime
from sqlalchemy_json import NestedMutableJson, MutableDict, mutable_json_type
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from lazyops.utils.serialization import Json
from typing import Any, Optional, Union, Type

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

    def process_bind_param(self, value: Optional[Union[str, FileLike]], dialect):
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


JsonStringField: Type[MutableDict] = mutable_json_type(dbtype = JsonString, nested=True)
JsonStringNestedField: Type[NestedMutableJson] = mutable_json_type(dbtype = JsonString, nested = True)


JSONBField: Type[MutableDict] = mutable_json_type(dbtype = JSONB)
JSONBNestedField: Type[NestedMutableJson] = mutable_json_type(dbtype = JSONB, nested = True)

DateTimeUTC: DateTime = DateTime(timezone = True)

StringList: ARRAY = ARRAY(Text, dimensions = 1)
DateTimeUTCList: ARRAY = ARRAY(DateTimeUTC, dimensions = 1)

