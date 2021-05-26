from discord.ext import commands
import textwrap
import asyncio
from cogs.reminders import reminders_file
from discord.ext.commands.cooldowns import BucketType


class Owner(commands.Cog):
	def __init__(self, bot):
		self.bot = bot


	@commands.command(hidden=True)
	@commands.is_owner()
	@commands.cooldown(1, 15, BucketType.user)
	async def leave(self, ctx):
		'''Makes the bot leave the server'''
		await ctx.send(f'Now leaving the server. Goodbye!')
		await ctx.guild.leave()


	@commands.command(name='r', hidden=True)
	@commands.is_owner()
	@commands.cooldown(1, 15, BucketType.user)
	async def repeat_command(self, ctx):
		'''Repeats the last command you used'''
		previous = ctx.bot.previous_command_ctxs
		for c in previous[::-1]:
			if c.author.id == ctx.author.id:
				if c.command.name == 'r':
					raise ValueError
				await c.reinvoke()
				return
		
		await ctx.send('No previous command saved.')


	@commands.command(name='reload', hidden=True)
	@commands.is_owner()
	@commands.cooldown(1, 15, BucketType.user)
	async def reload_extension(self, ctx, *, extension: str):
		'''Reloads an extension, e.g: ;reload cogs.music'''
		try:
			self.bot.unload_extension(extension)
			self.bot.load_extension(extension)
		except Exception as e:
			await ctx.send(f'Error: {type(e).__name__}: {e}')
		else:
			await ctx.send('Extension successfully reloaded.')


	@commands.command(name='load', hidden=True)
	@commands.is_owner()
	@commands.cooldown(1, 15, BucketType.user)
	async def load_extension(self, ctx, *, extension: str):
		'''Loads an extension, e.g. ;load cogs.music'''
		try:
			self.bot.load_extension(extension)
		except Exception as e:
			await ctx.send(f'Error: {type(e).__name__}: {e}')
		else:
			await ctx.send('Extension successfully loaded.')


	@commands.command(name='unload', hidden=True)
	@commands.is_owner()
	@commands.cooldown(1, 15, BucketType.user)
	async def unload_extension(self, ctx, *, extension: str):
		'''Unloads an extension, e.g. ;unload cogs.music'''
		try:
			self.bot.unload_extension(extension)
		except Exception as e:
			await ctx.send(f'Error: {type(e).__name__}: {e}')
		else:
			await ctx.send('Extension successfully unloaded.')


	@commands.command(name='eval', hidden=True)
	@commands.is_owner()
	@commands.cooldown(1, 15, BucketType.user)
	async def _eval(self, ctx, *, expression: str):
		'''Evaluates a Python expression
		
		Returns result to Discord automatically.
		Has access to bot via self.
		'''
		try:
			await ctx.send(eval(expression))
		except Exception as e:
			await ctx.send(f'Python error: {e}')


	@commands.command(name='exec', hidden=True)
	@commands.is_owner()
	@commands.cooldown(1, 15, BucketType.user)
	async def _exec(self, ctx, *, statement: str):
		'''Executes a Python statement
		
		Requires the use of `await ctx.send` for output.
		Has direct access to bot.
		'''
		statement = self.remove_backticks(statement)
		env = {
			'ctx': ctx,
			'bot': self.bot,
			'asyncio': asyncio,
		}

		try:
			code = f'async def func():\n    try:\n{textwrap.indent(statement, "        ")}\n    except Exception as e:\n        await ctx.send("Python error: %s" % e)\nasyncio.get_running_loop().create_task(func())'
			exec(code, env)
		except Exception as e:
			await ctx.send(f'Python error: {e}')


	def remove_backticks(self, statement: str):
		'''Removes backticks around a code block, if they are there'''
		if statement.startswith('```'):
			statement = statement[3:]
			if statement.startswith('py\n'):
				statement = statement[3:]
			if statement.endswith('```'):
				statement = statement[:-3]

		return statement


	@commands.command(name='del-all-r', hidden=True)
	@commands.is_owner()
	@commands.cooldown(1, 15, BucketType.user)
	async def delete_all_reminders(self, ctx):
		'''Deletes everything in the reminders file
		
		For recovering from errors that make the file unparseable.
		'''
		with open(reminders_file, 'w') as _:
			pass
		await ctx.send('Everything in the reminders file has been deleted.')


def setup(bot):
	bot.add_cog(Owner(bot))
