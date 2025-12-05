"""
Common Types
"""

import os
import sys
from enum import Enum, EnumMeta
from functools import singledispatchmethod
from typing import Any, Union, Dict, Optional, TypeVar, TYPE_CHECKING

if sys.version_info >= (3, 8):
    from typing import Final, Literal
else:
    from typing_extensions import Final, Literal

try:
    from aenum import extend_enum
    _EXTEND_SUPPORTED = True
except ImportError:
    _EXTEND_SUPPORTED = False

class StrEnumMeta(EnumMeta):

    @singledispatchmethod
    def __getitem__(self, key):
        return super().__getitem__(key)

    @__getitem__.register
    def _(self, index: int):
        return list(self)[index]
    
    @property
    def _reversed_members_(cls) -> Dict[str, str]:
        """
        Returns the reversed members
        """
        return {v: k for k, v in cls.__members__.items()}

from .base import PYDANTIC_VERSION

def _get_serialized_value(value: Union[str, 'StrEnum']) -> str:
    """
    Returns the serialized value
    """
    return value.name if hasattr(value, 'name') else value
    
class StrEnum(str, Enum, metaclass=StrEnumMeta):
    """
    StrEnum is a string enum that allows for case-insensitive comparisons
    """

    def __eq__(self, other: Any) -> bool:
        return self.value.lower() == other.lower() if \
            isinstance(other, str) else \
                super().__eq__(other)
    
    def __ne__(self, other: Any) -> bool:
        return self.value.lower() != other.lower() if \
            isinstance(other, str) else \
                super().__ne__(other)

    def __str__(self) -> str:
        return str.__str__(self)
    
    def __hash__(self) -> int:
        return id(self)
    
    @classmethod
    def extend(cls, name: str, value: Any):
        """
        Dynamically extends the enum with a new member.
        
        Requires the `aenum` package to be installed.

        Args:
            name: The name of the new enum member.
            value: The value of the new enum member.
        
        Raises:
            ImportError: If `aenum` is not installed.
        """
        if not _EXTEND_SUPPORTED: raise ImportError('aenum is not installed. Please install it to use this feature')
        extend_enum(cls, name, value)

    @classmethod
    def __validate__(cls, value: Union[str, 'StrEnumT']) -> 'StrEnumT':
        """
        Validates and converts a value to the corresponding Enum member.
        
        It attempts to match the value against member names (case-insensitive)
        and values.

        Args:
            value: The value to validate.

        Returns:
            The matching Enum member.
        
        Raises:
            ValueError: If the value cannot be mapped to any Enum member.
        """
        if hasattr(value, '__members__'): return value
        # return cls(value.__name__)
        reversed_members = {v: k for k, v in cls.__members__.items()}
        if value in cls.__members__:
            return cls.__members__[value]
        elif value in reversed_members:
            return cls.__members__[reversed_members[value]]
        elif value.lower() in cls.__members__:
            return cls.__members__[value.lower()]
        elif value.capitalize() in cls.__members__:
            return cls.__members__[value.capitalize()]
        elif value.upper() in cls.__members__:
            return cls.__members__[value.upper()]
        elif value.lower() in reversed_members:
            return cls.__members__[reversed_members[value.lower()]]
        raise ValueError(f"Invalid {cls.__name__} value: {value}")
        
    if TYPE_CHECKING:
        from pydantic_core import core_schema, SchemaSerializer
        from pydantic.annotated_handlers import GetCoreSchemaHandler, GetJsonSchemaHandler
        from pydantic.json_schema import JsonSchemaValue
    
    if PYDANTIC_VERSION == 2:
    
        @classmethod
        def __get_pydantic_json_schema__(
            cls, 
            _core_schema: 'core_schema.CoreSchema', 
            _handler: 'GetJsonSchemaHandler'
        ) -> 'JsonSchemaValue':
            """
            Get the Pydantic JSON Schema for the given source
            """
            return {'enum': [m.name for m in cls], 'type': 'string'}

        @classmethod
        def __get_pydantic_core_schema__(
            cls, 
            source: type[Any], 
            handler: 'GetCoreSchemaHandler'
        ) -> 'core_schema.CoreSchema':
            """
            Get the Pydantic CoreSchema for the given source
            """
            from pydantic_core import core_schema, SchemaSerializer
            schema = core_schema.no_info_after_validator_function(
                cls.__validate__,
                core_schema.any_schema(),
                serialization = core_schema.plain_serializer_function_ser_schema(_get_serialized_value),
                # serialization = core_schema.plain_serializer_function_ser_schema(lambda x: x),
            )
            cls.__pydantic_serializer__ = SchemaSerializer(schema)
            return schema

StrEnumT = TypeVar('StrEnumT', bound = StrEnum)
    

class UpperStrEnum(StrEnum):
    """
    UpperStrEnum is a string enum that allows for case-insensitive comparisons
    """

    def __eq__(self, other: Any) -> bool:
        return self.value.upper() == other.upper() if \
            isinstance(other, str) else \
                super().__eq__(other)
    
    def __ne__(self, other: Any) -> bool:
        return self.value.upper() != other.upper() if \
            isinstance(other, str) else \
                super().__ne__(other)
    

    def __str__(self) -> str:
        return str.__str__(self)
    
    def __hash__(self) -> int:
        return id(self)



class AppEnv(str, Enum):
    CICD = "cicd"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"
    TEST = "test"

    @classmethod
    def from_env(cls, env_value: str) -> "AppEnv":
        """
        Determines the AppEnv from a string value, handling various formats and partial matches.
        
        Args:
            env_value: The string value to parse (e.g., "production", "prod", "ci/cd").
            
        Returns:
            The corresponding AppEnv member.
            
        Raises:
            ValueError: If the value cannot be mapped to a known environment.
        """
        env_value = env_value.lower()
        if "cicd" in env_value or "ci/cd" in env_value: return cls.CICD
        if "prod" in env_value: return cls.PRODUCTION
        if "dev" in env_value: return cls.DEVELOPMENT
        if "staging" in env_value: return cls.STAGING
        if "local" in env_value: return cls.LOCAL
        if "test" in env_value: return cls.TEST
        raise ValueError(f"Invalid app environment: {env_value} ({type(env_value)})")
    
    @classmethod
    def from_hostname(cls, hostname: str) -> "AppEnv":
        """
        Get the app environment from the hostname
        """
        hostname = hostname.lower()
        if "dev" in hostname: return cls.DEVELOPMENT
        if "staging" in hostname: return cls.STAGING
        if "test" in hostname: return cls.TEST
        return cls.LOCAL if "local" in hostname else cls.PRODUCTION
        
    
    @classmethod
    def from_module_name(cls, module_name: str) -> 'AppEnv':
        """
        Retrieves the app environment
        """
        module_name = module_name.replace(".", "_").upper()
        for key in {
            "SERVER_ENV",
            f"{module_name}_ENV",
            "APP_ENV",
            "ENVIRONMENT",
        }:
            if env_value := os.getenv(key):
                return cls.from_env(env_value)

        from lzo.utils.system import is_in_kubernetes, get_host_name
        if is_in_kubernetes():
            hn = get_host_name()
            try:
                parts = hn.split("-")
                for p in parts:
                    if all(
                        e not in p.lower()
                        for e in {'development', 'test', 'staging', 'local', 'dev', 'prod', 'production'}
                    ):
                        parts.remove(p)
                return cls.from_env(parts[0]) if len(parts) > 0 else cls.PRODUCTION
                # return cls.PRODUCTION
                # return cls.from_env(parts[2]) if len(parts) > 3 else cls.PRODUCTION
            except Exception as e:
                return cls.from_hostname(hn)

        return cls.LOCAL
    
    def __eq__(self, other: Any) -> bool:
        """
        Equality operator
        """
        if isinstance(other, str): return self.value == other.lower()
        return self.value == other.value if isinstance(other, AppEnv) else False

    @property
    def is_devel(self) -> bool:
        """
        Returns True if the app environment is development
        """
        return self in [self.LOCAL, self.CICD, self.DEVELOPMENT, self.STAGING, self.TEST]

    @property
    def is_local(self) -> bool:
        """
        Returns True if the app environment is local
        """
        return self in [self.LOCAL, self.CICD]

    @property
    def name(self) -> str:
        """
        Returns the name in lower
        """
        return self.value.lower()

    @property
    def short_name(self) -> str:
        """
        Returns the short name in lower
        """
        if self == self.DEVELOPMENT: return 'dev'
        return 'prod' if self == self.PRODUCTION else self.name
    
    def select(self, values: Dict[Union[str, 'AppEnv'], Any], default: Optional[Any] = None) -> Any:
        """
        Returns the value for the app env
        """
        return next((value for key, value in values.items() if key == self), default)


    @classmethod
    def extend(cls, name: str, value: Any):
        """
        Extends the enum with a new value
        """
        if not _EXTEND_SUPPORTED: raise ImportError('aenum is not installed. Please install it to use this feature')
        extend_enum(cls, name, value)




def get_app_env(
    module_name: str,
) -> AppEnv:
    """
    Retrieves the app environment
    """
    module_name = module_name.replace(".", "_").upper()
    for key in {
        "SERVER_ENV",
        f"{module_name}_ENV",
        "APP_ENV",
        "ENVIRONMENT",
    }:
        if env_value := os.getenv(key):
            return AppEnv.from_env(env_value)

    from lzo.utils.system import is_in_kubernetes, get_host_name
    if is_in_kubernetes():
        # Name should be
        # scout-<service>-<index>
        # or 
        # scout-<service>-<env>-<index>
        hn = get_host_name()
        try:
            parts = hn.split("-")
            return AppEnv.from_env(parts[1]) if len(parts) > 2 else AppEnv.PRODUCTION
        except Exception as e:
            return AppEnv.from_hostname(hn)
        # parts = get_host_name().split("-")
        # return AppEnv.from_env(parts[2]) if len(parts) > 3 else AppEnv.PRODUCTION
    
    return AppEnv.LOCAL
