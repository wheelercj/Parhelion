# External imports
import os
import discord
import inspect

# Internal imports
from discord.ext import commands


my_channel_id = int(os.environ['MY_CHANNEL_ID'])
bot = commands.Bot(command_prefix=(';', 'par ', 'Par '))


@bot.command(hidden=True)
@commands.cooldown(2, 10)
async def echo(context, *, message: str):
	'''Repeats a message'''
	await context.send(message)


@bot.command(hidden=True)
@commands.cooldown(2, 10)
async def ping(context):
	'''Pings the server'''
	await context.send(f'Pong! It took {round(bot.latency, 2)} ms.')


@bot.command(aliases=['about', 'source', 'src'])
@commands.cooldown(1, 60)
async def info(context):
	'''Shows general info about this bot'''
	# If this is the original instance of this bot:
	if '☼♫' in [x.name for x in bot.guilds]:
		embed = discord.Embed(description='Enter `;help` for a list of commands.\nThis bot was created by Chris Wheeler, except for the parts otherwise specified. See the source on Repl.it by clicking [here](https://replit.com/@wheelercj/simple-Discord-bot).')

	# Else if this is a forked copy of this bot:
	else:
		embed = discord.Embed(description='Enter `;help` for a list of commands.\nThis is a fork of a bot created by Chris Wheeler. You can see the original source on Repl.it by clicking [here](https://replit.com/@wheelercj/simple-Discord-bot).')

	await context.send(embed=embed)


@bot.command()
@commands.cooldown(1, 60)
async def invite(context):
	'''Shows the link to invite this bot to another server'''
	embed = discord.Embed(description='You can invite me to another server that you have "manage server" permissions in with this link: https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3300352')
	await context.send(embed=embed)


@bot.command()
@commands.cooldown(2, 10)
async def calc(context, *, string: str):
	'''Evaluates math expressions'''
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


@bot.command(hidden=True, aliases=['python', 'eval'])
@commands.is_owner()
@commands.cooldown(4, 10)
async def py(context, *, string: str):
	'''Evaluates Python expressions'''
	try:
		# The eval function can do just about anything by default. Be
		# careful with this command! For more info, see https://realpython.com/python-eval-function/#minimizing-the-security-issues-of-eval
		await context.send(eval(string))
	except Exception as e:
		await context.send(f'Python error: {e}')


async def dev_mail(bot, message: str, use_embed: bool = True, embed_title: str = 'dev mail'):
	channel = await bot.fetch_channel(my_channel_id)
	if use_embed:
		embed = discord.Embed(title=embed_title, description=message)
		await channel.send(embed=embed)
	else:
		await channel.send(message)


@bot.command(hidden=True)
@commands.cooldown(2, 10)
async def reverse(context, *, message: str):
	'''Reverses a message'''
	await context.send(message[::-1])


@bot.command(hidden=True)
@commands.cooldown(2, 10)
async def rot13(context, *, message: str):
	'''Rotates each letter of a message 13 letters through the alphabet'''
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


@bot.command()
@commands.cooldown(1, 60)
async def servers(context):
	'''Shows how many servers this bot is in'''
	await context.send(f'I am in {len(bot.guilds)} servers.')


@bot.command(hidden=True)
@commands.is_owner()
async def leave(context):
	'''Makes the bot leave the server'''
	await context.send(f'Now leaving the server. Goodbye!')
	await context.guild.leave()
