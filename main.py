import os
import discord
from reminders import *
from music import *
from rand import *
from keep_alive import keep_alive


@bot.event
async def on_connect():
	try:
		print('Connecting . . . ')
		reminders = load_reminders()
		if reminders is not None:
			for r in reminders:
				await cotinue_reminder(r, bot)
	except Exception as e:
		print(f'on_connect error: {e}')
		raise e


@bot.event
async def on_ready():
	print('------------------------------------')
	print(f'Discord v{discord.__version__}')
	print(f'{bot.user.name}#{bot.user.discriminator} ready!')
	print('------------------------------------')


@bot.event
async def on_message(message: str):
	if message.author != bot.user:
		content = message.content
		content = content[:2] + content[3:]
		if bot.user.mention in content.split():
			await message.channel.send(f'Hello {message.author.name.split()[0]}!')

		await bot.process_commands(message)


keep_alive()
token = os.environ.get('DISCORD_BOT_SECRET')
bot.run(token)
