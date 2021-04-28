# This is a Discord bot created with the help of these guides:
# https://ritza.co/showcase/repl.it/building-a-discord-bot-with-python-and-repl-it.html
# https://www.freecodecamp.org/news/create-a-discord-bot-with-python/
# https://discordpy.readthedocs.io/en/latest/ext/commands/commands.html#invocation-context

import os
from commands import *
from keep_alive import keep_alive


keep_alive()
token = os.environ.get('DISCORD_BOT_SECRET')
bot.run(token)
