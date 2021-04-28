import random
from discord.ext import commands


bot = commands.Bot(command_prefix='!')


@bot.command()
async def echo(context, arg):
	"""echo the input."""
	await context.send(arg)


# @bot.command()
# async def remind(context, arg):
# 	"""get a text-to-speech reminder message after x minutes (default: 15)."""
# 	args = string.split()
# 	if not len(args):
# 		await context.send(# 	if args[0].isnumeric() )and len(args) > 1:
# 		# TODO: wait args[0] minutes
# 	else:
# 		# TODO: wait 15 minutes

# 		await context.send('/tts ' + string.split(' ', 1))[1]
# 		# TODO: also mention the person who used this command.


@bot.command()
async def roll(context, arg1=1, arg2=6):
	"""roll a die. Optionally specify lowest and highest possible numbers (defaults are 1 and 6)."""
	
	arg1 = int(arg1)
	arg2 = int(arg2)

	if  arg1 <= arg2:
		await context.send(str(random.randint(arg1, arg2)))
	else:
		await context.send(f'{arg1} > {arg2}')


@bot.command(name='flip-coin')
async def flip_coin(context):
	"""flip a coin."""
	n = random.randint(1, 2)
	if n == 1:
		await context.send('heads')
	else:
		await context.send('tails')


@bot.command()
async def reverse(context, arg):
	"""reverse the input."""
	await context.send(arg[::-1])


@bot.command()
async def rot13(context, arg):
	"""rotate each letter 13 letters through the alphabet."""
	arg = arg.lower()
	new_string = ''
	alphabet = 'abcdefghijklmnopqrstuvwxyz'
	for char in arg:
		index = alphabet.find(char)
		if index != -1:
			new_index = (index + 13) % 26
			new_string += alphabet[new_index]
		else:
			new_string += char

	await context.send(new_string)
