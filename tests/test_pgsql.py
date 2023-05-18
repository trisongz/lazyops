import os

os.environ['POSTGRES_URI'] = 'test:test@localhost:5432/test'
os.environ['POSTGRES_USER'] = 'postgres'
# os.environ['POSTGRES_PASSWORD'] = 'test'

import asyncio
from lazyops.libs.psqldb import PostgresDB

async def test():
    PostgresDB.prepare_db(
        role_user = 'test',
        role_password = 'test',
        db_name = 'test',
    )
    async with PostgresDB.async_session() as sess:
        await sess.execute("SELECT 1")


asyncio.run(test())