from __future__ import annotations

"""
Type Helpers
"""


import uuid
import datetime
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


