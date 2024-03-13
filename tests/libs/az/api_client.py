"""
This demonstrates how to use the API Client that is built into the authzero framework
"""

import asyncio
from lazyops.libs.authzero import AuthZeroAPIClient, az_settings
from lazyops.utils import Timer
from lazyops.utils.logs import logger

az_settings.configure(
    domain = 'domain.us.auth0.com', # This should mirror the domain for the server
    client_id = '....', # this should be a valid `machine-to-machine` client id
    client_secret = '....', # this should be a valid `machine-to-machine` client secret
)

client = AuthZeroAPIClient(
    api_client_id = 'test',
    api_client_env = 'test',
    audience = 'https://....ai',
    endpoint = 'http://localhost:8085',
    api_key = 'abc123', # You can test this with the API Keys that are allowed
    # api_key = 'xai-...', # Or you can use a valid API key that is returned after logging in
)


async def entrypoint():
    
    r = await client.aget('/whoami')
    logger.info(r.json())
    logger.info(client.asession.cookies)
    t = Timer()
    n = 0
    errors = 0

    while True:
        r = await client.aget('/test')
        if r.status_code != 200: 
            errors += 1
            logger.error(f'[{n} - {r.status_code} - {t.elapsed_s}]: {r.text}')
            if errors > 10: break
        if n % 20 == 0:
            logger.info(r.json(), prefix = f'{n} - {t.elapsed_s}')
            r = await client.aget('/whoami')
            logger.info(r.json())
        n += 1
        await asyncio.sleep(2.0)


asyncio.run(entrypoint())