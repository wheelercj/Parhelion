# External imports
import os
import platform
import discord
import textwrap
import asyncio
from math import *

# Internal imports
from discord.ext import commands


my_user_id = int(os.environ['MY_USER_ID'])
bot = commands.Bot(command_prefix=(';', 'par ', 'Par '))
use_hidden = True


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def hhelp(ctx):
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

	await ctx.send(f'```{message}```')


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def echo(ctx, *, message: str):
	'''Repeats a message'''
	await ctx.send(message)


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def ping(ctx):
	'''Pings the server'''
	await ctx.send(f'Pong! It took {round(bot.latency, 2)} ms.')


@bot.command(aliases=['info', 'stats', 'invite'])
@commands.cooldown(3, 15)
async def about(ctx):
	'''Shows general info about this bot'''
	embed = discord.Embed(
		title='About me',
		description= f'''
			Created by Chris Wheeler
			with Python {platform.python_version()} and [discord.py](https://discordpy.readthedocs.io/en/latest/)

			Currently in {len(bot.guilds)} servers.
			Invite link [here](https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3300352)
			Source code [here](https://replit.com/@wheelercj/simple-Discord-bot)
		'''
	)
	
	await ctx.send(embed=embed)


@bot.command()
@commands.cooldown(3, 15)
async def calc(ctx, *, string: str):
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

		await ctx.send(eval(code, {"__builtins__": {}}, allowed_names))
	except NameError as e:
		await ctx.send(e)
	except Exception as e:
		await ctx.send(f'Python error: {e}')


@bot.command(name='eval', hidden=use_hidden)
@commands.is_owner()
@commands.cooldown(3, 15)
async def _eval(ctx, *, string: str):
	'''Evaluates a Python expression
	
	This command is very powerful. Be careful!'''
	try:
		await ctx.send(eval(string))
	except Exception as e:
		await ctx.send(f'Python error: {e}')


@bot.command(name='exec', hidden=use_hidden)
@commands.is_owner()
@commands.cooldown(3, 15)
async def _exec(ctx, *, string: str):
	'''Executes a Python statement
	
	This command is very powerful. Be careful!'''
	string = remove_backticks(string)
	env = {
		'ctx': ctx,
		'asyncio': asyncio,
	}

	try:
		code = f'async def func():\n{textwrap.indent(string, "    ")}\nasyncio.get_running_loop().create_task(func())'
		exec(code, env)
	except Exception as e:
		await ctx.send(f'Python error: {e}')


def remove_backticks(string: str):
	'''Removes backticks around a code block, if they are there'''
	if string.startswith('```'):
		string = string[3:]
		if string.startswith('py\n'):
			string = string[3:]
		if string.endswith('```'):
			string = string[:-3]

	return string


async def dev_mail(bot, message: str, use_embed: bool = True, embed_title: str = 'dev mail'):
	user = await bot.fetch_user(my_user_id)
	if use_embed:
		embed = discord.Embed(title=embed_title, description=message)
		await user.send(embed=embed)
	else:
		await user.send(message)


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def reverse(ctx, *, message: str):
	'''Reverses a message'''
	await ctx.send(message[::-1])


@bot.command(hidden=use_hidden)
@commands.cooldown(3, 15)
async def rot13(ctx, *, message: str):
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

	await ctx.send(new_string)


@bot.command(hidden=use_hidden)
@commands.is_owner()
@commands.cooldown(3, 15)
async def leave(ctx):
	'''Makes the bot leave the server'''
	await ctx.send(f'Now leaving the server. Goodbye!')
	await ctx.guild.leave()
