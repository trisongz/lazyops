"""
Configuration Types
"""

import os
from enum import Enum
from typing import Any

class AppEnv(str, Enum):
    CICD = "cicd"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    LOCAL = "local"

    @classmethod
    def from_env(cls, env_value: str) -> "AppEnv":
        """
        Get the app environment from the environment variables
        """
        env_value = env_value.lower()
        if "cicd" in env_value or "ci/cd" in env_value: return cls.CICD
        if "prod" in env_value: return cls.PRODUCTION
        if "dev" in env_value: return cls.DEVELOPMENT
        if "staging" in env_value: return cls.STAGING
        if "local" in env_value: return cls.LOCAL
        raise ValueError(f"Invalid app environment: {env_value} ({type(env_value)})")
    
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
        return self in [AppEnv.LOCAL, AppEnv.CICD, AppEnv.DEVELOPMENT]

    @property
    def is_local(self) -> bool:
        """
        Returns True if the app environment is local
        """
        return self in [AppEnv.LOCAL, AppEnv.CICD]

    @property
    def name(self) -> str:
        """
        Returns the name in lower
        """
        return self.value.lower()


    


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

    from lazyops.utils.system import is_in_kubernetes, get_host_name
    if is_in_kubernetes():
        # Name should be
        # scout-<service>-<index>
        # or 
        # scout-<service>-<env>-<index>
        parts = get_host_name().split("-")
        return AppEnv.from_env(parts[2]) if len(parts) > 3 else AppEnv.PRODUCTION
    
    return AppEnv.LOCAL