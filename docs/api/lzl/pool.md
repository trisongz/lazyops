# lzl.pool - Thread & Async Utilities

The `lzl.pool` module provides a unified interface for concurrency, bridging the gap between synchronous threading and `asyncio` event loops.

## ThreadPool

A singleton-style proxy that manages a global `ThreadPoolExecutor` and `ProcessPoolExecutor`.

::: lzl.pool.base
    options:
        members:
            - ThreadPool

## Concurrency Helpers

Utilities for running functions in the background, mapping iterables concurrently, and more.

::: lzl.pool.base
    options:
        members:
            - amap_iterable
            - async_map
            - ensure_coro
            - is_coro_func

## Usage Guide

### Running Sync Code Asynchronously

Use `ThreadPool` to offload blocking operations to a worker thread while awaiting them in an async function.

```python
from lzl.pool import ThreadPool

def blocking_io():
    # Simulate heavy work
    import time
    time.sleep(1)
    return "done"

async def main():
    # Runs in a thread, non-blocking for the event loop
    result = await ThreadPool.arun(blocking_io)
    print(result)
```

### Background Tasks

Fire-and-forget background tasks that work regardless of whether you are in a sync or async context.

```python
from lzl.pool import ThreadPool

def background_job(user_id):
    print(f"Processing {user_id}...")

# Works from async functions
await ThreadPool.background(background_job, 123)

# Works from sync functions too
ThreadPool.background(background_job, 456)
```

### Parallel Execution

Concurrent mapping over iterables.

```python
from lzl.pool import ThreadPool

items = [1, 2, 3, 4, 5]

def process(x):
    return x * x

# Parallel execution using threads
results = ThreadPool.map(process, items, num_workers=4)
```