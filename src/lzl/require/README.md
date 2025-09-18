# `lzl.require`

Helpers for detecting, importing, and (optionally) installing optional
dependencies.  The module wraps common patterns such as "import-if-available"
with sensible defaults and logging so that LazyOps consumers can request third
party tooling without sprinkling installation logic throughout the codebase.

## Common Patterns
- **`LazyLib.import_lib`** – Import a top-level package, installing it on demand
  when permitted.
- **`LazyLib.get`** – Resolve dotted module paths (and optional attributes) with
  a shorthand syntax like `"pip.__main:main"`.
- **`resolve_missing`** – Batch-ensure that a list of modules is present before
  executing a higher-level workflow.
- **`require_missing_wrapper`** – Decorator factory that runs a resolver before
  the wrapped callable, handling both sync and async functions.

## Example
```python
from lzl.require import LazyLib, resolve_missing

resolve_missing(["pip"])  # no-op if pip is already installed

pkg_resources = LazyLib.get("setuptools|pkg_resources")
console_main = LazyLib["pip.__main:main"]
```

## Testing Notes
- Patch `subprocess.check_call` in tests that exercise installer helpers to
  avoid mutating the development environment.
- Use standard-library modules that ship with `pip` (for example `pip` or
  `setuptools`) when verifying availability checks.
