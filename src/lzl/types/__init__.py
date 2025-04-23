"""
Lzl Types Submodule.

Provides core type definitions, Pydantic compatibility layers, custom properties,
and common type aliases used throughout the `lzl` and `lzo` packages.
"""

from .base import (
    BaseModel,
    validator,
    root_validator,
    pre_root_validator,
    Field,
    ConfigDict,
    model_validator,
    field_validator,
    get_schema_extra,
    ByteSize,
    PYDANTIC_VERSION,
    get_pydantic_field_names,
    PrivateAttr,
)
from .properties import (
    eproperty,
    aproperty,
    rproperty,
    lazyproperty,
    classproperty,
)

from .settings import (
    BaseSettings,
)

from .common import (
    Final, Literal, StrEnum, UpperStrEnum, AppEnv, get_app_env
)
from .typed import (
    AnyType,
    ClassType,
    SelfType,
    ParamType,
    ReturnType,
    LocalReturnType,
    CallableType,
    CallableAsyncType,
    CallableSyncOrAsyncType,
    CallableSyncOrAsyncReturnNoneType,
    MultiParamSpec,
    ProtocolParamType,
    ProtocolReturnType,
    ProtocolSelfType,
    # CallableAsyncNoParam,
    # CallableSyncNoParam,
    # CallableAsyncSingleParam,
    # CallableSyncSingleParam,
    # MethodAsyncNoParam,
    # MethodSyncNoParam,
    # MethodAsyncSingleParam,
    # MethodSyncSingleParam,
    AsyncGenerator
)

from .utils import create_alias_choices