# External imports
import re
import asyncio
import datetime
import pickle
import traceback
import discord
from discord.ext import commands

# Internal imports
from other import dev_mail


class Reminder:
	def __init__(self, chosen_time: str, start_time: datetime.datetime, end_time: datetime.datetime, message: str, author_mention: str, author_id: int, channel: int):
		self.chosen_time = chosen_time
		self.start_time = start_time
		self.end_time = end_time
		self.message = message
		self.author_mention = author_mention
		self.author_id = author_id
		self.channel = channel

	def __repr__(self):
		return f'Reminder("{self.chosen_time}", {self.start_time}, {self.end_time}, "{self.message}", "{self.author_mention}", {self.author_id}, {self.channel})'

	def __eq__(self, other):
		return self.chosen_time == other.chosen_time \
			and self.start_time == other.start_time \
			and self.end_time == other.end_time \
			and self.message == other.message \
			and self.author_mention == other.author_mention \
			and self.author_id == other.author_id \
			and self.channel == other.channel

	def __ne__(self, other):
		return self.chosen_time != other.chosen_time \
			or self.start_time != other.start_time \
			or self.end_time != other.end_time \
			or self.message != other.message \
			or self.author_mention != other.author_mention \
			or self.author_id != other.author_id \
			or self.channel != other.channel


class Reminders(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.reminders_file = 'reminders.txt'
		self.use_tts = False  # Text-to-speech for the reminder messages.


	@commands.command(aliases=['reminder', 'remindme'])
	@commands.cooldown(3, 15)
	async def remind(self, ctx, chosen_time: str, *, message: str):
		'''Sends a reminder, e.g. ;remind 1h30m iron socks
		
		Currently, these reminders are saved in a publicly accessible file.
		The maximum time allowed is 2,147,483 seconds (24.85 days).
		See https://bugs.python.org/issue20493 for details.
		'''
		try:
			seconds = self.parse_time(chosen_time)
			if seconds > 2147483:
				raise ValueError('The maximum time possible is 24.85 days.')
			await ctx.send(f'Reminder set! In {chosen_time}, I will remind you: {message}')
			reminder = await self.save_reminder(ctx, chosen_time, seconds, message)

			await asyncio.sleep(seconds)
			await ctx.send(f'{ctx.author.mention}, here is your {chosen_time} reminder: {message}', tts=self.use_tts)
			await self.delete_reminder(reminder)
		except Exception as e:
			if e == 'invalid load key, \'\\xef\'':
				await ctx.send(f'Reminder error: {e}.')
				with open(self.reminders_file, 'w') as _:
					pass
			else:
				await ctx.send(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')
				if await ctx.bot.is_owner(ctx.author):
					await self.send_traceback(ctx, e)


	@commands.command(name='list-r', aliases=['list-reminders'])
	@commands.cooldown(3, 15)
	async def list_reminders(self, ctx):
		'''Shows all of your reminders'''
		reminders, author_reminders = await self.load_author_reminders(ctx)

		if author_reminders is None:
			await ctx.send('You have no saved reminders.')
		else:
			r_str = 'Here are your in-progress reminders:'
			for i, r in enumerate(author_reminders):
				remaining = r.end_time - datetime.datetime.now(datetime.timezone.utc)
				r_str += f'\n\n{i+1}. "{r.message}"\nduration: {r.chosen_time}\ntime remaining: {str(remaining)}'
			embed = discord.Embed(description=r_str)
			await ctx.send(embed=embed)


	@commands.command(name='del-r', aliases=['del-reminder', 'delete-reminder'])
	@commands.cooldown(3, 15)
	async def del_r(self, ctx, *, index: int):
		'''Deletes a reminder by its index in list-r
		
		Currently, this only deletes a reminder from the saved reminders file, not
		from the program. A deleted reminder will then only be cancelled if the
		bot is restarted.
		'''
		reminders, author_reminders = await self.load_author_reminders(ctx)
		
		if author_reminders is None:
			await ctx.send('You have no saved reminders.')
		else:
			if index > len(author_reminders):
				await ctx.send('Reminder index not found. Use list-r.')
			else:
				reminders.remove(author_reminders[index-1])
				await ctx.send(f'Reminder deleted: "{author_reminders[index-1].message}"')
				with open(self.reminders_file, 'wb') as file:
					pickle.dump(reminders, file)


	async def load_author_reminders(self, ctx):
		'''Returns the lists of reminders and ctx.author\'s reminders
		
		Returns None for either/both of those that there are none of.
		'''
		reminders = await self.load_reminders()
		if reminders is None:
			return None, None
		else:
			author_reminders = []
			for r in reminders:
				if r.author_id == ctx.author.id:
					author_reminders.append(r)

			if author_reminders is None:
				return reminders, None
			else:
				return reminders, author_reminders


	async def send_traceback(self, ctx, e):
		etype = type(e)
		trace = e.__traceback__
		lines = traceback.format_exception(etype, e, trace)
		traceback_text = ''.join(lines)
		await ctx.send(f'```\n{traceback_text}\n```')

		
	def parse_time(self, Time: str) -> float:
		'''Converts a str of one or multiple units of time to a float of seconds
		
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


	async def save_reminder(self, ctx, chosen_time: str, seconds: int, message: str):
		'''Saves one reminder to the saved reminders file'''
		start_time = datetime.datetime.now(datetime.timezone.utc)
		end_time = start_time + datetime.timedelta(0, seconds)
		author_mention = str(ctx.author.mention)
		author_id = ctx.author.id
		channel = ctx.channel.id

		reminder = Reminder(chosen_time, start_time, end_time, message, author_mention, author_id, channel)
		with open(self.reminders_file, 'ab') as file:
			pickle.dump(reminder, file)
		
		return reminder


	async def load_reminders(self):
		'''Loads and return all reminders from the saved reminders file'''
		reminders = []
		with open(self.reminders_file, 'rb') as file:
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


	async def cotinue_reminder(self, reminder):
		'''Continues a reminder that had been stopped by a server restart'''
		
		channel = self.bot.get_channel(reminder.channel)
		try:
			current_time = datetime.datetime.now(datetime.timezone.utc)
			end_time = reminder.end_time
			remaining_time = end_time - current_time
			remaining_seconds = remaining_time.total_seconds()
			if remaining_seconds > 0:
				await asyncio.sleep(remaining_seconds)
				await channel.send(f'{reminder.author_mention}, here is your {reminder.chosen_time} reminder: {reminder.message}', tts=self.use_tts)
			else:
				await channel.send(f'{reminder.author_mention}, an error delayed your reminder: {reminder.message}', tts=self.use_tts)
				await channel.send(f'The reminder had been set for {end_time.year}-{end_time.month}-{end_time.day} at {end_time.hour}:{end_time.minute} UTC')

			await self.delete_reminder(reminder)
		except Exception as e:
			await channel.send(f'{reminder.author_mention}, your reminder was cancelled because of an error: {e}')
			if await self.bot.is_owner(reminder.author_id):
				await self.send_traceback(channel, e)


	async def delete_reminder(self, reminder):
		'''Removes one reminder from the file of saved reminders'''
		reminders = await self.load_reminders()
		try:
			reminders.remove(reminder)
			with open(self.reminders_file, 'wb') as file:
				for r in reminders:
					pickle.dump(r, file)
		except Exception as e:
			await dev_mail(self.bot, f'Error: failed to delete reminder: {reminder}\nbecause of error: {e}')


def setup(bot):
	bot.add_cog(Reminders(bot))
