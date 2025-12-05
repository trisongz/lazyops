# lzo.utils - Utilities

The `lzo.utils` module is a collection of lightweight, dependency-free helpers for common tasks like hashing, serialization, and system interaction.

## Submodules

### Hashing
Consistent hashing for objects and arguments.
::: lzo.utils.hashing

### Key Generation
Helpers for generating secrets, UUIDs, and API keys.
::: lzo.utils.keygen

### Serialization
Unified serialization interface.
::: lzo.utils.serialization

### Async Exit
Utilities for handling async shutdown and exit signals.
::: lzo.utils.aioexit

### File Stream
File streaming utilities.
::: lzo.utils.filestream

### Logs
Logging helpers.
::: lzo.utils.logs

## Usage Guide

### Generating Keys

```python
from lzo.utils.keygen import Generate

# Random 16-char alphanumeric string
key = Generate.alphanumeric_passcode(16)

# UUID
uid = Generate.uuid()
```

### Object Hashing

Create deterministic hashes for complex objects (dicts, Pydantic models).

```python
from lzo.utils.hashing import create_object_hash

data = {"a": 1, "b": [2, 3]}
hash_val = create_object_hash(data)
```