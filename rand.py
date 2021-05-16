import random
import linecache
from commands import *


class Random(commands.Cog):
	def __init__(self, bot):
		self.bot = bot


	@commands.command(aliases=['random'])
	async def rand(self, context, low: int = 1, high: int = 6):
		'''Gives a random number (default bounds are 1 and 6)'''
		low = int(low)
		high = int(high)
		if  low <= high:
			await context.send(str(random.randint(low, high)))
		else:
			await context.send(str(random.randint(high, low)))


	@commands.command(name='flip-coin', aliases=['flip'])
	async def flip_coin(self, context):
		'''Flips a coin'''
		n = random.randint(1, 2)
		if n == 1:
			await context.send('heads')
		else:
			await context.send('tails')


	# Source of the roll and choose commands: https://github.com/Rapptz/discord.py/blob/8517f1e085df27acd5191d0d0cb2363242be0c29/examples/basic_bot.py#L30
	# License: https://github.com/Rapptz/discord.py/blob/v1.7.1/LICENSE
	@commands.command()
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
	async def choose(self, context, *choices: str):
		'''Chooses randomly between multiple choices'''
		await context.send(random.choice(choices))


bot.add_cog(Random(bot))
