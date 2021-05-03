from discord.ext import commands


bot = commands.Bot(command_prefix=';')


@bot.command()
async def echo(context, *, message: str):
	'''Displays a message'''
	await context.send(message)


@bot.command()
async def ping(context):
	'''Pings the server'''
	await context.send(f'Pong! It took {round(bot.latency, 2)} ms.')


@bot.command(aliases=['python', 'eval'])
async def py(context, *, string: str):
	'''Evaluates a Python expression and returns the result

	Print statements don't work with this because they don't return anything.
	'''
	try:
		await context.send(eval(string))
	except Exception as e:
		await context.send(f'Python error: {e}')


@bot.command()
async def calc(context, *, string: str):
	'''Evaluates a math expression
	
	This is an alias of ;py
	'''
	try:
		await context.send(eval(string))
	except Exception as e:
		await context.send(f'Python error: {e}')


@bot.command(hidden=True)
async def reverse(context, *, message: str):
	'''Reverses a message'''
	await context.send(message[::-1])


@bot.command(hidden=True)
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
