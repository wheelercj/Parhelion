import asyncio
import os

import asyncpg  # https://pypi.org/project/asyncpg/
from dotenv import load_dotenv  # https://pypi.org/project/python-dotenv/

from bot import Bot


async def main():
    load_dotenv()
    try:
        db: asyncpg.Pool = await get_db_connection()
    except Exception:
        print("\x1b[31mError: unable to connect to the database because:\x1b[0m")
        raise
    bot = Bot()
    bot.db = db
    token = os.environ["discord_bot_secret_token"]
    async with bot:
        await bot.start(token, reconnect=True)


async def get_db_connection() -> asyncpg.Pool:
    """Connects to the PostgreSQL database"""
    host = os.environ.get("postgres_host", "localhost")
    database = os.environ.get("postgres_database", "postgres")
    port = os.environ.get("postgres_port", "5432")
    user = os.environ.get("postgres_user", "postgres")
    password = os.environ["postgres_password"]
    return await asyncpg.create_pool(
        host=host,
        database=database,
        port=port,
        user=user,
        password=password,
        command_timeout=60,
    )


if __name__ == "__main__":
    asyncio.run(main())
