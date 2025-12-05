# lzo.registry - Object Registries

The `lzo.registry` module provides patterns for managing global object registries, plugins, and configuration settings. It supports lazy instantiation, hook injection, and string-based import resolution.

## MRegistry

The `MRegistry` (Mutable Registry) is the core class. It manages three internal maps:
1.  **mregistry**: Classes/Functions registered directly.
2.  **uninit_registry**: String import paths for lazy loading.
3.  **init_registry**: Cached, instantiated objects.

::: lzo.registry.base
    options:
      members:
        - MRegistry

### Usage Examples

#### Basic Registration

```python
from lzo.registry import MRegistry

# Create a named registry
Services = MRegistry("services")

# Register a class
@Services.register("email_sender")
class EmailService:
    def send(self, msg): ...

# Lazy instantiation (created on first access)
sender = Services.get("email_sender")
```

#### Lazy Import Paths

Register objects without importing them at the top level.

```python
# Registers the string path; import happens only when 'db' is requested
Services.register("db", "my_app.database.PostgresConnection")

# Triggers import and instantiation
db = Services.get("db") 
```

#### Lifecycle Hooks

Inject logic before or after object instantiation.

```python
def configure_db(db_instance):
    db_instance.connect()
    return db_instance

# Post-hook: runs after instantiation
Services.register_posthook("db", configure_db)

# Pre-hook: modifies kwargs before instantiation
def inject_credentials(**kwargs):
    kwargs['password'] = 'secret'
    return kwargs

Services.register_prehook("db", inject_credentials)
```

## Settings Registry

A specialized registry for application settings, often used with Pydantic `BaseSettings`.

::: lzo.registry.settings
    options:
      members:
        - register_settings
        - get_app_settings

### Usage

```python
from lzo.registry import register_settings, get_app_settings
from lzo.types import BaseSettings

# Define your settings
class AppConfig(BaseSettings):
    app_name: str = "MyApp"
    
    class Config:
        # Special attributes for registry
        _rmodule = "my_app"

# Register them
register_settings(AppConfig)

# Retrieve globally
config = get_app_settings("my_app")
print(config.app_name)
```

## Client Registry

Registry for managing API clients and services.

::: lzo.registry.clients
