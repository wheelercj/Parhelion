from discord.ext import commands


bot = commands.Bot(command_prefix=';')


@bot.command()
async def echo(context, *, message: str):
	'''Display a message.'''
	await context.send(message)


@bot.command()
async def ping(context):
	'''Ping the server.'''
	await context.send(f'Pong! It took {round(bot.latency, 2)} ms.')


@bot.command(aliases=['python', 'eval'])
async def py(context, *, string: str):
	'''Evaluate a Python expression and return the output.
	
	Print statements don't work with this because they don't return anything.
	'''
	try:
		await context.send(eval(string))
	except Exception as e:
		await context.send(f'Python error: {e}')


@bot.command()
async def reverse(context, *, message: str):
	'''Reverse a message.'''
	await context.send(message[::-1])


@bot.command()
async def rot13(context, *, message: str):
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
