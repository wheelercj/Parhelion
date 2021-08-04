# external imports
import os
import sys
import asyncio
import asyncpg

# internal imports
from bot import Bot
from keep_alive import keep_alive
from startup import get_db_connection


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


if __name__ == '__main__':
    main()
