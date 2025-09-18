# `lzl.pool`

Utility functions and proxy objects that bridge synchronous code with asyncio.
The module centres around the proxied `ThreadPool` singleton, which exposes
helpers for running synchronous functions inside an event loop, scheduling
background work, and streaming subprocess output.

## Highlights
- **`ThreadPool.asyncish`** – Await synchronous callables transparently by
  delegating to a shared thread pool.
- **`ThreadPool.background`** – Schedule work as an `asyncio.Task` when inside
  an event loop or fallback to `ThreadPoolExecutor` otherwise.
- **Concurrency helpers** – `set_concurrency_limit`, `get_concurrency_limit`,
  and `amap_iterable` provide coarse-grained control over asynchronous fan-out.
- **Command execution** – Convenience wrappers (`acmd`, `acmd_exec`,
  `acmd_stream`) streamline subprocess usage when async integration is needed.

## Usage
```python
from lzl.pool import ThreadPool, set_concurrency_limit

set_concurrency_limit(8)

async def example():
    result = await ThreadPool.asyncish(sum, [1, 2, 3])
    return result
```

## Testing Notes
- Prefer lightweight callables (e.g. pure arithmetic) when exercising
  `ThreadPool` in tests to keep execution deterministic.
- Use `pytest.mark.asyncio` (or equivalent) when asserting behaviour that
  depends on an active event loop.
