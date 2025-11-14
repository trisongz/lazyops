# lzo.utils - Utility Helpers

The `lzo.utils` module collects lightweight helper modules (retry decorators, key generators, formatting utilities) that avoid heavy dependencies.

## Module Reference

::: lzo.utils
    options:
      show_root_heading: true
      show_source: true

## Overview

The utils module provides a comprehensive set of utility functions and decorators that are commonly used across projects. These utilities are designed to be lightweight and have minimal dependencies.

## Submodules

### Helpers

General-purpose helper functions:

::: lzo.utils.helpers

### Key Generation

Generate consistent keys for caching and identification:

::: lzo.utils.keygen

### Hashing

Efficient hashing utilities:

::: lzo.utils.hashing

### Serialization

Data serialization helpers:

::: lzo.utils.serialization

## Usage Examples

### Retry Decorator

```python
from lzo.utils import retryable

@retryable(max_attempts=3, backoff=2.0)
def api_call():
    response = requests.get("https://api.example.com")
    response.raise_for_status()
    return response.json()

# Automatically retries on failure with exponential backoff
data = api_call()
```

### Key Generation

```python
from lzo.utils.keygen import generate_key

# Generate a unique key
key = generate_key("user", user_id=123, action="login")
# Returns: "user:123:login" or similar

# Use for caching
cache[generate_key("data", id=456)] = data
```

### Hashing

```python
from lzo.utils.hashing import hash_dict

# Generate consistent hash for dictionary
data = {"key": "value", "number": 42}
hash_value = hash_dict(data)

# Same data always produces same hash
assert hash_dict(data) == hash_value
```

### Formatting

```python
from lzo.utils.helpers.formatting import format_bytes, format_duration

# Format bytes for display
print(format_bytes(1234567))  # "1.18 MB"

# Format duration
print(format_duration(3665))  # "1h 1m 5s"
```

### Batching

```python
from lzo.utils.helpers.batching import batch_items

items = range(100)
for batch in batch_items(items, batch_size=10):
    process_batch(batch)
```

### Timing

```python
from lzo.utils.helpers.timing import Timer

with Timer() as timer:
    expensive_operation()

print(f"Operation took {timer.elapsed:.2f} seconds")
```

### Date Helpers

```python
from lzo.utils.helpers.dates import parse_date, format_date

# Parse various date formats
date = parse_date("2024-01-15")

# Format consistently
formatted = format_date(date, fmt="%Y-%m-%d")
```

### Environment Variables

```python
from lzo.utils.helpers.envvars import get_env_bool, get_env_int

# Get typed environment variables with defaults
debug = get_env_bool("DEBUG", default=False)
port = get_env_int("PORT", default=8000)
```

### Caching

```python
from lzo.utils.helpers.caching import memoize

@memoize
def expensive_function(x, y):
    # Results are cached
    return x * y

result = expensive_function(5, 10)  # Computed
result = expensive_function(5, 10)  # Cached
```

## Features

- **Retry Logic**: Automatic retry with exponential backoff
- **Key Generation**: Consistent key generation for caching
- **Hashing**: Fast, consistent hashing of complex objects
- **Formatting**: Human-readable formatting utilities
- **Batching**: Efficient batch processing
- **Timing**: Performance measurement
- **Date Handling**: Consistent date parsing and formatting
- **Environment Variables**: Type-safe environment variable access
- **Caching**: Simple memoization decorator

## Design Principles

The utils module follows these principles:

1. **Lightweight**: Minimal dependencies
2. **Reusable**: Generic, composable functions
3. **Type-Safe**: Full typing support
4. **Well-Tested**: Comprehensive test coverage
5. **Documented**: Clear examples and docstrings

## Performance Considerations

- Hash functions use xxhash for speed
- Caching decorators use LRU cache for efficiency
- Batching helpers minimize memory overhead
- Timer utilities have minimal overhead

The façade README at `src/lzo/utils/README.md` highlights the most common entry points; run `make test-lzo-utils` to confirm everything behaves as documented.
