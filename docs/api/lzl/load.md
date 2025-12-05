# lzl.load - Lazy Loading

The `lzl.load` module provides utilities for lazy loading of modules and dependencies, enabling deferred imports and reducing startup time.

## Module Reference

::: lzl.load
    options:
      show_root_heading: true
      show_source: true

## Overview

Lazy loading defers the import of modules until they are actually needed, which can significantly improve application startup time and reduce memory footprint.

## Usage Examples

### Basic Lazy Loading

```python
from lzl.load import LazyLoad

# Create a lazy reference to a module
numpy = LazyLoad('numpy')

# The module is only imported when accessed
array = numpy.array([1, 2, 3])  # Import happens here
```

### Lazy Loading with Aliases

```python
from lzl.load import LazyLoad

# Load with an alias
pd = LazyLoad('pandas', 'pd')

# Use as normal
df = pd.DataFrame({'a': [1, 2, 3]})
```

### Conditional Imports

```python
from lzl.load import LazyLoad

# Only import if actually used
optional_module = LazyLoad('some.optional.module')

if needs_feature:
    optional_module.do_something()
```

## Benefits

- **Faster Startup**: Modules are only imported when needed
- **Reduced Memory**: Unused modules don't consume memory
- **Simplified Dependencies**: Optional dependencies can be handled gracefully
- **Better Testing**: Mock imports more easily in tests

## Implementation Details

The `LazyLoad` class uses Python's import system to defer module loading. When you access an attribute on a lazy-loaded module, the actual import is triggered transparently.
