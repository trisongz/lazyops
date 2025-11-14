# lzl.pool - Thread Pool Utilities

The `lzl.pool` module provides thread pool management and execution utilities for concurrent operations.

## Module Reference

::: lzl.pool
    options:
      show_root_heading: true
      show_source: true

## Overview

The pool module offers efficient thread pool management for CPU-bound and I/O-bound tasks, with support for both synchronous and asynchronous execution patterns.

## Usage Examples

### Basic Thread Pool

```python
from lzl.pool import ThreadPool

pool = ThreadPool(max_workers=4)

def process_item(item):
    return item * 2

# Submit tasks to the pool
futures = [pool.submit(process_item, i) for i in range(10)]

# Get results
results = [f.result() for f in futures]
```

### Async Context Manager

```python
from lzl.pool import ThreadPool

async def main():
    async with ThreadPool(max_workers=4) as pool:
        result = await pool.run_in_thread(blocking_function, arg1, arg2)
```

### Batch Processing

```python
from lzl.pool import ThreadPool

def process_batch(items):
    pool = ThreadPool(max_workers=8)
    results = pool.map(process_item, items)
    return list(results)

items = range(100)
processed = process_batch(items)
```

### Resource Management

```python
from lzl.pool import ThreadPool

# Pool automatically cleans up threads
with ThreadPool(max_workers=4) as pool:
    pool.submit(task1)
    pool.submit(task2)
# Threads are shut down here
```

## Features

- **Automatic Scaling**: Thread count adapts to workload
- **Resource Management**: Proper cleanup with context managers
- **Async Integration**: Works seamlessly with asyncio
- **Error Handling**: Proper exception propagation
- **Monitoring**: Track pool status and worker utilization

## Configuration

Thread pool behavior can be customized:

- `max_workers`: Maximum number of worker threads
- `thread_name_prefix`: Prefix for thread names (useful for debugging)
- `initializer`: Function to run when each thread starts
- `initargs`: Arguments for the initializer function
