# external imports
import os

# internal imports
from bot import Bot
from keep_alive import keep_alive


if __name__ == '__main__':
    keep_alive()
    token = os.environ.get('DISCORD_BOT_SECRET_TOKEN')
    Bot().run(token, bot=True, reconnect=True)
