
import asyncio
import random
from lazyops.libs.posthog.client import PostHogClient

async def test_dryrun():
    client = PostHogClient(dryrun = True, api_key = 'xxx', project_id = 'xxx', debug_enabled=True, batch_size = 20, num_workers=2)
    # client.start_task_queue()

    for _ in range(10):
        async with client:
            for x in range(5):
                client.add_event('test', distinct_id = f'yyy-{x}', properties = {'test': 'test', 'y': x})
                await asyncio.sleep(random.randint(1, 2) * 0.1)
        


    for x in range(100):
        for i in range(350):
            client.add_event('test', distinct_id = f'xxx-{i}-{x}', properties = {'test': 'test', 'test2': i, 'test3': x})
            await asyncio.sleep(random.randint(1, 10) * 0.1)
    

async def entrypoint():
    await test_dryrun()

if __name__ == '__main__':
    asyncio.run(entrypoint())
    