import random
from discord.ext import commands


bot = commands.Bot(command_prefix=';')


@bot.command()
async def echo(context, *, message):
	'''Display a message.'''
	await context.send(message)


@bot.command()
async def ping(context):
	'''Ping the server.'''
	await context.send(f'Pong! It took {round(bot.latency, 2)} ms.')


@bot.command(name='eval')
async def calc(context, *, string):
	'''Evaluate a Python expression.'''
	try:
		await context.send(eval(string))
	except Exception as e:
		await context.send(f'eval error: {e}')


@bot.command()
async def roll(context, low=1, high=6):
	'''Roll a die. Default bounds are 1 and 6.'''
	
	low = int(low)
	high = int(high)

	if  low <= high:
		await context.send(str(random.randint(low, high)))
	else:
		await context.send(f'{low} > {high}')


@bot.command(name='flip-coin')
async def flip_coin(context):
	'''Flip a coin.'''
	n = random.randint(1, 2)
	if n == 1:
		await context.send('heads')
	else:
		await context.send('tails')


@bot.command()
async def reverse(context, *, message):
	'''Reverse a message.'''
	await context.send(message[::-1])


@bot.command()
async def rot13(context, *, message):
	'''Rotate each letter of a message 13 letters through the alphabet.'''
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
