import asyncio
import os

import asyncpg  # https://pypi.org/project/asyncpg/
from dotenv import load_dotenv  # https://pypi.org/project/python-dotenv/

from bot import Bot


async def main():
    dotenv_path: str = "../.env"
    abs_dotenv_path: str = os.path.join(os.path.dirname(__file__), dotenv_path)
    load_dotenv(abs_dotenv_path)
    try:
        db: asyncpg.Pool = await get_db_connection()
    except Exception:
        print("\x1b[31mError: unable to connect to the database because:\x1b[0m")
        raise
    bot = Bot()
    bot.db = db
    token = os.environ["DISCORD_BOT_TOKEN"]
    async with bot:
        await bot.start(token, reconnect=True)


async def get_db_connection() -> asyncpg.Pool:
    """Connects to the PostgreSQL database"""
    host = os.environ.get("POSTGRES_HOST", "localhost")
    database = os.environ.get("POSTGRES_DB", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ["POSTGRES_PASSWORD"]
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
