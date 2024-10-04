from __future__ import annotations

"""
Extended Types
"""

import contextlib
from sqlalchemy import types
from sqlalchemy.schema import Sequence
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql import operators
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, JSON
from sqlalchemy.dialects.postgresql.base import ischema_names

from lzl import load
from typing import Any, cast, Optional, Union, Dict, List, Type, TYPE_CHECKING

# if load.TYPE_CHECKING:
#     import fileio
# else:
#     fileio = load.LazyLoad("fileio", install_missing=True, install_options={'package': 'file-io'})

# if TYPE_CHECKING:
#     from fileio import FileLike

from lzl.io import File, FileLike

class FileField(types.TypeDecorator):

    impl = types.String
    cache_ok = True
    mysql_default_length = 255

    def coerce_compared_value(self, op, value):
        """
        Coerce the value to be compared.
        """
        return types.String(length = self.mysql_default_length) if op in (operators.like_op, operators.not_like_op) else self
    
    def process_bind_param(self, value: Optional[Union[str, 'FileLike']], dialect):
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


class JsonString(types.TypeDecorator):
    """
    A String type that stores JSON data.
    """
    impl = types.String
    cache_ok = True
    hashable = True

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        """
        Initializes the JsonString Type
        """
        super().__init__(*args, **kwargs)
        from lzl.io.ser import get_serializer
        self.ser = get_serializer('json')
        self.ser.enforce_string_value = True

    def load_dialect_impl(self, dialect):
        """
        Load the dialect implementation.
        """
        return dialect.type_descriptor(self.impl)

    def process_bind_param(self, value, dialect) -> Optional[str]:
        """
        Process the value to be stored in the database.
        """
        if value is not None:
            value = self.ser.dumps(value)
        return value

    def process_result_value(self, value, dialect) ->  Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Process the value retrieved from the database.
        """
        if value is not None:
            value = self.ser.loads(value)
        return value


class SerializedBinary(types.TypeDecorator):
    """
    A LargeBinary type that stores serialized data.
    """
    impl = types.LargeBinary
    cache_ok = True
    hashable = True

    def __init__(
        self,
        *args,
        serializer: Optional[str] = 'json',
        compression: Optional[str] = 'zstd',
        compression_level: int = 3,
        validate_raw: Optional[bool] = True,
        **kwargs,
    ) -> None:
        """
        Initializes the SerializedBinary Type

        - Supports Serialization: json, pickle, msgpack
        - Supports Compression: zstd, lz4, zlib, and bz2
        """
        super().__init__(*args, **kwargs)
        from lzl.io.ser import get_serializer
        self.ser = get_serializer(serializer, compression = compression, compression_level = compression_level)
        self.validate_raw = validate_raw

    
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
            if self.validate_raw:
                if isinstance(value, bytes): return value
                if isinstance(value, str): return value.encode()
            value = self.ser.dumps(value)
        return value

    def process_result_value(self, value, dialect) ->  Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Process the value retrieved from the database.
        """
        if value is not None: value = self.ser.loads(value)
        return value



DateTimeUTC: types.DateTime = types.DateTime(timezone = True)

IntList: ARRAY = ARRAY(types.Integer, dimensions = 1)
BigIntList: ARRAY = ARRAY(types.BigInteger, dimensions = 1)
StringList: ARRAY = ARRAY(types.Text, dimensions = 1)
DateTimeUTCList: ARRAY = ARRAY(DateTimeUTC, dimensions = 1)
# AutoSequence: types.BigInteger = 

with contextlib.suppress(ImportError):
    from sqlalchemy_json import NestedMutableJson, MutableDict, mutable_json_type

    JsonStringField: Type[MutableDict] = mutable_json_type(dbtype = JsonString, nested=True)
    JsonStringNestedField: Type[NestedMutableJson] = mutable_json_type(dbtype = JsonString, nested = True) # type: ignore


    JSONBField: Type[MutableDict] = mutable_json_type(dbtype = JSONB)
    JSONBNestedField: Type[NestedMutableJson] = mutable_json_type(dbtype = JSONB, nested = True) # type: ignore


# for reflection
ischema_names['file'] = FileField
ischema_names['jsonstring'] = JsonString
ischema_names['serializedbinary'] = SerializedBinary

# Try to import pgvector
try:
    from pgvector.sqlalchemy import Vector

except ImportError:
    import numpy as np

    def from_db(value):
        # could be ndarray if already cast by lower-level driver
        if value is None or isinstance(value, np.ndarray):
            return value
        return np.array(value[1:-1].split(','), dtype=np.float32)
        
    def to_db(value, dim=None):
        if value is None: return value
        if isinstance(value, np.ndarray):
            if value.ndim != 1:
                raise ValueError('expected ndim to be 1')
            if not np.issubdtype(value.dtype, np.integer) and not np.issubdtype(value.dtype, np.floating):
                raise ValueError('dtype must be numeric')
            value = value.tolist()
        if dim is not None and len(value) != dim:
            raise ValueError('expected %d dimensions, not %d' % (dim, len(value)))
        return '[' + ','.join([str(float(v)) for v in value]) + ']'


    class Vector(types.UserDefinedType):
        cache_ok = True
        _string = types.String()

        def __init__(self, dim=None):
            super(types.UserDefinedType, self).__init__()
            self.dim = dim

        def get_col_spec(self, **kw):
            return "VECTOR" if self.dim is None else "VECTOR(%d)" % self.dim

        def bind_processor(self, dialect):
            def process(value):
                return to_db(value, self.dim)
            return process

        def literal_processor(self, dialect):
            string_literal_processor = self._string._cached_literal_processor(dialect)
            def process(value):
                return string_literal_processor(to_db(value, self.dim))
            return process

        def result_processor(self, dialect, coltype):
            def process(value):
                return from_db(value)
            return process

        class comparator_factory(types.UserDefinedType.Comparator):
            def l2_distance(self, other):
                return self.op('<->', return_type=types.Float)(other)

            def max_inner_product(self, other):
                return self.op('<#>', return_type=types.Float)(other)

            def cosine_distance(self, other):
                return self.op('<=>', return_type=types.Float)(other)

    ischema_names['vector'] = Vector

# from pgvector.asyncpg import Vector