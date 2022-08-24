import asyncio
import os
import sys

import asyncpg  # https://pypi.org/project/asyncpg/
from dotenv import load_dotenv  # https://pypi.org/project/python-dotenv/

from bot import Bot


async def main():
    try:
        db: asyncpg.Pool = await get_db_connection()
    except Exception as error:
        print(
            f"Error: unable to connect to the database because {error}.",
            file=sys.stderr,
        )
        return
    bot = Bot()
    bot.db = db
    token = os.environ["DISCORD_BOT_SECRET_TOKEN"]
    async with bot:
        await bot.start(token, reconnect=True)


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


async def get_db_connection() -> asyncpg.Pool:
    """Connects to the PostgreSQL database"""
    load_dotenv()
    user = os.environ["PostgreSQL_user"]
    password = os.environ["PostgreSQL_password"]
    database = os.environ["PostgreSQL_database"]
    host = os.environ["PostgreSQL_host"]

    credentials = {
        "user": user,
        "password": password,
        "database": database,
        "host": host,
    }
    return await asyncpg.create_pool(**credentials, command_timeout=60)


if __name__ == "__main__":
    asyncio.run(main())
