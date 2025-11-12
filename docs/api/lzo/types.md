# lzo.types - Type Definitions and Settings

The `lzo.types` module re-exports LazyOps pydantic wrappers such as `BaseSettings` and `BaseModel`, streamlining environment-aware configuration.

## Module Reference

::: lzo.types
    options:
      show_root_heading: true
      show_source: true

## Overview

The types module provides enhanced Pydantic models with additional functionality for configuration management, validation, and serialization.

## Usage Examples

### Basic Settings

```python
from lzo.types import BaseSettings

class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    username: str
    password: str
    database: str
    
    class Config:
        env_prefix = "DB_"

# Automatically loads from environment variables
# DB_HOST, DB_PORT, DB_USERNAME, DB_PASSWORD, DB_DATABASE
settings = DatabaseSettings()
```

### Base Model

```python
from lzo.types import BaseModel

class User(BaseModel):
    id: int
    username: str
    email: str
    active: bool = True

user = User(id=1, username="john", email="john@example.com")
```

### Environment-Aware Configuration

```python
from lzo.types import BaseSettings
from lzo.types.common import AppEnv

class AppSettings(BaseSettings):
    env: AppEnv = AppEnv.DEVELOPMENT
    debug: bool = True
    
    @property
    def is_production(self) -> bool:
        return self.env == AppEnv.PRODUCTION

settings = AppSettings()
if settings.is_production:
    # Production-specific logic
    pass
```

### Nested Configuration

```python
from lzo.types import BaseSettings, BaseModel

class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0

class CacheConfig(BaseModel):
    ttl: int = 3600
    redis: RedisConfig

class AppSettings(BaseSettings):
    cache: CacheConfig

settings = AppSettings()
print(settings.cache.redis.host)
```

### Validation and Serialization

```python
from lzo.types import BaseModel
from pydantic import validator

class APIConfig(BaseModel):
    url: str
    timeout: int = 30
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

# Validate
config = APIConfig(url="https://api.example.com")

# Serialize
config_dict = config.model_dump()
config_json = config.model_dump_json()
```

## Features

- **Environment Variables**: Automatic loading from environment
- **Type Validation**: Runtime type checking with Pydantic
- **Default Values**: Sensible defaults with override capability
- **Nested Models**: Support for complex configuration structures
- **Serialization**: Convert to/from dict, JSON, YAML
- **Immutability**: Optional frozen models for thread safety

## Configuration Patterns

### Development vs Production

```python
from lzo.types import BaseSettings
from lzo.types.common import AppEnv

class Settings(BaseSettings):
    env: AppEnv = AppEnv.DEVELOPMENT
    
    @property
    def database_url(self) -> str:
        if self.env == AppEnv.PRODUCTION:
            return "postgresql://prod-server/db"
        return "postgresql://localhost/dev_db"
```

### Secret Management

```python
from lzo.types import BaseSettings
from pydantic import SecretStr

class APISettings(BaseSettings):
    api_key: SecretStr
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = APISettings()
# Use get_secret_value() to access the secret
api_key = settings.api_key.get_secret_value()
```

### Multi-Environment Support

```python
from lzo.types import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    class Config:
        env_file = Path(".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            # Customize the order of configuration sources
            return (init_settings, env_settings, file_secret_settings)
```

## Best Practices

1. Use environment variables for sensitive configuration
2. Provide sensible defaults for optional settings
3. Validate configuration at startup, not at use time
4. Use nested models for related configuration groups
5. Document your settings with docstrings and field descriptions

Quick-start examples live in `src/lzo/types/README.md` and can be validated with `make test-lzo-types`.
