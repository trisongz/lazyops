import time
import asyncio
import random
from lazyops.utils.helpers import timed_cache

"""
Test of the new behavior for only caching if the result is True
"""

_values = [
    True,
    False,
    False,
    False,
    False,
]

@timed_cache(5, cache_if_result=True)
def test_timed_cache() -> bool:
    return random.choice(_values)

for _ in range(10):
    print(test_timed_cache())

@timed_cache(2, cache_if_result=True)
async def test_timed_cache_async() -> bool:
    return random.choice(_values)


async def run_test():
    for _ in range(10):
        print(await test_timed_cache_async())
        await asyncio.sleep(1)

asyncio.run(run_test())