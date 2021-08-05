# external imports
import os
import sys
import asyncio
import asyncpg

# internal imports
from bot import Bot
from keep_alive import keep_alive


def main():
    keep_alive()
    loop = asyncio.get_event_loop()
    try:
        db: asyncpg.Pool = loop.run_until_complete(get_db_connection())
    except Exception as error:
        print(f'Error: unable to connect to the database because {error}.', file=sys.stderr)
        return

    bot = Bot()
    bot.db = db
    token = os.environ.get('DISCORD_BOT_SECRET_TOKEN')
    bot.run(token, bot=True, reconnect=True)


async def get_db_connection() -> asyncpg.Pool:
    """Connects to the PostgreSQL database"""
    user = os.environ['PostgreSQL user']
    password = os.environ['PostgreSQL password']
    database = os.environ['PostgreSQL database']
    host = os.environ['PostgreSQL host']

    credentials = {'user': user, 'password': password, 'database': database, 'host': host}
    return await asyncpg.create_pool(**credentials, command_timeout=60)


if __name__ == '__main__':
    main()
