import discord
import random
import linecache
from commands import *


class Random(commands.Cog):
	def __init__(self, bot):
		self.bot = bot


	@commands.command(aliases=['random'])
	@commands.cooldown(2, 10)
	async def rand(self, context, low: int = 1, high: int = 6):
		'''Gives a random number (default bounds are 1 and 6)'''
		low = int(low)
		high = int(high)
		if  low <= high:
			await context.send(str(random.randint(low, high)))
		else:
			await context.send(str(random.randint(high, low)))


	@commands.command(name='flip-coin', aliases=['flip'])
	@commands.cooldown(2, 10)
	async def flip_coin(self, context):
		'''Flips a coin'''
		n = random.randint(1, 2)
		if n == 1:
			await context.send('heads')
		else:
			await context.send('tails')


	@commands.command()
	@commands.cooldown(2, 10)
	async def quote(self, context):
		'''Shows a random famous quote'''
		# These three variables depend on the format of quotes.txt.
		first_quote_line = 4
		last_quote_line = 298
		delta = 3

		quote_count = (last_quote_line - first_quote_line) / delta
		rand_line = random.randint(0, quote_count) * delta + first_quote_line
		quote = linecache.getline('quotes.txt', rand_line)
		author = linecache.getline('quotes.txt', rand_line + 1)

		embed = discord.Embed(description=f'{quote}\n{author}')
		await context.send(embed=embed)


	# Source of the roll and choose commands: https://github.com/Rapptz/discord.py/blob/8517f1e085df27acd5191d0d0cb2363242be0c29/examples/basic_bot.py#L30
	# License: https://github.com/Rapptz/discord.py/blob/v1.7.1/LICENSE
	@commands.command()
	@commands.cooldown(2, 10)
	async def roll(self, context, dice: str):
		'''Rolls dice in NdN format'''
		try:
			rolls, limit = map(int, dice.split('d'))
		except Exception:
			await context.send('Error: format has to be in NdN.')
			return

		result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
		await context.send(result)


	@commands.command()
	@commands.cooldown(2, 10)
	async def choose(self, context, *choices: str):
		'''Chooses randomly between multiple choices'''
		await context.send(random.choice(choices))


bot.add_cog(Random(bot))
