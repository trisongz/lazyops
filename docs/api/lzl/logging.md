# lzl.logging - Structured Logging

The `lzl.logging` module provides a zero-config, high-performance structured logging system built on top of `loguru`.

## Core Logger

::: lzl.logging.main

## Configuration

::: lzl.logging.base

## Formatters

::: lzl.logging.formatters

## Usage

```python
from lzl.logging import logger

# Basic usage
logger.info("Application started")

# Structured context
logger.info("Processing request", request_id="req-123", user_id=456)

# Exception handling
try:
    1 / 0
except Exception:
    logger.exception("Something went wrong")
```