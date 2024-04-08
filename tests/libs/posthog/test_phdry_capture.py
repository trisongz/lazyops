
import asyncio
import random
from lazyops.utils import logger, create_unique_id
from lazyops.libs.posthog.client import PostHogClient
from lazyops.libs.posthog.utils import capture
from typing import Dict, Any, Optional

@capture(event = 'test_event_2')
async def capture_event_2(*args, x: Optional[int] = None, y: Optional[int] = None, ph_ctx: Optional[Dict[str, Any]] = None, **kwargs):
    
    # logger.info('Capturing Event 2')
    ph_ctx['properties']['test'] = 'test_2'
    ph_ctx['properties']['random_id'] = create_unique_id()
    if x: ph_ctx['properties']['x'] = x
    if y: ph_ctx['properties']['y'] = y
    ph_ctx['distinct_id'] = f'xxx-{create_unique_id()}'
    
    return 'test_2'


client = PostHogClient(dryrun = True, api_key = 'xxx', project_id = 'xxx', debug_enabled=True, batch_size = 20)

@client.capture(event = 'test_event')
async def capture_event(*args, x: Optional[int] = None, y: Optional[int] = None, ph_ctx: Dict[str, Any], **kwargs):
    
    # logger.info('Capturing Event')
    ph_ctx['properties']['test'] = 'test'
    ph_ctx['properties']['random_id'] = create_unique_id()
    if x: ph_ctx['properties']['x'] = x
    if y: ph_ctx['properties']['y'] = y
    ph_ctx['distinct_id'] = f'xxx-{create_unique_id()}'
    
    return 'test'


@capture(event = 'test_event_3')
async def capture_event_3(*args, x: Optional[int] = None, y: Optional[int] = None, ph_ctx: Dict[str, Any], **kwargs):
    
    # logger.info('Capturing Event 3')
    ph_ctx['properties']['test'] = 'test_3'
    ph_ctx['properties']['random_id'] = create_unique_id()
    if x: ph_ctx['properties']['x'] = x
    if y: ph_ctx['properties']['y'] = y
    ph_ctx['distinct_id'] = f'xxx-{create_unique_id()}'
    
    return 'test_3'


async def test_captures():
    for _ in range(10):
        async with client:
            for x in range(5):
                await capture_event(x = x)
                await capture_event_2(x = x)
                await capture_event_3(x = x)
                await asyncio.sleep(random.randint(1, 2) * 0.1)
    
    for x in range(100):
        for y in range(350):
            await capture_event(x = x, y = y)
            await capture_event_2(x = x, y = y)
            await capture_event_3(x = x, y = y)
            await asyncio.sleep(random.randint(1, 10) * 0.1)


async def entrypoint():
    await test_captures()

if __name__ == '__main__':
    asyncio.run(entrypoint())
    