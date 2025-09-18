# `lzl.io`

The `lzl.io` package surfaces tooling for working with file abstractions,
serialisation helpers, and lightweight persistence.  It acts as the I/O
backbone for the broader LazyOps ecosystem.

## Submodules
- **`lzl.io.ser`** – Registry-driven serializers that support JSON, pickle, and
  msgpack out of the box, with hooks for registering custom implementations.
- **`lzl.io.persistence`** – Durable key/value stores and temporary file
  helpers, backed by pluggable backends (local files, Redis, object storage,
  sqlite).
- **`lzl.io.file`** – High-level file façade for local and cloud object stores.
- **`lzl.io.queue`** – Experimental background queues for batching work.  The
  API is still stabilising; consult `docs/future-updates.md` before relying on
  it in production.

## Quick Start
```python
from lzl.io import File
from lzl.io.persistence import PersistentDict

# Normalise a path into the configured File backend
uploads = File("s3://my-bucket/uploads/")

# Create a local persistent dictionary
cache = PersistentDict(
    name="example",
    backend_type="local",
    serializer="json",
    file_path="/tmp/example-cache.json",
)
cache["greeting"] = "hello"
```

## Testing Notes
- Use `tmp_path` fixtures when exercising `PersistentDict`/`TemporaryData`
  helpers to avoid polluting real directories.
- Tests that import optional dependencies (e.g. `filelock`) should skip if the
  module is not available to keep CI runs deterministic.
