# lzl.logging - Logging Utilities

The `lzl.logging` module provides enhanced logging capabilities built on top of `loguru`, with additional configuration options and integration helpers.

## Module Reference

::: lzl.logging
    options:
      show_root_heading: true
      show_source: true

## Overview

The logging module provides a flexible, powerful logging system that integrates seamlessly with the rest of the `lzl` toolkit.

## Usage Examples

### Basic Logging

```python
from lzl.logging import logger

logger.info("Application started")
logger.debug("Debug information")
logger.warning("Warning message")
logger.error("Error occurred")
```

### Structured Logging

```python
from lzl.logging import logger

logger.info("User action", user_id=123, action="login", ip="192.168.1.1")
```

### Custom Configuration

```python
from lzl.logging import configure_logging

# Configure logging with custom settings
configure_logging(
    level="DEBUG",
    format="<green>{time}</green> | <level>{level}</level> | {message}",
    rotation="100 MB"
)
```

### Context Management

```python
from lzl.logging import logger

with logger.contextualize(request_id="abc-123"):
    logger.info("Processing request")  # Includes request_id in log
```

## Features

- **Structured Logging**: Easy-to-parse structured log output
- **Rotation Support**: Automatic log file rotation
- **Context Injection**: Add contextual information to logs
- **Performance**: Minimal overhead with efficient formatting
- **Integration**: Works well with async code and multiple threads

## Configuration

The logging module can be configured through environment variables or programmatically:

- `LOG_LEVEL`: Set the minimum log level (DEBUG, INFO, WARNING, ERROR)
- `LOG_FORMAT`: Custom log format string
- `LOG_FILE`: Path to log file (if file logging is desired)
