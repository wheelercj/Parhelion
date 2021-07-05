# external imports
from replit import db
import re
import asyncio
from datetime import datetime
import discord
from discord.ext import commands

# internal imports
from common import send_traceback, create_task_key, parse_time_message
from task import Reminder
from tasks import save_task, delete_task, eval_task


async def save_reminder(ctx, start_time: datetime, target_time: datetime, duration: str, seconds: int, message: str) -> Reminder:
    """Saves one reminder to the database"""
    target_time = target_time.isoformat()
    reminder = await save_task(ctx, 'reminder', target_time, duration, Reminder, message)
    
    return reminder


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['add-r', 'reminder', 'remindme'])
    async def remind(self, ctx, *, time_and_message: str):
        """Sends you a reminder
        
        Enter the time (or duration) in front of the message.
        The maximum reliable duration is 24.85 days (see https://bugs.python.org/issue20493 for details).
        """
        # Remove some chars for security and simplicity.
        to_remove = ['"', '\'', ',', '\\', '{', '}']
        for char in to_remove:
            time_and_message.replace(char, '')

        try:
            start_time = ctx.message.created_at
            target_time, message = await parse_time_message(ctx, time_and_message)
            seconds = (target_time - start_time).total_seconds()

            reminder = await save_reminder(ctx, start_time, target_time, '', seconds, message)
            await ctx.reply(f'Reminder set! At {datetime.isoformat(target_time)}, I will remind you: {message}')

            await asyncio.sleep(seconds)

            if datetime.now() < target_time:
                raise ValueError('Reminder sleep failed.')

            await ctx.reply(f'{ctx.author.mention}, here is your reminder: {message}')
            await delete_task(task=reminder)
        except Exception as e:
            await ctx.reply(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')
            if await ctx.bot.is_owner(ctx.author):
                await send_traceback(ctx, e)


    @commands.command(name='list-r', aliases=['list-reminders'])
    async def list_reminders(self, ctx):
        """Shows all of your reminders"""
        task_key_prefix = await create_task_key('reminder', ctx.author.id)
        r_keys = db.prefix(task_key_prefix)
        r_keys = sorted(r_keys)

        if not len(r_keys):
            await ctx.send('You have no saved reminders.')
        else:
            r_list = 'Here are your in-progress reminders:'
            for i, key in enumerate(r_keys):
                try:
                    reminder = await eval_task(db[key])
                    target_time = datetime.fromisoformat(reminder.target_time)
                    remaining = target_time - datetime.now()
                    if str(remaining).startswith('-'):
                        raise ValueError('Negative time remaining.')

                    r_list += f'\n\n{i+1}. "{reminder.message}"\nduration: {reminder.duration}\ntime remaining: {str(remaining)}'
                except Exception as e:
                    del db[key]
                    await ctx.send(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')

            embed = discord.Embed(description=r_list)
            await ctx.send(embed=embed)


    @commands.command(name='del-r', aliases=['del-reminder', 'delete-reminder'])
    async def del_r(self, ctx, index: int):
        """Deletes a reminder by its index
        
        Currently, this only deletes a reminder from the
        database, not from the program. A deleted reminder will then only be cancelled if the bot is restarted.
        """
        task_key_prefix = await create_task_key('reminder', ctx.author.id)
        r_keys = db.prefix(task_key_prefix)
        r_keys = sorted(r_keys)
        
        if not len(r_keys):
            await ctx.send('You have no saved reminders.')
        else:
            try:
                key = r_keys[index-1]
                reminder = await eval_task(db[key])
                await ctx.send(f'Reminder deleted: "{reminder.message}"')
                del db[key]
            except KeyError:
                await ctx.send('Reminder not found.')

        
    @del_r.error
    async def del_r_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Error: missing argument. Use the reminder's index number shown in the list-r command.")
            await ctx.send(error)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Error: use the reminder's index number shown in the list-r command.")


def setup(bot):
    bot.add_cog(Reminders(bot))
