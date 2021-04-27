# This is a Discord bot that gives simple responses to specific phrases.
# Created with the help of these guides:
# https://ritza.co/showcase/repl.it/building-a-discord-bot-with-python-and-repl-it.html
# https://www.freecodecamp.org/news/create-a-discord-bot-with-python/

import discord
import os
import re
#from commands import *
from keep_alive import keep_alive

import random
from discord.ext import commands

# command_symbol = '!'
# commands = {
# 	'echo': echo,
# 	'remind': remind,
# 	'roll': roll,
# 	'flip-coin': flip_coin,
# 	'reverse': reverse,
# 	'rot13': rot13,
# }


# def Help_all():
# 	commands_list = ['help'] + list(commands.keys())
# 	commands_list = sorted(commands_list)
# 	commands_str = 'Here\'s a list of all commands:'
# 	for c in commands_list:
# 		commands_str += '\n    ' + c
# 	return commands_str


# def Help(string):
# 	if string in commands:
# 		return f'Use `!{string}` to ' + commands[string].__doc__
# 	elif string == 'help':
# 		return 'Use `!help` to get a list of all commands or a description of a specific command.'
# 	else:
# 		return 'undefined'


my_secret = os.environ['DISCORD_BOT_SECRET']
client = discord.Client()


bot = commands.Bot(command_prefix='!')


@bot.command()
async def echo(context, arg):
	"""echo the input."""
	print('echo')
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
async def roll(context, arg1, arg2):
	"""roll a die. Optionally specify lowest and highest possible numbers (defaults are 1 and 6)."""
	
	low = 1
	high = 6
	if arg1:
		low = int(arg1)
	if arg2:
		high = int(arg2)

	if  low <= high:
		await context.send(str(random.randint(low, high)))
	else:
		await context.send(f'{low} > {high}')


@bot.command()
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


# here


@client.event
async def on_ready():
	print('Ready')
	print(client.user)


@client.event
async def on_message(message):
	if message.author != client.user:
		# command_match = re.search(rf'(?<=^{command_symbol})\S+', message.content)
		# if command_match:
		# 	command_name = command_match[0]
		# 	args_match = re.search(rf'(?<= ).+', message.content)

		# 	output = ''
		# 	if command_name == 'help':
		# 		if args_match:
		# 			output = Help(args_match[0])
		# 		else:
		# 			output = Help_all()
		# 	elif command_name in commands:
		# 		if args_match:
		# 			output = commands[command_name](args_match[0])
		# 		else:
		# 			output = commands[command_name]('')
				
		# 	if output and len(output):
		# 		await message.channel.send(output)


# @client.event
# async def on_message(message):
# 	if message.author != client.user:
# 		command_match = re.search(rf'(?<=^{command_symbol})\S+', message.content)
# 		if command_match:
# 			command_name = command_match[0]
# 			args_match = re.search(rf'(?<= ).+', message.content)

# 			output = ''
# 			if command_name == 'help':
# 				if args_match:
# 					output = Help(args_match[0])
# 				else:
# 					output = Help_all()
# 			elif command_name in commands:
# 				if args_match:
# 					output = commands[command_name](args_match[0])
# 				else:
# 					output = commands[command_name]('')
				
# 			if output and len(output):
# 				await message.channel.send(output)


keep_alive()
token = os.environ.get('DISCORD_BOT_SECRET')
client.run(token)
