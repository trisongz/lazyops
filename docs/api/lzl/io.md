# lzl.io - I/O Operations

The `lzl.io` module provides comprehensive input/output operations including serialization, persistence, file handling, and data compression.

## Modules

::: lzl.io
    options:
      show_root_heading: true
      show_source: false
      members_order: alphabetical

## Serialization

The serialization submodule provides various serializers for common data formats:

::: lzl.io.ser

## Persistence

Persistent storage backends for caching and data persistence:

::: lzl.io.persistence

## File Operations

File system operations with support for local and cloud storage:

::: lzl.io.file

## Compression

Data compression utilities:

::: lzl.io.compression

## Usage Examples

### Basic Serialization

```python
from lzl.io.ser import serialize, deserialize

# Serialize data
data = {"key": "value", "number": 42}
serialized = serialize(data)

# Deserialize data
restored = deserialize(serialized)
```

### Persistent Storage

```python
from lzl.io.persistence import PersistentDict

# Create a persistent dictionary
cache = PersistentDict("my_cache.db")
cache["key"] = "value"
cache.sync()  # Save to disk
```

### File Operations

```python
from lzl.io.file import read_file, write_file

# Read and write files
content = await read_file("input.txt")
await write_file("output.txt", content)
```
