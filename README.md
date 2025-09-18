# lazyops: Lazy Operations Toolkit (lzl / lzo)

[![PyPI version](https://badge.fury.io/py/lazyops.svg)](https://badge.fury.io/py/lazyops)
<!-- Add other badges here later: e.g., Build Status, Code Coverage -->

A Python library providing a collection of utility modules (`lzl`) and object registry patterns (`lzo`) for building robust applications.

## ⚠️ Project Status: Under Active Refactoring

This library is currently undergoing a major refactoring (targeting version `v0.3.x` and above).

The core functionality is being migrated from the older `lazyops` namespace (versions `v0.2.x` and below) into two distinct, more focused namespaces:

*   **`lzl` (Lazy Libraries/Utilities):** Contains foundational utilities, asynchronous helpers, common API client interfaces, I/O operations, logging, type definitions, and more.
*   **`lzo` (Lazy Objects/Registry):** Provides object registry patterns, state management, settings configuration, and related functionalities.

Expect potential API changes and improvements during this transition. The previous `v0.2.x` implementation is available under the corresponding git tag if needed.

---

### Installation

Install the latest version from PyPI:

```bash
pip install --upgrade lazyops
```

Or install directly from GitHub for the latest development version:

```bash
pip install --upgrade git+https://github.com/trisongz/lazyops.git
```

---

### Basic Usage (Illustrative)

```python
# Import from the new namespaces
import lzl
import lzo

# Example using lzl logging (assuming configuration)
from lzl.logging import logger
logger.info("Logging configured via lzl!")

# Example using lzo registry (illustrative)
# Assuming 'my_settings' are registered somewhere
from lzo.registry import settings
# app_config = settings['my_settings']
# print(f"Loaded setting: {app_config.some_value}")

# Example using lzl utils (e.g., async helper)
# import asyncio
# from lzl.utils import run_as_coro
#
# def my_sync_function(x):
#    return x * 2
#
# async def main():
#    result = await run_as_coro(my_sync_function, 5)
#    print(f"Async result: {result}")
#
# asyncio.run(main())

```
*(More detailed usage examples will be added as the refactoring progresses).*

---

### Module Highlights

- **`lzo.registry`** – Provides the `MRegistry` core with hook support for
  pre/post instantiation along with helpers for registering clients and
  settings.  See `src/lzo/registry/README.md` for an overview and run
  `make test-lzo-registry` to exercise the accompanying tests.
- **`lzo.types`** – Re-exports the LazyOps pydantic wrappers such as
  `BaseSettings` and `BaseModel`, streamlining environment-aware
  configuration.  Quick-start examples live in `src/lzo/types/README.md` and
  can be validated with `make test-lzo-types`.
- **`lzo.utils`** – Collects lightweight helper modules (retry decorators,
  key generators, formatting utilities) that avoid heavy dependencies.  The
  façade README at `src/lzo/utils/README.md` highlights the most common entry
  points; run `make test-lzo-utils` to confirm everything behaves as
  documented.

---

### Core Dependencies

*   Python 3.7+
*   [pydantic](https://github.com/pydantic/pydantic): Used for data validation and settings management.
*   Other foundational libraries used internally (e.g., `aiohttpx`, `loguru`, `async_lru`).

*(A more detailed dependency list will be maintained in `setup.py` or `pyproject.toml`)*.

---

### Contributing

Contributions are welcome! Please read the **[`CONTRIBUTING.md`](CONTRIBUTING.md)** file for guidelines on code style, formatting, type hinting, docstrings, and the development process.

---

### License

This project is licensed under the MIT License - see the [`LICENSE`](LICENSE) file for details.
