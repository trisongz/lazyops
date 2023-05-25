from __future__ import annotations

"""
Type Helpers
"""


import uuid
import datetime
import contextlib
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import Field, BaseModel
from lazyops.utils import create_unique_id, create_timestamp, timer

DatetimeT = datetime.datetime
OptionalDatetimeT = Optional[datetime.datetime]

UUIDT = uuid.UUID
OptionalUUIDT = Optional[uuid.UUID]

UniqueIDT = str
OptionalUniqueIDT = Optional[str]

DurationT = float
OptionalDurationT = Optional[float]


# Factories
DurationFactory = lambda: Field(default_factory = timer)
DateTimeFactory = lambda: Field(default_factory = create_timestamp)
UniqueIDFactory = lambda: Field(default_factory = create_unique_id)

NullAlias = lambda x: Field(None, alias = x)

# Enums
class OrderBy(Enum):
    ASC = 'asc'
    DESC = 'desc'


class PaginationParams(BaseModel):
    """Pagination params for endpoints."""
    offset: int = 0
    limit: Optional[int] = 100
    order_by: Optional[Any] = None # OrderBy.asc



try:
    from fileio import File, FileLike
    from sqlalchemy.types import TypeDecorator, Text
    from sqlalchemy.sql import operators

    class FileField(TypeDecorator):

        impl = Text
        cache_ok = True

        def coerce_compared_value(self, op, value):
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
            return File(value) if value is not None else None

except ImportError:
    FileField: object = None
