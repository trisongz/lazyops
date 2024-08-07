from ._base import *
from .models import LazyDBCacheBase

LazyDBCacheType = TypeVar("LazyDBCacheType", bound=LazyDBCacheBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)