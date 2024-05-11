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
    TEST = "test"

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

        from lazyops.utils.system import is_in_kubernetes, get_host_name
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
                # for e in {'dev', 'test', 'staging', 'local'}:
                # parts = [p for p in parts if any({
                #     p.lower() in {'dev', 'development', 'test', 'staging', 'local'}
                # }
                #     p.lower()
                # ]
                # if parts:
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
        hn = get_host_name()
        try:
            parts = hn.split("-")
            return AppEnv.from_env(parts[1]) if len(parts) > 2 else AppEnv.PRODUCTION
        except Exception as e:
            return AppEnv.from_hostname(hn)
        # parts = get_host_name().split("-")
        # return AppEnv.from_env(parts[2]) if len(parts) > 3 else AppEnv.PRODUCTION
    
    return AppEnv.LOCAL
