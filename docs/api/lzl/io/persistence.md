# lzl.io.persistence - Data Persistence

The `lzl.io.persistence` module offers robust persistence mechanisms, providing a dictionary-like interface backed by various storage engines (SQLite, Redis, Object Storage). It supports caching, asynchronous access, and data serialization.

## Persistent Dictionary

The `PersistentDict` is the core class. It mimics a standard Python dictionary but persists its contents.

::: lzl.io.persistence.main
    options:
      members:
        - PersistentDict

## Initialization

```python
from lzl.io.persistence import PersistentDict

# Local SQLite backend (default if no scheme provided)
cache = PersistentDict("my_app_cache", serializer="json")

# Redis backend
redis_cache = PersistentDict(
    "my_redis_cache", 
    backend="redis", 
    base_key="app:v1",
    expiration=3600
)

# Object Storage backend (S3)
s3_cache = PersistentDict(
    "s3_cache",
    base_key="s3://my-bucket/cache/prefix",
    serializer="pickle"
)
```

## Features

### Async Support

Most methods have an `async` equivalent prefixed with `a` (e.g., `aget`, `aset`, `adelete`).

```python
await cache.aset("key", "value")
value = await cache.aget("key")
```

### Context Managers & Locking

Ensure data consistency with context managers that handle locking.

```python
# Sync context
with cache.acquire_context():
    cache["key"] = "new_value"
    # Changes are flushed on exit

# Async context
async with cache.acquire_acontext():
    await cache.aset("key", "async_value")
```

### Mutation Tracking

`PersistentDict` tracks changes to mutable objects (like lists or dicts) retrieved from the cache and saves them back if they are modified within a tracking context.

```python
with cache.track_changes("user:123", "get") as user_data:
    user_data["login_count"] += 1
# user_data is automatically saved back to the backend if it changed
```

### Math & Set Operations

Native support for atomic increments and set operations (especially useful with Redis).

```python
# Increment
cache.incr("counter", 1)

# Set operations
cache.sadd("users", "alice", "bob")
members = cache.smembers("users")
```

## Backends

Supported backends implementations.

- **Local**: Stores data in local files.
- **SQLite**: High-performance, single-file database (Recommended for local persistence).
- **Redis**: Distributed in-memory store.
- **Object Storage**: S3, MinIO, R2 for cloud persistence.

::: lzl.io.persistence.backends

## Serialization

Data is serialized before storage. Supported formats:
- `json`: Human-readable, widely supported.
- `pickle`: Python-specific, supports complex objects.
- `msgpack`: Binary, efficient.

You can configure compression (gzip, zstd) alongside serialization.

## Metrics

Attach metrics to track usage or values within the dictionary.

```python
from lzl.io.persistence.addons import CountMetric

cache.configure_metric("hits", kind="count")
cache.metrics["hits"].incr()
```