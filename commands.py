# External imports
import os
import discord
import textwrap
import asyncio

# Internal imports
from discord.ext import commands


my_channel_id = int(os.environ['MY_CHANNEL_ID'])
bot = commands.Bot(command_prefix=(';', 'par ', 'Par '))
use_hidden = True


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def hhelp(context):
	'''Shows help for all the hidden commands'''
	hidden_commands = []
	for cmd in bot.commands:
		if cmd.hidden:
			hidden_commands.append(cmd)

	# Alphabetize.
	hidden_commands = sorted(hidden_commands, key=lambda x: x.name)

	# Get column width.
	hidden_names = [x.name for x in hidden_commands]
	width = len(max(hidden_names, key=len))

	message = 'Hidden Commands:'
	for cmd in hidden_commands:
		message += f'\n  {cmd.name:<{width}} {cmd.short_doc}'
		if len(cmd.checks):
			message += ' (owner only)'
	message += '\n\n Type ;help command for more info on a command.'

	await context.send(f'```{message}```')


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def echo(context, *, message: str):
	'''Repeats a message'''
	await context.send(message)


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def ping(context):
	'''Pings the server'''
	await context.send(f'Pong! It took {round(bot.latency, 2)} ms.')


@bot.command(aliases=['info'])
@commands.cooldown(3, 15)
async def about(context):
	'''Shows general info about this bot'''
	# If this is the original instance of this bot:
	if '☼♫' in [x.name for x in bot.guilds]:
		embed = discord.Embed(description='Enter `;help` for a list of commands.\nThis bot was created by Chris Wheeler, except for the parts otherwise specified. See the source on Repl.it by clicking [here](https://replit.com/@wheelercj/simple-Discord-bot).')

	# Else if this is a forked copy of this bot:
	else:
		embed = discord.Embed(description='Enter `;help` for a list of commands.\nThis is a fork of a bot created by Chris Wheeler. You can see the original source on Repl.it by clicking [here](https://replit.com/@wheelercj/simple-Discord-bot).')

	await context.send(embed=embed)


@bot.command()
@commands.cooldown(3, 15)
async def invite(context):
	'''Shows the link to invite this bot to another server'''
	embed = discord.Embed(description='You can invite me to another server that you have "manage server" permissions in with this link: https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3300352')
	await context.send(embed=embed)


@bot.command()
@commands.cooldown(3, 15)
async def calc(context, *, string: str):
	'''Evaluates a math expression
	
	Uses a limited version of Python's eval function.'''
	try:
		# The eval function can do just about anything by default, so a
		# lot of its features have to be removed for security. For more
		# info, see https://realpython.com/python-eval-function/#minimizing-the-security-issues-of-eval 
		allowed_names = {}
		code = compile(string, '<string>', 'eval')
		for name in code.co_names:
			if name not in allowed_names:
				raise NameError(f'Use of "{name}" is not allowed.')

		await context.send(eval(code, {"__builtins__": {}}, allowed_names))
	except NameError as e:
		await context.send(e)
	except Exception as e:
		await context.send(f'Python error: {e}')


@bot.command(name='eval', hidden=use_hidden)
@commands.is_owner()
@commands.cooldown(3, 15)
async def _eval(context, *, string: str):
	'''Evaluates a Python expression
	
	This command is very powerful. Be careful!'''
	try:
		await context.send(eval(string))
	except Exception as e:
		await context.send(f'Python error: {e}')


@bot.command(name='exec', hidden=use_hidden)
@commands.is_owner()
@commands.cooldown(3, 15)
async def _exec(context, *, string: str):
	'''Executes a Python statement
	
	This command is very powerful. Be careful!'''
	# The exec function can do just about anything by default.
	# Be careful with this command!
	env = {
		'context': context,
		'asyncio': asyncio,
	}

	try:
		code = f'async def func():\n{textwrap.indent(string, "    ")}\nasyncio.get_running_loop().create_task(func())'
		exec(code, env)
	except Exception as e:
		await context.send(f'Python error: {e}')


async def dev_mail(bot, message: str, use_embed: bool = True, embed_title: str = 'dev mail'):
	channel = await bot.fetch_channel(my_channel_id)
	if use_embed:
		embed = discord.Embed(title=embed_title, description=message)
		await channel.send(embed=embed)
	else:
		await channel.send(message)


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def reverse(context, *, message: str):
	'''Reverses a message'''
	await context.send(message[::-1])


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def rot13(context, *, message: str):
	'''Rotates each letter 13 letters through the alphabet'''
	message = message.lower()
	new_string = ''
	alphabet = 'abcdefghijklmnopqrstuvwxyz'
	for char in message:
		index = alphabet.find(char)
		if index != -1:
			new_index = (index + 13) % 26
			new_string += alphabet[new_index]
		else:
			new_string += char

	await context.send(new_string)


@bot.command(aliases=['servers'])
@commands.cooldown(3, 15)
async def stats(context):
	'''Shows how many servers this bot is in'''
	await context.send(f'I am in {len(bot.guilds)} servers.')


@bot.command(hidden=use_hidden)
@commands.is_owner()
@commands.cooldown(3, 15)
async def leave(context):
	'''Makes the bot leave the server'''
	await context.send(f'Now leaving the server. Goodbye!')
	await context.guild.leave()
