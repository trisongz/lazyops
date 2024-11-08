"""
This submodule only contains a compatiability layer for `pydantic` and `pydantic_settings`
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
    rproperty
)

from .settings import (
    BaseSettings,
)

from .common import (
    Final, Literal, StrEnum, UpperStrEnum, AppEnv, get_app_env
)
from .typed import AsyncGenerator