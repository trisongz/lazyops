# lzo.registry - Object Registry

The `lzo.registry` module provides the `MRegistry` core with hook support for pre/post instantiation along with helpers for registering clients and settings.

## Module Reference

::: lzo.registry
    options:
      show_root_heading: true
      show_source: true

## Overview

The registry pattern centralizes object lifecycle management with support for dependency injection, singleton patterns, and lifecycle hooks.

## Usage Examples

### Basic Registry

```python
from lzo.registry import MRegistry

# Create a registry
registry = MRegistry()

# Register an object
registry.register('config', {'key': 'value'})

# Retrieve the object
config = registry.get('config')
```

### Factory Registration

```python
from lzo.registry import MRegistry

registry = MRegistry()

# Register a factory function
def create_client():
    return DatabaseClient(host='localhost')

registry.register_factory('db', create_client)

# Client is created on first access
client = registry.get('db')
```

### Lifecycle Hooks

```python
from lzo.registry import MRegistry

registry = MRegistry()

def pre_init_hook(name, **kwargs):
    print(f"Creating {name}")
    return kwargs

def post_init_hook(name, instance):
    print(f"Created {name}")
    instance.setup()
    return instance

registry.register_hooks(
    pre_init=pre_init_hook,
    post_init=post_init_hook
)
```

### Settings Registry

```python
from lzo.registry import settings
from lzo.types import BaseSettings

class AppSettings(BaseSettings):
    api_key: str
    timeout: int = 30

# Register settings
settings.register('app', AppSettings)

# Access anywhere
app_config = settings['app']
```

### Client Registry

```python
from lzo.registry import clients

# Register API clients
clients.register('stripe', stripe_client)
clients.register('sendgrid', sendgrid_client)

# Access clients
stripe = clients['stripe']
```

## Features

- **Lazy Initialization**: Objects created only when accessed
- **Singleton Support**: Control whether objects are shared or recreated
- **Lifecycle Hooks**: Pre/post instantiation callbacks
- **Type Safety**: Full typing support
- **Thread Safety**: Safe for concurrent access
- **Dependency Injection**: Automatic resolution of dependencies

## Registry Patterns

### Global Registries

The module provides pre-configured global registries:

- `settings`: For application settings and configuration
- `clients`: For API clients and external services
- `state`: For application state management

### Custom Registries

Create custom registries for specific use cases:

```python
from lzo.registry import MRegistry

# Create a specialized registry
cache_registry = MRegistry()
cache_registry.register('user_cache', UserCache())
cache_registry.register('session_cache', SessionCache())
```

## Advanced Features

### Dependency Resolution

```python
registry.register('logger', create_logger)
registry.register('database', create_database, deps=['logger'])
# Database will have logger injected
```

### Context Managers

```python
with registry.scoped() as scoped_registry:
    # Objects created in this scope are automatically cleaned up
    scoped_registry.register('temp', TempResource())
# TempResource.__exit__() called here
```

See the `src/lzo/registry/README.md` file for detailed information and run `make test-lzo-registry` to exercise the tests.
