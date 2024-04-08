import os

os.environ['POSTHOG_API_KEY'] = 'xxx'
os.environ['POSTHOG_DEBUG_ENABLED'] = 'True'
os.environ['POSTHOG_BATCH_SIZE'] = '20'


import asyncio
import random
from lazyops.utils import logger, create_unique_id
from lazyops.libs.posthog import capture, PHCtxT
from typing import Dict, Any, Optional


"""
Here we will test the autocapture without explicitly initializing the client
"""

@capture()
async def lazy_event_1(*args, x: Optional[int] = None, y: Optional[int] = None, ph_ctx: Optional[PHCtxT] = None, **kwargs):
    if ph_ctx:
        ph_ctx['properties']['event_name'] = 'lazy_event_1'
        ph_ctx['properties']['random_id'] = create_unique_id()
        if x: ph_ctx['properties']['x'] = x
        if y: ph_ctx['properties']['y'] = y
        ph_ctx['distinct_id'] = f'xxx-{create_unique_id()}'
    return 'lazy_event_1'

@capture()
async def lazy_event_2(*args, x: Optional[int] = None, y: Optional[int] = None, ph_ctx: Optional[PHCtxT] = None, **kwargs):
    if ph_ctx:
        ph_ctx['properties']['event_name'] = 'lazy_event_2'
        ph_ctx['properties']['random_id'] = create_unique_id()
        if x: ph_ctx['properties']['x'] = x
        if y: ph_ctx['properties']['y'] = y
        ph_ctx['distinct_id'] = f'xxx-{create_unique_id()}'
    return 'lazy_event_2'


async def test_captures():
    for y in range(10):
        for x in range(5):
            await lazy_event_1(x = x, y = y)
            await lazy_event_2(x = x, y = y)
            await asyncio.sleep(random.randint(1, 2) * 0.1)


async def entrypoint():
    await test_captures()

if __name__ == '__main__':
    asyncio.run(entrypoint())
    