# External imports
import os
import sys
import discord
import logging
import inspect
import traceback

# Internal imports
from reminders import *
from music import *
from rand import *
from docs import *
from keep_alive import keep_alive


# Discord logging guide: https://discordpy.readthedocs.io/en/latest/logging.html#logging-setup
# Python's intro to logging: https://docs.python.org/3/howto/logging.html#logging-basic-tutorial
logger = logging.getLogger('discord')
COMMANDS = 25  # Logs each command use (as well as warnings, errors, and criticals).
logger.setLevel(COMMANDS)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


my_user_id = int(os.environ['MY_USER_ID'])


@bot.event
async def on_connect():
	try:
		print('Loading . . . ')
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
	# mark that's in the unrendered version of mentions.
	mention = bot.user.mention[:2] + '!' + bot.user.mention[2:]
	if mention in message.content:
		nickname = message.author.nick
		if nickname is not None:
			await message.channel.send(f'Hello {nickname.split()[0]}!')
		else:
			await message.channel.send(f'Hello {message.author.name.split()[0]}!')


@bot.event
async def on_command(ctx):
	log_message = f'author: {ctx.author.display_name}; guild: {ctx.guild}; command: {ctx.message.content}'
	logger.log(COMMANDS, log_message)

	bot.previous_commands_ctx.append(ctx)
	if len(bot.previous_commands_ctx) > 15:
		previous_commands_ctx = previous_commands_ctx[8:]


@bot.event
async def on_command_error(ctx, error):
	if hasattr(ctx.command, 'on_error'):
            return

	if isinstance(error, commands.CommandOnCooldown):
		await ctx.send(error)
	elif isinstance(error, commands.UserInputError):
		await ctx.send(error)
	else:
		print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
		traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


@bot.event
async def on_guild_join(guild):
	message = f'I\'ve joined a new server called "{guild}"!' \
			f'\nI am now in {len(bot.guilds)} servers.'
	await dev_mail(bot, message, use_embed=False)


@bot.command(name='inspect', aliases=['source', 'src'])
@commands.cooldown(3, 15)
async def _inspect(ctx, *, command: str):
	'''Shows the source code of a command'''
	try:
		cmds = {cmd.name: cmd for cmd in bot.commands}
		if command not in cmds.keys():
			raise NameError(f'Command {command} not found.')
		source = str(inspect.getsource(cmds[command].callback))
		await ctx.send(f'```py\n{source}```')
	except NameError as e:
		await ctx.send(e)
	except KeyError as e:
		await ctx.send(e)


keep_alive()
token = os.environ.get('DISCORD_BOT_SECRET_TOKEN')
bot.run(token)
