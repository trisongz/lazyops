import asyncio
import random
from lazyops.utils import logger, create_unique_id
from lazyops.libs.posthog import capture, PHCtxT, get_posthog_client, PostHogClient
from typing import Dict, Any, Optional


"""
Here we will test the deferred capture by initializing the client after defining the functions

The first set of events should not be captured since the client has not been initialized. 
The second set of events should be captured.
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

    

    # These events should not be captured
    logger.warning('Starting with events should not be captured. No logs should be printed')
    for y in range(10):
        for x in range(5):
            await lazy_event_1(x = x, y = y)
            await lazy_event_2(x = x, y = y)
            await asyncio.sleep(random.randint(1, 2) * 0.1)
    logger.warning('Completed. No events should have been logged')
    
    # These events should be captured
    # Preferrably, use get_posthog_client to avoid creating a new client
    # But there's a check in place to prevent multiple clients from being created

    # client = get_posthog_client(api_key = 'xxx', project_id = 'xxx', debug_enabled=True, batch_size = 20)
    client = PostHogClient(api_key = 'xxx', project_id = 'xxx', debug_enabled=True, batch_size = 20)
    logger.warning('Starting with events should be captured. Logs should be printed')
    for y in range(10):
        for x in range(5):
            await lazy_event_1(x = x, y = y)
            await lazy_event_2(x = x, y = y)
            await asyncio.sleep(random.randint(1, 2) * 0.1)
    logger.warning('Completed. All events should have been logged')


async def entrypoint():
    await test_captures()

if __name__ == '__main__':
    asyncio.run(entrypoint())
    