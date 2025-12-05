# lzl.proxied - Proxy Objects

The `lzl.proxied` module provides the `ProxyObject` pattern, allowing for objects that are lazily initialized, thread-safe, and transparently proxied.

## ProxyObject

The generic proxy wrapper.

::: lzl.proxied.base
    options:
        members:
            - ProxyObject
            - new_method_proxy

## Usage Guide

### Deferred Initialization

Create an object that isn't instantiated until you access one of its attributes.

```python
from lzl.proxied import ProxyObject

def connect_db():
    print("Connecting to DB...")
    return DatabaseConnection()

# Connection is NOT established here
db = ProxyObject(obj_getter=connect_db)

def query():
    # Connection happens here, on first access
    return db.execute("SELECT * FROM users")
```

### Thread Safety

By default, `ProxyObject` includes a lock to ensure that initialization is thread-safe.

```python
# Safe to share across threads
global_resource = ProxyObject(
    obj_cls="my_lib.HeavyResource",
    threadsafe=True
)
```