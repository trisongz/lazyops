# lzl.proxied - Proxy Objects

The `lzl.proxied` module provides proxy object patterns for lazy initialization and dynamic behavior.

## Module Reference

::: lzl.proxied
    options:
      show_root_heading: true
      show_source: true

## Overview

Proxy objects allow you to defer initialization of expensive resources until they are actually needed, and to intercept attribute access for dynamic behavior.

## Usage Examples

### Lazy Initialization

```python
from lzl.proxied import ProxyObject

class ExpensiveResource:
    def __init__(self):
        # Expensive initialization
        self.data = load_large_dataset()
    
    def process(self):
        return self.data

# Create a proxy - doesn't initialize yet
resource = ProxyObject(ExpensiveResource)

# Initialization happens on first access
result = resource.process()
```

### Proxy Dictionary

```python
from lzl.proxied import ProxyDict

# Create a dictionary that proxies access
registry = ProxyDict()

registry['config'] = lambda: load_config()
registry['database'] = lambda: connect_database()

# Values are only created when accessed
config = registry['config']  # load_config() called here
```

### Dynamic Behavior

```python
from lzl.proxied import ProxyObject

class LoggingProxy(ProxyObject):
    def __getattr__(self, name):
        print(f"Accessing: {name}")
        return super().__getattr__(name)

obj = LoggingProxy(MyClass())
obj.method()  # Logs "Accessing: method" before calling
```

## Features

- **Deferred Initialization**: Resources created only when needed
- **Transparent Access**: Proxies behave like the underlying object
- **Interception**: Hook into attribute access and method calls
- **Memory Efficient**: Avoid loading unnecessary resources

## Use Cases

- **Configuration Management**: Lazy load configuration files
- **Database Connections**: Defer connection until first query
- **API Clients**: Initialize clients only when making requests
- **Resource Pooling**: Manage expensive resource allocation

## Implementation Details

The proxy pattern uses Python's `__getattr__` and `__setattr__` methods to intercept attribute access and forward it to the underlying object after initialization.
