"""
Common Type Definitions and Enumerations.

This module provides frequently used type aliases like `Final` and `Literal`,
base string enumeration classes (`StrEnum`, `UpperStrEnum`), and a specific
enumeration for application environments (`AppEnv`).
"""

import os
import sys
from enum import Enum, EnumMeta
from functools import singledispatchmethod
from typing import Any, Union, Dict, Optional, TypeVar, Type, TYPE_CHECKING

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
    """Metaclass for StrEnum to allow indexing and reversed members."""

    @singledispatchmethod
    def __getitem__(self, key):
        return super().__getitem__(key)

    @__getitem__.register
    def _(self, index: int):
        """Allows accessing enum members by integer index."""
        return list(self)[index]
    
    @property
    def _reversed_members_(cls) -> Dict[str, str]:
        """Returns a mapping from enum values back to member names."""
        return {v: k for k, v in cls.__members__.items()}

from .base import PYDANTIC_VERSION

def _get_serialized_value(value: Union[str, 'StrEnum']) -> str:
    """Returns the serialized value for StrEnum (its name or the string itself).

    Used for Pydantic v2 serialization.

    Args:
        value: The StrEnum member or a string.

    Returns:
        str: The name of the enum member or the original string.
    """
    return value.name if hasattr(value, 'name') else value
    
class StrEnum(str, Enum, metaclass=StrEnumMeta):
    """String enumeration with case-insensitive comparison and Pydantic v2 support.

    Inherits from `str` and `Enum`. Comparisons with strings ignore case.
    Includes helper methods for validation and extending the enum dynamically
    (if `aenum` is installed).
    """

    def __eq__(self, other: Any) -> bool:
        """Compares with another value, ignoring case if `other` is a string."""
        return self.value.lower() == other.lower() if \
            isinstance(other, str) else \
                super().__eq__(other)
    
    def __ne__(self, other: Any) -> bool:
        """Compares with another value for inequality, ignoring case if `other` is a string."""
        return self.value.lower() != other.lower() if \
            isinstance(other, str) else \
                super().__ne__(other)

    def __str__(self) -> str:
        """Returns the string representation of the enum member's value."""
        return str.__str__(self)
    
    def __hash__(self) -> int:
        """Returns a unique hash based on the object's identity."""
        # Use id() for hashing as string value might not be unique if extended
        return id(self)
    
    @classmethod
    def extend(cls, name: str, value: Any):
        """Dynamically extends the enum with a new member.

        Requires the `aenum` library to be installed.

        Args:
            name: The name of the new enum member.
            value: The value of the new enum member.

        Raises:
            ImportError: If `aenum` is not installed.
        """
        if not _EXTEND_SUPPORTED: raise ImportError('aenum is not installed. Please install it to use this feature')
        extend_enum(cls, name, value)

    @classmethod
    def __validate__(cls: Type['StrEnumT'], value: Union[str, 'StrEnumT']) -> 'StrEnumT':
        """Validates and converts a value to an enum member.

        Used by Pydantic v2. Handles case-insensitive matching against both member
        names and values.

        Args:
            value: The input value (string or existing enum member).

        Returns:
            StrEnumT: The corresponding enum member.

        Raises:
            ValueError: If the value does not correspond to any enum member.
        """
        if isinstance(value, cls): return value # Already the correct type
        # if hasattr(value, '__members__'): return value
        # return cls(value.__name__)
        reversed_members = cls._reversed_members_
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
            """Generates the Pydantic v2 JSON schema for this enum.

            Returns a schema with an 'enum' list containing member names.

            Args:
                _core_schema: The Pydantic core schema (unused).
                _handler: The Pydantic JSON schema handler (unused).

            Returns:
                JsonSchemaValue: A dictionary representing the JSON schema.
            """
            return {'enum': [m.name for m in cls], 'type': 'string'}

        @classmethod
        def __get_pydantic_core_schema__(
            cls, 
            source: type[Any], 
            handler: 'GetCoreSchemaHandler'
        ) -> 'core_schema.CoreSchema':
            """Generates the Pydantic v2 CoreSchema for validation.

            Uses the `__validate__` method for validation and specifies
            serialization behavior.

            Args:
                source: The source type being validated.
                handler: The Pydantic core schema handler.

            Returns:
                core_schema.CoreSchema: The Pydantic core schema.
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
    """String enumeration that performs comparisons in uppercase.

    Inherits from `StrEnum`, but converts both self and the other value
    to uppercase before comparison if the other value is a string.
    """

    def __eq__(self, other: Any) -> bool:
        """Compares with another value, converting to uppercase if `other` is a string."""
        return self.value.upper() == other.upper() if \
            isinstance(other, str) else \
                super().__eq__(other)
    
    def __ne__(self, other: Any) -> bool:
        """Compares with another value for inequality, converting to uppercase if `other` is a string."""
        return self.value.upper() != other.upper() if \
            isinstance(other, str) else \
                super().__ne__(other)
    

    def __str__(self) -> str:
        """Returns the string representation of the enum member's value."""
        return str.__str__(self)
    
    def __hash__(self) -> int:
        """Returns a unique hash based on the object's identity."""
        return id(self)



class AppEnv(str, Enum):
    """Enumeration for different application deployment environments."""
    CICD = "cicd"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"
    TEST = "test"

    @classmethod
    def from_env(cls, env_value: str) -> "AppEnv":
        """Determines the AppEnv from a string value (case-insensitive).

        Args:
            env_value: The string representation of the environment
                (e.g., "production", "dev", "CICD").

        Returns:
            AppEnv: The corresponding enum member.

        Raises:
            ValueError: If the `env_value` does not match any known environment.
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
        """Determines the AppEnv based on keywords in a hostname (case-insensitive).

        Defaults to LOCAL or PRODUCTION if specific keywords aren't found.

        Args:
            hostname: The hostname string.

        Returns:
            AppEnv: The inferred enum member.
        """
        hostname = hostname.lower()
        if "dev" in hostname: return cls.DEVELOPMENT
        if "staging" in hostname: return cls.STAGING
        if "test" in hostname: return cls.TEST
        return cls.LOCAL if "local" in hostname else cls.PRODUCTION
        
    
    @classmethod
    def from_module_name(cls, module_name: str) -> 'AppEnv':
        """Determines the AppEnv by checking environment variables or hostname.

        Checks standard environment variables (SERVER_ENV, APP_ENV, etc.) first.
        If running in Kubernetes, attempts to parse the hostname.
        Falls back to LOCAL.

        Args:
            module_name: The name of the calling module, used to construct
                potential environment variable names (e.g., MYMODULE_ENV).

        Returns:
            AppEnv: The determined application environment.
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
            except Exception as e:
                return cls.from_hostname(hn)

        return cls.LOCAL
    
    def __eq__(self, other: Any) -> bool:
        """Compares AppEnv with another value (string or AppEnv), ignoring case for strings."""
        if isinstance(other, str): return self.value == other.lower()
        return self.value == other.value if isinstance(other, AppEnv) else False

    @property
    def is_devel(self) -> bool:
        """Checks if the environment is considered a development/testing environment."""
        return self in [self.LOCAL, self.CICD, self.DEVELOPMENT, self.STAGING, self.TEST]

    @property
    def is_local(self) -> bool:
        """Checks if the environment is considered local (incl. CI/CD)."""
        return self in [self.LOCAL, self.CICD]

    @property
    def name(self) -> str:
        """Returns the lowercase string value of the environment name."""
        return self.value.lower()

    @property
    def short_name(self) -> str:
        """Returns a shortened lowercase name ('dev', 'prod', or the full name)."""
        if self == self.DEVELOPMENT: return 'dev'
        return 'prod' if self == self.PRODUCTION else self.name
    
    def select(self, values: Dict[Union[str, 'AppEnv'], Any], default: Optional[Any] = None) -> Any:
        """Selects a value from a dictionary based on the current AppEnv.

        Allows matching the dictionary keys against the current environment
        enum member.

        Args:
            values: A dictionary mapping environment names (str or AppEnv)
                to corresponding values.
            default: The default value to return if the current environment
                is not found in the keys. Defaults to None.

        Returns:
            The value associated with the current environment, or the default.
        """
        # Use self (the AppEnv member) directly for comparison thanks to __eq__
        return next((value for key, value in values.items() if key == self), default)


    @classmethod
    def extend(cls, name: str, value: Any):
        """Dynamically extends the AppEnv enum with a new member.

        Requires the `aenum` library to be installed.

        Args:
            name: The name of the new enum member.
            value: The value of the new enum member.

        Raises:
            ImportError: If `aenum` is not installed.
        """
        if not _EXTEND_SUPPORTED: raise ImportError('aenum is not installed. Please install it to use this feature')
        extend_enum(cls, name, value)




def get_app_env(
    module_name: str,
) -> AppEnv:
    """Retrieves the current application environment.

    Alias for `AppEnv.from_module_name`.

    Args:
        module_name: The name of the calling module, used to construct
            potential environment variable names.

    Returns:
        AppEnv: The determined application environment.
    """
    # This function seems to duplicate the logic of AppEnv.from_module_name,
    # including the Kubernetes check. Consider calling cls.from_module_name here.
    # Keeping original logic for now, but flagging for potential refactor.
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
    
    return AppEnv.LOCAL
