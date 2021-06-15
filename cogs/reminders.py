# External imports
from replit import db
import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands

# Internal imports
from common import send_traceback
from task import Reminder
from tasks import create_task_key, save_task, delete_task


reminders_logger = logging.getLogger('reminders')
reminders_logger.setLevel(logging.ERROR)
reminders_handler = logging.FileHandler(filename='reminders.log', encoding='utf-8')
reminders_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(lineno)s: %(message)s'))
if not reminders_logger.hasHandlers():
    reminders_logger.addHandler(reminders_handler)


async def eval_reminder(string: str) -> Reminder:
    '''Turns a reminder str into a Reminder object'''
    if not string.startswith('Reminder(') \
            or not string.endswith(')'):
        raise ValueError

    string = string[9:-1]
    args = string.split(', ')

    try:
        message: str = args[0][1:-1]
        author_id = int(args[1])
        start_time: str = args[2][1:-1]
        target_time: str = args[3][1:-1]
        duration: str = args[4][1:-1]
        is_dm = bool(args[5][1:-1])
        guild_id = int(args[6])
        channel_id = int(args[7])

        reminder = Reminder(message, author_id, start_time, target_time, duration, is_dm, guild_id, channel_id)

        if len(args) != 8:
            await delete_task(task=reminder)
            log_message = f'Incorrect number of args. Deleting {reminder}'
            reminders_logger.log(logging.ERROR, log_message)
            raise ValueError(log_message)
        
        return reminder

    except IndexError as e:
        await delete_task(task_type='reminder', author_id=author_id, target_time=target_time)
        log_message = f'Index error. Deleting {author_id} {target_time}. Error details: {e}'
        reminders_logger.log(logging.ERROR, log_message)
        raise IndexError(log_message)


async def save_reminder(ctx, duration: str, seconds: int, message: str) -> Reminder:
    '''Saves one reminder to the database'''
    start_time = datetime.now(timezone.utc)
    target_time = start_time + timedelta(0, seconds)
    target_time = target_time.isoformat()
    reminder = await save_task(ctx, 'reminder', target_time, duration, Reminder, message)
    
    return reminder


async def continue_reminder(bot, reminder_str: str):
    '''Continues a reminder that had been stopped by a server restart'''
    reminder = await eval_reminder(reminder_str)

    try:
        destination = await reminder.get_destination(bot)

        current_time = datetime.now(timezone.utc)
        target_time = datetime.fromisoformat(reminder.target_time)
        remaining_time = target_time - current_time
        remaining_seconds = remaining_time.total_seconds()

        if remaining_seconds > 0:
            await asyncio.sleep(remaining_seconds)
            await destination.send(f'<@!{reminder.author_id}>, here is your {reminder.duration} reminder: {reminder.message}')
            await delete_task(task=reminder)
            reminders_logger.log(logging.INFO, f'deleting {reminder}')
        else:
            await destination.send(f'<@!{reminder.author_id}>, an error delayed your reminder: {reminder.message}')
            await destination.send(f'The reminder had been set for {target_time.year}-{target_time.month}-{target_time.day} at {target_time.hour}:{target_time.minute} UTC')
            await delete_task(task=reminder)
            reminders_logger.log(logging.ERROR, f'Delayed delivery. Deleting {reminder}')

    except Exception as e:
        await destination.send(f'<@!{reminder.author_id}>, your reminder was cancelled because of an error: {e}')
        if await bot.is_owner(reminder.author_id):
            await send_traceback(destination, e)
        await delete_task(task=reminder)
        reminders_logger.log(logging.ERROR, f'deleting {reminder} because {e}')
        raise e


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['add-r', 'reminder', 'remindme'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def remind(self, ctx, duration: str, *, message: str):
        '''Sends you a reminder, e.g. ;remind 1h30m iron socks
        
        The maximum time allowed is 24.85 days (see https://bugs.python.org/issue20493 for details).
        '''
        # Remove some chars for security and simplicity.
        to_remove = ['"', '\'', ',', '\\', '{', '}']
        for char in to_remove:
            message.replace(char, '')

        try:
            seconds = self.parse_time(duration)
            if seconds > 2147483:
                raise ValueError('The maximum time possible is 24.85d')
            await ctx.send(f'Reminder set! In {duration}, I will remind you: {message}')
            reminder = await save_reminder(ctx, duration, seconds, message)

            await asyncio.sleep(seconds)

            await ctx.send(f'{ctx.author.mention}, here is your {duration} reminder: {message}')
            await delete_task(task=reminder)
            reminders_logger.log(logging.INFO, f'deleting {reminder}')        
        except Exception as e:
            await ctx.send(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')
            if await ctx.bot.is_owner(ctx.author):
                await send_traceback(ctx, e)


    @commands.command(name='list-r', aliases=['list-reminders'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def list_reminders(self, ctx):
        '''Shows all of your reminders'''
        task_key_prefix = await create_task_key('reminder', ctx.author.id)
        r_keys = db.prefix(task_key_prefix)
        r_keys = sorted(r_keys)

        if not len(r_keys):
            await ctx.send('You have no saved reminders.')
        else:
            r_list = 'Here are your in-progress reminders:'
            for i, key in enumerate(r_keys):
                try:
                    reminder = await eval_reminder(db[key])
                    target_time = datetime.fromisoformat(reminder.target_time)
                    remaining = target_time - datetime.now(timezone.utc)
                    if str(remaining).startswith('-'):
                        raise ValueError('Negative time remaining.')

                    r_list += f'\n\n{i+1}. "{reminder.message}"\nduration: {reminder.duration}\ntime remaining: {str(remaining)}'
                except Exception as e:
                    log_message = f'Deleting {db[key]} because {e}'
                    reminders_logger.log(logging.ERROR, log_message)
                    del db[key]
                    await ctx.send(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')

            embed = discord.Embed(description=r_list)
            await ctx.send(embed=embed)


    @commands.command(name='del-r', aliases=['del-reminder', 'delete-reminder'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def del_r(self, ctx, index: int):
        '''Deletes a reminder by its index
        
        Currently, this only deletes a reminder from the database,
        not from the program. A deleted reminder will then only be
        cancelled if the bot is restarted.
        '''
        task_key_prefix = await create_task_key('reminder', ctx.author.id)
        r_keys = db.prefix(task_key_prefix)
        r_keys = sorted(r_keys)
        
        if not len(r_keys):
            await ctx.send('You have no saved reminders.')
        else:
            try:
                key = r_keys[index-1]
                reminder = await eval_reminder(db[key])
                await ctx.send(f'Reminder deleted: "{reminder.message}"')
                log_message = f'deleting {db[key]}'
                reminders_logger.log(logging.INFO, log_message)
                del db[key]
            except KeyError:
                await ctx.send('Reminder not found.')

        
    @del_r.error
    async def del_r_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send('Error: missing argument. Use the reminder\'s index number shown in the list-r command.')
            await ctx.send(error)
        elif isinstance(error, commands.BadArgument):
            await ctx.send('Error: use the reminder\'s index number shown in the list-r command.')


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
