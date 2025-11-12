# lzo - Lazy Objects/Registry

The `lzo` namespace provides object registry patterns, state management, settings configuration, and related functionalities.

## Key Modules

- **[Registry](registry.md)**: Object registry with lifecycle hooks and dependency injection
- **[Types](types.md)**: Pydantic-based configuration and settings management
- **[Utils](utils.md)**: Lightweight utility helpers for common operations

## Overview

The `lzo` toolkit focuses on object lifecycle management, configuration handling, and reusable patterns for building robust applications. It provides a clean, type-safe way to manage application state and dependencies.

### Installation

The `lzo` module is included with the base `lazyops` installation:

```bash
pip install lazyops
```

### Quick Example

```python
import lzo
from lzo.registry import MRegistry
from lzo.types import BaseSettings

# Define configuration
class AppConfig(BaseSettings):
    app_name: str
    debug: bool = False

# Register and retrieve
registry = MRegistry()
registry.register('config', AppConfig(app_name="MyApp"))
config = registry.get('config')
```

## Core Concepts

### Registry Pattern

The registry pattern provides a centralized way to manage objects throughout your application's lifecycle. It supports:

- **Lifecycle Hooks**: Pre/post instantiation callbacks
- **Dependency Injection**: Automatic resolution of dependencies
- **Singleton Management**: Control object creation and reuse
- **Type Safety**: Full typing support with Pydantic

### Settings Management

The types module extends Pydantic's settings management with:

- **Environment Integration**: Automatic environment variable loading
- **Validation**: Type-safe configuration validation
- **Serialization**: Easy conversion to/from various formats
- **Nested Configuration**: Support for complex configuration structures

### Utility Helpers

The utils module provides lightweight helpers that avoid heavy dependencies:

- **Retry Decorators**: Automatic retry with exponential backoff
- **Key Generators**: Consistent key generation for caching
- **Formatting**: String and data formatting utilities
- **Batching**: Efficient batch processing helpers

## Architecture

The `lzo` namespace follows these design principles:

1. **Type Safety**: Extensive use of type hints and Pydantic models
2. **Minimal Dependencies**: Keep the core lightweight
3. **Extensibility**: Easy to extend with custom patterns
4. **Documentation**: Well-documented with clear examples

Browse the sidebar to explore specific modules and their documentation.
