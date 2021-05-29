from replit import db
import re
import ast
import asyncio
import datetime
import traceback
import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType


use_tts = False  # Text-to-speech for the reminder messages.


async def send_traceback(ctx, e):
    etype = type(e)
    trace = e.__traceback__
    lines = traceback.format_exception(etype, e, trace)
    traceback_text = ''.join(lines)
    await ctx.send(f'```\n{traceback_text}\n```')


class Reminder:
    def __init__(self, chosen_time: str, end_time: str, message: str, author_id: int, channel: int):
        self.chosen_time = chosen_time
        self.end_time = end_time
        self.message = message
        self.author_id = author_id
        self.channel = channel

    def __repr__(self):
        return f'Reminder("{self.chosen_time}", "{self.end_time}", "{self.message}", {self.author_id}, {self.channel})'

    def __eq__(self, other):
        return self.chosen_time == other.chosen_time \
            and self.end_time == other.end_time \
            and self.message == other.message \
            and self.author_id == other.author_id \
            and self.channel == other.channel

    def __ne__(self, other):
        return self.chosen_time != other.chosen_time \
            or self.end_time != other.end_time \
            or self.message != other.message \
            or self.author_id != other.author_id \
            or self.channel != other.channel


def eval_str(string):
    parsed = ast.parse(string, mode='eval')
    fixed = ast.fix_missing_locations(parsed)
    compiled = compile(fixed, '<string>', 'eval')
    return eval(compiled)


async def save_reminder(ctx, chosen_time: str, seconds: int, message: str) -> Reminder:
    '''Saves one reminder to the database'''
    start_time = datetime.datetime.now(datetime.timezone.utc)
    end_time = start_time + datetime.timedelta(0, seconds)
    end_time = end_time.isoformat()
    author_id = ctx.author.id
    channel = ctx.channel.id

    reminder = Reminder(chosen_time, end_time, message, author_id, channel)

    db[f'{author_id} {end_time}'] = repr(reminder)

    return reminder


async def continue_reminder(bot, reminder):
    '''Continues a reminder that had been stopped by a server restart'''
    
    channel = bot.get_channel(reminder.channel)
    try:
        current_time = datetime.datetime.now(datetime.timezone.utc)
        end_time = datetime.datetime.fromisoformat(reminder.end_time)
        remaining_time = end_time - current_time
        remaining_seconds = remaining_time.total_seconds()
        if remaining_seconds > 0:
            await asyncio.sleep(remaining_seconds)
            await channel.send(f'<@!{reminder.author_id}>, here is your {reminder.chosen_time} reminder: {reminder.message}', tts=use_tts)
        else:
            await channel.send(f'<@!{reminder.author_id}>, an error delayed your reminder: {reminder.message}', tts=use_tts)
            await channel.send(f'The reminder had been set for {end_time.year}-{end_time.month}-{end_time.day} at {end_time.hour}:{end_time.minute} UTC')

        await delete_reminder(reminder)
    except Exception as e:
        await channel.send(f'<@!{reminder.author_id}>, your reminder was cancelled because of an error: {e}')
        if await bot.is_owner(reminder.author_id):
            await send_traceback(channel, e)
            

async def delete_reminder(reminder):
    '''Removes one reminder from the database'''
    del db[f'{reminder.author_id} {reminder.end_time}']


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['reminder', 'remindme'])
    @commands.cooldown(1, 15, BucketType.user)
    async def remind(self, ctx, chosen_time: str, *, message: str):
        '''Sends a reminder, e.g. ;remind 1h30m iron socks
        
        The maximum time allowed is 2,147,483 seconds (24.85 days).
        See https://bugs.python.org/issue20493 for details.
        '''
        try:
            seconds = self.parse_time(chosen_time)
            if seconds > 2147483:
                raise ValueError('The maximum time possible is 24.85 days.')
            await ctx.send(f'Reminder set! In {chosen_time}, I will remind you: {message}')
            reminder = await save_reminder(ctx, chosen_time, seconds, message)

            await asyncio.sleep(seconds)
            await ctx.send(f'{ctx.author.mention}, here is your {chosen_time} reminder: {message}', tts=use_tts)
            await delete_reminder(reminder)
        except Exception as e:
            await ctx.send(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')
            if await ctx.bot.is_owner(ctx.author):
                await send_traceback(ctx, e)


    @commands.command(name='list-r', aliases=['list-reminders'])
    @commands.cooldown(1, 15, BucketType.user)
    async def list_reminders(self, ctx):
        '''Shows all of your reminders'''
        r_keys = db.prefix(f'{ctx.author.id}')
        r_keys = sorted(r_keys)

        if not len(r_keys):
            await ctx.send('You have no saved reminders.')
        else:
            r_list = 'Here are your in-progress reminders:'
            for i, key in enumerate(r_keys):
                reminder = eval_str(db[key])
                end_time = datetime.datetime.fromisoformat(reminder.end_time)
                remaining = end_time - datetime.datetime.now(datetime.timezone.utc)

                r_list += f'\n\n{i+1}. "{reminder.message}"\nduration: {reminder.chosen_time}\ntime remaining: {str(remaining)}'
            embed = discord.Embed(description=r_list)
            await ctx.send(embed=embed)


    @commands.command(name='del-r', aliases=['del-reminder', 'delete-reminder'])
    @commands.cooldown(1, 15, BucketType.user)
    async def del_r(self, ctx, index: int):
        '''Deletes a reminder by its index shown with list-r
        
        Currently, this only deletes a reminder from the database,
        not from the program. A deleted reminder will then only be
        cancelled if the bot is restarted.
        '''
        r_keys = db.prefix(f'{ctx.author.id}')
        r_keys = sorted(r_keys)
        
        if not len(r_keys):
            await ctx.send('You have no saved reminders.')
        else:
            try:
                key = r_keys[index-1]
            except KeyError:
                await ctx.send('Reminder not found.')
            else:
                reminder = eval_str(db[key])
                await ctx.send(f'Reminder deleted: "{reminder.message}"')
                del db[key]

        
    @del_r.error
    async def del_r_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            if error.param.name == 'index':
                await ctx.send('Error: missing argument. Use the reminder\'s index number shown in the list-r command.')
        else:
            await ctx.send(error)


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


def setup(bot):
    bot.add_cog(Reminders(bot))
