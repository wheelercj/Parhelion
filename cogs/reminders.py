# External imports
from replit import db
import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

# Internal imports
from common import send_traceback


reminders_logger = logging.getLogger('reminders')
reminders_logger.setLevel(logging.DEBUG)
reminders_handler = logging.FileHandler(filename='reminders.log', encoding='utf-8')
reminders_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(lineno)s: %(message)s'))
if not reminders_logger.hasHandlers():
    reminders_logger.addHandler(reminders_handler)


class Reminder:
    def __init__(self, chosen_time: str, end_time: str, message: str, author_id: int, guild_id: int, channel_id: int):
        self.chosen_time = chosen_time
        self.end_time = end_time
        self.message = message
        self.author_id = author_id
        self.guild_id = guild_id
        self.channel_id = channel_id

    def __repr__(self):
        return f'Reminder("{self.chosen_time}", "{self.end_time}", "{self.message}", {self.author_id}, {self.guild_id}, {self.channel_id})'

    def __eq__(self, other):
        return self.chosen_time == other.chosen_time \
            and self.end_time == other.end_time \
            and self.message == other.message \
            and self.author_id == other.author_id \
            and self.guild_id == other.guild_id \
            and self.channel_id == other.channel_id

    def __ne__(self, other):
        return self.chosen_time != other.chosen_time \
            or self.end_time != other.end_time \
            or self.message != other.message \
            or self.author_id != other.author_id \
            or self.guild_id != other.guild_id \
            or self.channel_id != other.channel_id


async def eval_reminder(string: str) -> Reminder:
    if not string.startswith('Reminder(') \
            or not string.endswith(')'):
        raise ValueError

    string = string[9:-1]
    args = string.split(', ')

    try:
        chosen_time: str = args[0][1:-1]
        end_time: str = args[1][1:-1]
        message: str = args[2][1:-1]
        author_id = int(args[3])
        guild_id = int(args[4])
        channel_id = int(args[5])

        reminder = Reminder(chosen_time, end_time, message, author_id, guild_id, channel_id)

        if len(args) != 6:
            await delete_reminder(reminder, logging.ERROR)
            raise ValueError('Error! Must delete a reminder.')

        return reminder
    except IndexError as e:
        del db[f'reminder {author_id} {end_time}']
        log_message = f'deleting reminder {author_id} {end_time}'
        reminders_logger.log(logging.ERROR, log_message)
        raise IndexError(f'Error! Must delete reminder: "{message}"\n   because {e}')


async def save_reminder(ctx, chosen_time: str, seconds: int, message: str) -> Reminder:
    '''Saves one reminder to the database'''
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(0, seconds)
    end_time = end_time.isoformat()
    author_id = ctx.author.id
    guild_id = ctx.guild.id
    channel_id = ctx.channel.id

    reminder = Reminder(chosen_time, end_time, message, author_id, guild_id, channel_id)

    db[f'reminder {author_id} {end_time}'] = repr(reminder)

    return reminder


async def continue_reminder(bot, reminder_str: str):
    '''Continues a reminder that had been stopped by a server restart'''
    reminder = await eval_reminder(reminder_str)
    guild = bot.get_guild(reminder.guild_id)

    try:
        channel = guild.get_channel(reminder.channel_id)
        if channel is None:
            raise ValueError('Channel not found. The reminder must be deleted.')

        current_time = datetime.now(timezone.utc)
        end_time = datetime.fromisoformat(reminder.end_time)
        remaining_time = end_time - current_time
        remaining_seconds = remaining_time.total_seconds()

        if remaining_seconds > 0:
            await asyncio.sleep(remaining_seconds)
            await channel.send(f'<@!{reminder.author_id}>, here is your {reminder.chosen_time} reminder: {reminder.message}')
        else:
            await channel.send(f'<@!{reminder.author_id}>, an error delayed your reminder: {reminder.message}')
            await channel.send(f'The reminder had been set for {end_time.year}-{end_time.month}-{end_time.day} at {end_time.hour}:{end_time.minute} UTC')

        await delete_reminder(reminder, logging.INFO)
    except Exception as e:
        await channel.send(f'<@!{reminder.author_id}>, your reminder was cancelled because of an error: {e}')
        if await bot.is_owner(reminder.author_id):
            await send_traceback(channel, e)
        await delete_reminder(reminder, logging.ERROR)
        raise e
            

async def delete_reminder(reminder, log_level: int = None):
    '''Removes one reminder from the database'''
    if log_level is not None:
        log_message = f'deleting {reminder}'
        reminders_logger.log(log_level, log_message)
    try:
        del db[f'reminder {reminder.author_id} {reminder.end_time}']
    except KeyError:
        # The reminder may have been deleted with the del-r command.
        log_message = f'could not find to delete: {reminder}'
        reminders_logger.log(logging.WARNING, log_message)


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['reminder', 'remindme'])
    @commands.cooldown(1, 15, BucketType.user)
    async def remind(self, ctx, chosen_time: str, *, message: str):
        '''Sends you a reminder, e.g. ;remind 1h30m iron socks
        
        The maximum time allowed is 24.85 days (see https://bugs.python.org/issue20493 for details).
        '''
        # Remove quotes, commas, and curly braces for security.
        message = message.replace('"', '').replace('\'', '').replace(',', '').replace('{', '').replace('}', '')
        try:
            seconds = self.parse_time(chosen_time)
            if seconds > 2147483:
                raise ValueError('The maximum time possible is 24.85d')
            await ctx.send(f'Reminder set! In {chosen_time}, I will remind you: {message}')
            reminder = await save_reminder(ctx, chosen_time, seconds, message)

            await asyncio.sleep(seconds)
            await ctx.send(f'{ctx.author.mention}, here is your {chosen_time} reminder: {message}')
            await delete_reminder(reminder, logging.INFO)
        except Exception as e:
            await ctx.send(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')
            if await ctx.bot.is_owner(ctx.author):
                await send_traceback(ctx, e)


    @commands.command(name='list-r', aliases=['list-reminders'])
    @commands.cooldown(1, 15, BucketType.user)
    async def list_reminders(self, ctx):
        '''Shows all of your reminders'''
        r_keys = db.prefix(f'reminder {ctx.author.id}')
        r_keys = sorted(r_keys)

        if not len(r_keys):
            await ctx.send('You have no saved reminders.')
        else:
            r_list = 'Here are your in-progress reminders:'
            for i, key in enumerate(r_keys):
                try:
                    reminder = await eval_reminder(db[key])
                    end_time = datetime.fromisoformat(reminder.end_time)
                    remaining = end_time - datetime.now(timezone.utc)

                    r_list += f'\n\n{i+1}. "{reminder.message}"\nduration: {reminder.chosen_time}\ntime remaining: {str(remaining)}'
                except SyntaxError as e:
                    log_message = f'deleting reminder {db[key]}'
                    reminders_logger.log(logging.ERROR, log_message)
                    del db[key]
                    await ctx.send(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')

            embed = discord.Embed(description=r_list)
            await ctx.send(embed=embed)


    @commands.command(name='del-r', aliases=['del-reminder', 'delete-reminder'])
    @commands.cooldown(1, 15, BucketType.user)
    async def del_r(self, ctx, index: int):
        '''Deletes a reminder by its index
        
        Currently, this only deletes a reminder from the database,
        not from the program. A deleted reminder will then only be
        cancelled if the bot is restarted.
        '''
        r_keys = db.prefix(f'reminder {ctx.author.id}')
        r_keys = sorted(r_keys)
        
        if not len(r_keys):
            await ctx.send('You have no saved reminders.')
        else:
            try:
                key = r_keys[index-1]
                reminder = await eval_reminder(db[key])
                await ctx.send(f'Reminder deleted: "{reminder.message}"')
                log_message = f'deleting reminder {db[key]}'
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
