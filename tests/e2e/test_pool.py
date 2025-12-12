import pytest
import asyncio
from lzl.pool import ThreadPool
# ProcessPool might be available via lzl.pool or lzl.pool.process
# check lzl/pool/__init__.py manually if fails, but ThreadPool is main.

def cpu_bound_task(x):
    return x * x

def io_bound_task(x):
    import time
    time.sleep(0.1)
    return x + 1

def test_thread_pool():
    """
    Test ThreadPool execution.
    """
    async def _test():
        # Initialize pool
        pool = ThreadPool    
        result = await pool.create_background_task(io_bound_task, 1)
        assert result == 2

        # Map
        async def _test_thread_pool():
            pool = ThreadPool(max_workers=2)
            
            results = []
            async for res in pool.aiterate(io_bound_task, [1, 2, 3]):
                results.append(res)
            
            assert sorted(results) == [2, 3, 4]

        import anyio
        anyio.run(_test_thread_pool)
        anyio.run(_test)
