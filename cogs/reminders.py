# external imports
import asyncio
import asyncpg
from datetime import datetime
import discord
from discord.ext import commands
from typing import List

# internal imports
from common import send_traceback, parse_time_message


'''
    CREATE TABLE IF NOT EXISTS reminders (
        author_id BIGINT NOT NULL,
        start_time TIMESTAMP NOT NULL,
        target_time TIMESTAMP NOT NULL,
        message VARCHAR(300) NOT NULL,
        is_dm BOOLEAN NOT NULL,
        guild_id BIGINT,
        channel_id BIGINT,
        PRIMARY KEY (author_id, start_time)
    )
'''


async def save_reminder_to_db(ctx, bot, start_time: datetime, target_time: datetime, message: str) -> None:
    """Saves one reminder to the database"""
    if ctx.guild:
        is_dm = False
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
    else:
        is_dm = True
        guild_id = 0
        channel_id = 0

    await bot.db.execute('''
        INSERT INTO reminders
        (author_id, start_time, target_time, message, is_dm, guild_id, channel_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7);
        ''', ctx.author.id, start_time, target_time, message, is_dm, guild_id, channel_id)


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(aliases=['reminder', 'remindme', 'timer'], invoke_without_command=True)
    async def remind(self, ctx, *, time_and_message: str):
        """Sends you a reminder
        
        Enter a time (or duration) in front of your reminder message. All times must be in UTC; use the `time` command to see the current time in UTC.
        """
        await ctx.send('the remind commands are being rewritten right now and are not working properly')
        try:
            async with ctx.typing():
                start_time = ctx.message.created_at
                target_time, message = await parse_time_message(ctx, time_and_message)

                if target_time < start_time:
                    raise commands.BadArgument('Please choose a time in the future.')

                await save_reminder_to_db(ctx, self.bot, start_time, target_time, message)

                await ctx.reply(f'Reminder set! At {datetime.isoformat(target_time)}, I will remind you: {message}')

            seconds = (target_time - start_time).total_seconds()
            await asyncio.sleep(seconds)
            # The maximum reliable sleep duration is 24.85 days.
            # For details, see https://bugs.python.org/issue20493

            if datetime.utcnow() < target_time:
                raise ValueError('Reminder sleep failed.')

            await ctx.reply(f'{ctx.author.mention}, here is your reminder: {message}')
            await self.delete_reminder_from_db(ctx.author.id, start_time)
        except Exception as e:
            await ctx.reply(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')
            if await ctx.bot.is_owner(ctx.author):
                await send_traceback(ctx, e)


    async def delete_reminder_from_db(self, author_id: int, start_time: datetime) -> None:
        """Deletes a row of the reminder table"""
        await self.bot.db.execute('''
            DELETE FROM reminders
            WHERE author_id = $1,
                AND start_time = $2;
            ''', author_id, start_time)
            

    async def get_reminder_list(self, author_id: int) -> List[asyncpg.Record]:
        """Gets a list of reminder records belonging to one person"""
        return self.bot.db.fetch('''
            SELECT *
            FROM reminders
            WHERE author_id = $1
            ORDER BY target_time;
            ''', author_id)


    @remind.command(name='list')
    async def list_reminders(self, ctx):
        """Shows all of your reminders"""
        reminders = await self.get_reminder_list(ctx.author.id)

        if reminders is None:
            await ctx.send('You have no saved reminders.')
            return

        r_list = 'Here are your in-progress reminders:'
        for i, r in enumerate(reminders):
            try:
                remaining = r['target_time'] - datetime.utcnow()
                message = r['message']
                target_time = r['target_time']

                r_list += f'\n\n{i+1}. "{message}"' \
                    + f'\ntarget time: {target_time}' \
                    + f'\ntime remaining: {str(remaining)}'
            except Exception as e:
                await self.delete_reminder_from_db(ctx.author.id, r['start_time'])
                await ctx.send(f'{ctx.author.mention}, your reminder was cancelled because of an error: {e}')

        embed = discord.Embed(description=r_list)
        await ctx.send(embed=embed)


    @remind.command(name='delete', aliases=['del'])
    async def delete_reminder(self, ctx, index: int):
        """Deletes a reminder by its index shown in the `remind list` command
        
        Currently, this only deletes a reminder from the database, not from the program. A deleted reminder will then only be cancelled if the bot is restarted.
        """
        try:
            reminders = await self.get_reminder_list(ctx.author.id)
            reminder_message = reminders[index-1]['message']
            await self.delete_reminder_from_db(ctx.author.id, reminders[index-1]['start_time'])
            await ctx.send(f'Reminder deleted: "{reminder_message}"')
        except KeyError:
            await ctx.send('Reminder not found.')


    @delete_reminder.error
    async def delete_reminder_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Error: missing argument. Use the reminder's index number shown in the `remind list` command.")
            await ctx.send(error)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Error: use the reminder's index number shown in the `remind list` command.")


def setup(bot):
    bot.add_cog(Reminders(bot))
