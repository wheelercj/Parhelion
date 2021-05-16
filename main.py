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
		await answer_mention(message, bot)
		await bot.process_commands(message)


async def answer_mention(message: str, bot):
	'''Respond when mentioned'''
	# For some reason, bot.user.mention is always missing the exclamation
	# point that's in the unrendered version of mentions.
	mention = bot.user.mention[:2] + '!' + bot.user.mention[2:]
	if mention in message.content:
		nickname = message.author.nick
		if nickname is not None:
			await message.channel.send(f'Hello {nickname.split()[0]}!')
		else:
			await message.channel.send(f'Hello {message.author.name.split()[0]}!')


keep_alive()
token = os.environ.get('DISCORD_BOT_SECRET_TOKEN')
bot.run(token)
