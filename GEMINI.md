# LazyOps (lazyops)

## Project Overview

**LazyOps** is a Python library designed to provide a collection of utility modules and object registry patterns for building robust applications. It is currently under active refactoring to migrate core functionality into two distinct namespaces:

*   **`lzl` (Lazy Libraries/Utilities):** Foundational utilities, async helpers, API clients, I/O operations, logging, and type definitions.
*   **`lzo` (Lazy Objects/Registry):** Object registry patterns, state management, and configuration settings.

**Key Technologies:** Python 3.10+, Pydantic v2, AnyIO, Loguru, Typer.

## Architecture

The codebase is organized into a `src` layout:

*   `src/lzl/`: Contains the utility modules (e.g., `io`, `logging`, `pool`, `proxied`, `require`).
*   `src/lzo/`: Contains the object registry and pattern modules (e.g., `registry`, `types`, `utils`).
*   `tests/`: Comprehensive test suite using `pytest`, mirrored to the source structure.

## Development Workflow

### Installation

To install the package in editable mode with all dependencies:

```bash
pip install -e ".[dev,docs,file,kops,fastapi]"
```

### Build & Run

The project uses `setuptools` configured via `pyproject.toml`.

*   **CLI:** The project exposes a CLI entry point `lzl` (mapped to `lzl.cmd:main`).

### Testing

The project relies heavily on `pytest` and a `Makefile` to manage test execution.

**Common Test Commands:**

*   `make test`: Run the entire test suite.
*   `make test-lzl`: Run all documentation-focused submodule tests for `lzl`.
    *   Specific modules: `make test-lzl-io`, `make test-lzl-logging`, `make test-lzl-pool`, etc.
*   `make test-lzo`: Run all `lzo` suite tests.
    *   Specific modules: `make test-lzo-registry`, `make test-lzo-types`.

### Documentation

Documentation is built using **MkDocs** with the Material theme and **Mintlify**.

*   `make mkdocs-serve`: Serve documentation locally at `http://127.0.0.1:8000/`.
*   `make mkdocs-build`: Build static documentation.
*   `make docs-preview`: Preview via Mintlify.

## Key Files & Configuration

*   **`pyproject.toml`**: Defines project metadata, dependencies (including optional groups like `kops`, `fastapi`), and build system.
*   **`Makefile`**: The central entry point for running tests and documentation tasks.
*   **`src/lzl/` & `src/lzo/`**: Core source code directories.
*   **`README.md`**: Project overview and basic usage examples.

## Conventions

*   **Namespaces:** strictly adhere to `lzl` for utilities and `lzo` for registry/objects.
*   **Async First:** The library leans heavily on `anyio` and async patterns.
*   **Pydantic:** Extensive use of Pydantic models and settings (`BaseSettings`, `BaseModel`) for configuration and validation.
