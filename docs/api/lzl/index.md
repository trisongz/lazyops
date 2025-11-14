# lzl - Lazy Libraries/Utilities

The `lzl` namespace contains foundational utilities, asynchronous helpers, common API client interfaces, I/O operations, logging, type definitions, and more.

## Key Modules

- **[IO](io.md)**: Input/output operations including serialization, persistence, and file handling
- **[Load](load.md)**: Lazy loading utilities for deferred imports
- **[Logging](logging.md)**: Logging configuration and utilities
- **[Pool](pool.md)**: Thread pool and async execution helpers
- **[Proxied](proxied.md)**: Proxy object patterns for lazy initialization
- **[Require](require.md)**: Dependency resolution and requirement management
- **[Sysmon](sysmon.md)**: System monitoring and resource tracking

## Overview

The `lzl` toolkit provides a comprehensive set of utilities that are commonly used across internal development projects. These utilities are designed to be lightweight, performant, and easy to integrate into existing codebases.

### Installation

The `lzl` module is included with the base `lazyops` installation:

```bash
pip install lazyops
```

### Quick Example

```python
import lzl
from lzl.logging import logger
from lzl.load import LazyLoad

# Use lazy loading
lazy_module = LazyLoad('expensive.module')

# Configure logging
logger.info("Starting application")
```

## Architecture

The `lzl` namespace is organized into several key areas:

- **API Clients**: HTTP clients, database connectors, and external service integrations
- **I/O Operations**: File handling, serialization, and data persistence
- **Utilities**: Common helpers for async operations, caching, and more
- **Extensions**: Optional integrations with FastAPI, Temporal, and other frameworks

Browse the sidebar to explore specific modules and their documentation.
