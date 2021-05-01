import re
import asyncio
import datetime
import pickle
import discord
from commands import *


reminders_file = 'reminders.txt'


class Reminder:
	def __init__(self, chosen_time: str, start_time: datetime.datetime, end_time: datetime.datetime, message: str, author: str, channel: int):
		self.chosen_time = chosen_time
		self.start_time = start_time
		self.end_time = end_time
		self.message = message
		self.author = author
		self.channel = channel

	def __repr__(self):
		return f'Reminder("{self.chosen_time}", {self.start_time}, {self.end_time}, "{self.message}", "{self.author}", {self.channel})'


def parse_time(Time: str) -> float:
	'''Convert a str of one or multiple units of time to a float of seconds.
	
	The str must be in a certain format. Valid examples:
		2h45m
		30s
		2d5h30m
	'''
	seconds = 0.0
	while True:
		unit_match = re.search(r'[dhms]', Time)
		if not unit_match:
			return seconds
		else:
			unit = unit_match[0]
			index = unit_match.start()
			value = Time[:index]
			Time = Time[index+1:]

			if unit == 'd':
				seconds += float(value) * 24 * 60 * 60
			elif unit == 'h':
				seconds += float(value) * 60 * 60
			elif unit == 'm':
				seconds += float(value) * 60
			elif unit == 's':
				seconds += float(value)
			else:
				raise SyntaxError


@bot.command(hidden=True)
async def save_reminder(context, chosen_time: str, seconds: int, message: str):
	'''Save one reminder to the saved reminders file.'''
	start_time = datetime.datetime.now()
	end_time = start_time + datetime.timedelta(0, seconds)
	author = str(context.author.mention)
	channel = context.channel.id

	reminder = Reminder(chosen_time, start_time, end_time, message, author, channel)
	with open(reminders_file, 'wb') as file:
		pickle.dump(reminder, file)  # TODO: this might not append, it might overwrite everything.
	
	return reminder


def load_reminders():
	'''Load and return all reminders from the saved reminders file.'''
	reminders = []
	with open(reminders_file, 'rb') as file:
		while True:
			try:
				reminders.append(pickle.load(file))
			except EOFError:
				break

	return reminders


async def cotinue_reminder(reminder, bot):
	'''Continue a reminder that had been stopped by a server restart.'''
	
	channel = bot.get_channel(reminder.channel)
	try:
		current_time = datetime.datetime.now()
		end_time = reminder.end_time
		remaining_time = end_time - current_time
		remaining_seconds = remaining_time.total_seconds()
		if remaining_seconds > 0:
			await asyncio.sleep(remaining_seconds)
			await channel.send(f'{reminder.author}, here is your {reminder.chosen_time} reminder: {reminder.message}', tts=True)
		else:
			await channel.send(f'{reminder.author}, a connection problem delayed your reminder: {reminder.message}', tts=True)
			await channel.send(f'The reminder had been set for {end_time.year}-{end_time.month}-{end_time.day} at {end_time.hour}:{end_time.minute} UTC')

		delete_reminder(reminder)
	except Exception as e:
		await channel.send(f'{reminder.author}, your reminder encountered an error: {e}')


def delete_reminder(reminder):
	'''Remove one reminder from the file of saved reminders.'''
	reminders = load_reminders()
	for r in reminders:  # TODO: I'm assuming reminders is a list.
		if r == reminder:
			reminders.remove(r)
	# TODO: overwrite the entire file with `reminders`, or rewrite this to only delete the one reminder from the file.


@bot.command(aliases=['reminder'])
async def remind(context, chosen_time: str = '15m', message: str = ''):
	'''Get a reminder. E.g. ;remind 1h30m "iron socks"'''
	await context.send(f'Reminder set!')
	try:
		seconds = parse_time(chosen_time)
		reminder = await save_reminder(context, chosen_time, seconds, message)

		await asyncio.sleep(seconds)
		await context.send(f'{context.author.mention}, here is your {chosen_time} reminder: {message}', tts=True)
		delete_reminder(reminder)
	except Exception as e:
		await context.send(f'{context.author.mention}, your reminder encountered an error: {e}')
