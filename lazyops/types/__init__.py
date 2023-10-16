from __future__ import absolute_import

from lazyops.types.common import *

from lazyops.types.models import BaseModel, BaseSettings, Schema, Field, validator, UrlModel, BaseDBUrl, PostgresDB, RedisDB, NatsDB
# try:
#     from lazyops.types.models import BaseModel, BaseSettings, Schema, Field, validator, UrlModel, BaseDBUrl, PostgresDB, RedisDB, NatsDB
# except ImportError:
#     from lazyops.types.models_v2 import BaseModel, BaseSettings, Schema, Field, validator, UrlModel, BaseDBUrl, PostgresDB, RedisDB

from lazyops.types.classprops import lazyproperty, classproperty, cached_classproperty

try:
    from pydantic.dataclasses import dataclass
except ImportError:
    from dataclasses import dataclass

# from lazyops.types.resources import BaseResource, ResourceType, ResponseResource, ResponseResourceType