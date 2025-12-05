# lzl.load - Lazy Loading

The `lzl.load` module provides the `LazyLoad` proxy and other utilities for deferred imports. This pattern drastically reduces application startup time by only loading heavy dependencies when they are first accessed.

## Key Components

### LazyLoad

The core proxy class. It intercepts attribute access to trigger the import.

::: lzl.load.main
    options:
        members:
            - LazyLoad
            - lazy_load
            - load
            - reload

## Usage Guide

### Basic Lazy Loading

Instead of top-level imports, define a proxy.

```python
from lzl.load import LazyLoad

# 'numpy' is NOT imported yet
np = LazyLoad("numpy")

def process_data(data):
    # 'numpy' is imported here, on the first attribute access
    return np.array(data)
```

### Handling Optional Dependencies

You can configure `LazyLoad` to automatically install missing packages (though use with caution in production).

```python
# If 'pandas' is missing, it will attempt to pip install it
pd = LazyLoad("pandas", install_missing=True)
```

### Dependency Chains

If a module depends on another lazy module being loaded first (e.g., for side effects), you can declare dependencies.

```python
# specific_setup must be loaded before my_module
setup = LazyLoad("my_app.specific_setup")
mod = LazyLoad("my_app.my_module", dependencies=setup)
```

### Type Checking

For static analysis (mypy/pyright), you can use `TYPE_CHECKING` blocks to keep type hints working while using lazy loading at runtime.

```python
from typing import TYPE_CHECKING
from lzl.load import LazyLoad

if TYPE_CHECKING:
    import pandas as pd
else:
    pd = LazyLoad("pandas")

def get_df() -> "pd.DataFrame":
    return pd.DataFrame()
```