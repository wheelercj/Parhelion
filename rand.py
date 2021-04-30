import random
from commands import *


class Random(commands.Cog):
	def __init__(self, bot):
		self.bot = bot


	@commands.command(aliases=['random'])
	async def rand(self, context, low: int = 1, high: int = 6):
		'''Get a random number. Default bounds are 1 and 6.'''
		low = int(low)
		high = int(high)
		if  low <= high:
			await context.send(str(random.randint(low, high)))
		else:
			await context.send(str(random.randint(high, low)))


	@commands.command()
	async def roll(self, context, dice: str):
		'''Roll dice in NdN format.'''
		try:
			rolls, limit = map(int, dice.split('d'))
		except Exception:
			await context.send('Error: format has to be in NdN.')
			return

		result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
		await context.send(result)


	@commands.command(name='flip-coin', aliases=['flip'])
	async def flip_coin(self, context):
		'''Flip a coin.'''
		n = random.randint(1, 2)
		if n == 1:
			await context.send('heads')
		else:
			await context.send('tails')


	@commands.command()
	async def choose(self, context, *choices: str):
		'''Choose randomly between multiple choices.'''
		await context.send(random.choice(choices))


bot.add_cog(Random(bot))
