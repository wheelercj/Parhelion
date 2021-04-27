# This is a Discord bot that gives simple responses to specific phrases.
# Created with the help of this guide: https://ritza.co/showcase/repl.it/building-a-discord-bot-with-python-and-repl-it.html

import discord
import os
import re
from commands import *
from keep_alive import keep_alive


command_symbol = '!'
commands = {
	'echo': echo,
	'remind': remind,
	'roll': roll,
	'flip-coin': flip_coin,
	'reverse': reverse,
	'rot13': rot13,
}


def Help_all():
	commands_list = ['help'] + list(commands.keys())
	commands_list = sorted(commands_list)
	commands_str = 'Here\'s a list of all commands:'
	for c in commands_list:
		commands_str += '\n    ' + c
	return commands_str


def Help(string):
	if string in commands:
		return f'Use `!{string}` to ' + commands[string].__doc__
	elif string == 'help':
		return 'Use `!help` to get a list of all commands or a description of a specific command.'
	else:
		return 'undefined'


my_secret = os.environ['DISCORD_BOT_SECRET']
client = discord.Client()


@client.event
async def on_ready():
	print('Ready')
	print(client.user)


@client.event
async def on_message(message):
	if message.author != client.user:
		command_match = re.search(rf'(?<=^{command_symbol})\S+', message.content)
		if command_match:
			command_name = command_match[0]
			args_match = re.search(rf'(?<= ).+', message.content)

			output = ''
			if command_name == 'help':
				if args_match:
					output = Help(args_match[0])
				else:
					output = Help_all()
			elif command_name in commands:
				if args_match:
					output = commands[command_name](args_match[0])
				else:
					output = commands[command_name]('')
				
			if output and len(output):
				await message.channel.send(output)


keep_alive()
token = os.environ.get('DISCORD_BOT_SECRET')
client.run(token)
