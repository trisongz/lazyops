# lzl.require - Dependency Management

The `lzl.require` module provides dependency resolution and requirement management utilities.

## Module Reference

::: lzl.require
    options:
      show_root_heading: true
      show_source: true

## Overview

The require module helps manage optional dependencies and ensures that required packages are available before use.

## Usage Examples

### Basic Requirement Checking

```python
from lzl.require import require

# Ensure a package is available
require('numpy')
import numpy as np

# Multiple packages
require(['pandas', 'matplotlib'])
```

### Optional Dependencies

```python
from lzl.require import optional_require

# Try to import, return None if not available
numpy = optional_require('numpy')

if numpy is not None:
    array = numpy.array([1, 2, 3])
else:
    print("NumPy not available, using fallback")
```

### Version Checking

```python
from lzl.require import require_version

# Ensure minimum version
require_version('requests', '2.28.0')
```

### Installation Hints

```python
from lzl.require import require_with_hint

# Provide installation instructions
require_with_hint(
    'torch',
    install_hint="Install with: pip install torch"
)
```

### Dependency Groups

```python
from lzl.require import require_group

# Check for a group of related dependencies
require_group('ml', [
    'numpy',
    'pandas',
    'scikit-learn',
])
```

## Features

- **Automatic Checking**: Verify dependencies at import time
- **Clear Error Messages**: Helpful installation instructions
- **Version Validation**: Ensure compatible versions are installed
- **Optional Dependencies**: Graceful degradation when optional packages are missing
- **Group Management**: Manage related dependencies together

## Use Cases

- **Optional Features**: Features that require additional packages
- **Plugin Systems**: Validate plugin dependencies
- **Environment Validation**: Ensure development environment is properly configured
- **Documentation**: Make dependencies explicit in code

## Best Practices

1. Check requirements early in your module's initialization
2. Provide clear installation instructions in error messages
3. Use optional requirements for non-critical features
4. Group related dependencies for easier management
