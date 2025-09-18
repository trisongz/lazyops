# `lzl.load`

The `lzl.load` package provides lightweight primitives for deferring imports and
wrapping expensive initialisation logic.  Use these helpers when optional
dependencies should only be pulled in once they are actually needed by the
runtime.

## Key Exports
- **`LazyLoad`** – Proxy object that lazily imports a module on demand.  Use
  `load(lazy_module)` when eager resolution is required.
- **`lazy_import`** – Cached utility for resolving dotted import paths into
  modules, classes, or callables.
- **`lazy_function_wrapper`** – Decorator factory for deferring wrapper
  creation until the wrapped function is invoked.
- **Utility helpers** – Functions such as `import_from_string`,
  `import_function`, and `validate_callable` make it easy to work with dotted
  paths in configuration files.

## Example
```python
from lzl.load import LazyLoad, lazy_function_wrapper

# Lazily load an optional dependency
orjson = LazyLoad("orjson", install_missing=False)

# Turn a function into a cached singleton once it is first called
@lazy_function_wrapper(lambda: lambda fn: lambda *a, **kw: fn(*a, **kw))
def build_client():
    ...
```

## Testing Notes
- Prefer standard-library modules (e.g. `math`) in tests to avoid installing
  additional dependencies when exercising `LazyLoad`.
- When asserting wrapper behaviour, track side effects (e.g. via a list) rather
  than relying on global module state.
