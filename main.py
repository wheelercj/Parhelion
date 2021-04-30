# This is a Discord bot created with the help of these guides:
# https://ritza.co/showcase/repl.it/building-a-discord-bot-with-python-and-repl-it.html
# https://www.freecodecamp.org/news/create-a-discord-bot-with-python/
# https://discordpy.readthedocs.io/en/latest/ext/commands/commands.html#invocation-context

import os
import discord
from reminders import *
from keep_alive import keep_alive

# TODO: send a random quote each day.

@bot.event
async def on_connect():
	try:
		print('Connecting . . . ')
		reminders = load_reminders()
		for r in reminders:  # TODO: I'm assuming reminders is a list.
			await cotinue_reminders(r)
	except Exception as e:
		print(f'on_connect error: {e}')


@bot.event
async def on_ready():
	print('------------------------------------')
	print(f'Discord v{discord.__version__}')
	print(f'{bot.user.name}#{bot.user.discriminator} ready!')
	print('------------------------------------')


@bot.event
async def on_message(message):
	if message.author != bot.user:
		content = message.content
		content = content[:2] + content[3:]
		if bot.user.mention in content.split():
			await message.channel.send(f'Hello {message.author.name.split()[0]}!')

		await bot.process_commands(message)


keep_alive()
token = os.environ.get('DISCORD_BOT_SECRET')
bot.run(token)
