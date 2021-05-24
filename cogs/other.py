import platform
import inspect
import discord
from discord.ext import commands


class Other(commands.Cog):
	def __init__(self, bot):
		self.bot = bot


	@commands.command(hidden=True)
	@commands.cooldown(3, 15)
	async def hhelp(self, ctx):
		'''Shows help for all the hidden commands'''
		hidden_commands = []
		for cmd in self.bot.commands:
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
				message += ' (bot owner only)'
		message += '\n\n Type ;help command for more info on a command.'

		await ctx.send(f'```{message}```')


	@commands.command(hidden=True)
	@commands.cooldown(3, 15)
	async def echo(self, ctx, *, message: str):
		'''Repeats a message'''
		await ctx.send(message)


	@commands.command(hidden=True)
	@commands.cooldown(3, 15)
	async def ping(self, ctx):
		'''Pings the server'''
		await ctx.send(f'Pong! It took {round(self.bot.latency, 2)} ms.')


	@commands.command(aliases=['info', 'stats', 'invite'])
	@commands.cooldown(3, 15)
	async def about(self, ctx):
		'''Shows general info about this bot'''
		embed = discord.Embed(
			title='About me',
			description= f'''
				Created by Chris Wheeler
				with Python {platform.python_version()} and [discord.py](https://discordpy.readthedocs.io/en/latest/)

				Currently in {len(self.bot.guilds)} servers.
				Invite link [here](https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3300352)
				Source code [here](https://replit.com/@wheelercj/simple-Discord-bot)
			'''
		)
		
		await ctx.send(embed=embed)


	@commands.command(name='inspect', aliases=['source', 'src'])
	@commands.cooldown(3, 15)
	async def _inspect(self, ctx, *, command: str):
		'''Shows the source code of a command'''
		try:
			cmds = {cmd.name: cmd for cmd in self.bot.commands}
			if command not in cmds.keys():
				raise NameError(f'Command {command} not found.')
			source = str(inspect.getsource(cmds[command].callback))
			await ctx.send(f'```py\n{source}```')
		except NameError as e:
			await ctx.send(e)
		except KeyError as e:
			await ctx.send(e)


	@commands.command()
	@commands.cooldown(3, 15)
	async def calc(self, ctx, *, string: str):
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


	@commands.command(hidden=True)
	@commands.cooldown(3, 15)
	async def reverse(self, ctx, *, message: str):
		'''Reverses a message'''
		await ctx.send(message[::-1])


	@commands.command(hidden=True)
	@commands.cooldown(3, 15)
	async def rot13(self, ctx, *, message: str):
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


def setup(bot):
	bot.add_cog(Other(bot))
