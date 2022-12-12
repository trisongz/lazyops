
import asyncio
import aiohttp
import random
import math
from lazyops.apis import async_req
from lazyops import timer

max_ids = 5

def get_ran_id():
    return random.randint(0, max_ids)


async def test_hits(num_hits=50000, total_logs=10):
    start = timer()
    log_every = math.ceil(num_hits / total_logs)
    async with aiohttp.ClientSession() as sess:
        for n in range(num_hits):
            user_id = get_ran_id()
            res = await async_req(sess=sess, method='GET', url='http://127.0.0.1:5000/user', params={'user_id': user_id})
            assert res['uid'] == user_id
            if n+1 % log_every == 0:
                print(f'GET Request: {n+1} ', res)
                print('Current Time: ', start.ablstime)
        print(f'Completed Run of {num_hits} Async GET Requests: ', start.ablstime)

if __name__ == '__main__':
    asyncio.run(test_hits())