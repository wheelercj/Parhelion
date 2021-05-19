import re
import asyncio
import datetime
import pickle
from commands import *


reminders_file = 'reminders.txt'
use_tts = False  # Text-to-speech for the reminder messages.


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

	def __eq__(self, other):
		return self.chosen_time == other.chosen_time \
			and self.start_time == other.start_time \
			and self.end_time == other.end_time \
			and self.message == other.message \
			and self.author == other.author \
			and self.channel == other.channel

	def __ne__(self, other):
		return self.chosen_time != other.chosen_time \
			or self.start_time != other.start_time \
			or self.end_time != other.end_time \
			or self.message != other.message \
			or self.author != other.author \
			or self.channel != other.channel


@bot.command(aliases=['reminder', 'remindme'])
@commands.cooldown(3, 15)
async def remind(context, chosen_time: str = '15m', *, message: str = ''):
	'''Gives a reminder, e.g. ;remind 1h30m iron socks
	
	Currently, these reminders are saved in a publicly accessible file.
	'''
	await context.send(f'Reminder set! In {chosen_time}, I will remind you: {message}')
	try:
		seconds = parse_time(chosen_time)
		reminder = await save_reminder(context, chosen_time, seconds, message)

		await asyncio.sleep(seconds)
		await context.send(f'{context.author.mention}, here is your {chosen_time} reminder: {message}', tts=use_tts)
		await delete_reminder(reminder, bot)
	except Exception as e:
		if e == 'invalid load key, \'\\xef\'':
			await context.send(f'Reminder error: {e}.')
			with open(reminders_file, 'w') as _:
				pass
		else:
			await context.send(f'{context.author.mention}, your reminder was cancelled because of an error: {e}')


@bot.command(hidden=use_hidden, name='del-r.txt')
@commands.is_owner()
@commands.cooldown(3, 15)
async def delete_reminders_txt(context):
	'''Deletes everything in reminders.txt
	
	For recovering from errors that make the file unparseable.
	'''
	with open(reminders_file, 'w') as _:
		pass
	dev_mail(bot, 'All reminders deleted.', use_embed=False)

	
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


async def save_reminder(context, chosen_time: str, seconds: int, message: str):
	'''Save one reminder to the saved reminders file.'''
	start_time = datetime.datetime.now()
	end_time = start_time + datetime.timedelta(0, seconds)
	author = str(context.author.mention)
	channel = context.channel.id

	reminder = Reminder(chosen_time, start_time, end_time, message, author, channel)
	with open(reminders_file, 'ab') as file:
		pickle.dump(reminder, file)
	
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

	if len(reminders):
		if type(reminders[0]) is Reminder:
			return reminders
		else:
			return reminders[0]


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
			await channel.send(f'{reminder.author}, here is your {reminder.chosen_time} reminder: {reminder.message}', tts=use_tts)
		else:
			await channel.send(f'{reminder.author}, an error delayed your reminder: {reminder.message}', tts=use_tts)
			await channel.send(f'The reminder had been set for {end_time.year}-{end_time.month}-{end_time.day} at {end_time.hour}:{end_time.minute} UTC')

		await delete_reminder(reminder)
	except Exception as e:
		await channel.send(f'{reminder.author.mention}, your reminder was cancelled because of an error: {e}')


async def delete_reminder(reminder, bot):
	'''Remove one reminder from the file of saved reminders.'''
	reminders = load_reminders()
	try:
		reminders.remove(reminder)
		with open(reminders_file, 'wb') as file:
			for r in reminders:
				pickle.dump(r, file)
	except Exception as e:
		await dev_mail(bot, f'Error: failed to delete reminder: {reminder}\nbecause of error: {e}')
