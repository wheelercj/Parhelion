# external imports
import asyncio
import asyncpg
from datetime import datetime, timedelta
import discord
from discord.ext import commands
from typing import List

# internal imports
from common import parse_time_message


'''
    CREATE TABLE IF NOT EXISTS reminders (
        id SERIAL PRIMARY KEY,
        author_id BIGINT NOT NULL,
        start_time TIMESTAMP NOT NULL,
        target_time TIMESTAMP NOT NULL,
        message VARCHAR(500) NOT NULL,
        is_dm BOOLEAN NOT NULL,
        server_id BIGINT,
        channel_id BIGINT,
        UNIQUE (author_id, start_time)
    )
'''


async def delete_reminder_from_db(bot, author_id: int, start_time: datetime) -> None:
    """Deletes a row of the reminder table"""
    await bot.db.execute('''
        DELETE FROM reminders
        WHERE author_id = $1
            AND start_time = $2;
        ''', author_id, start_time)


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(aliases=['reminder', 'remindme', 'timer'], invoke_without_command=True)
    async def remind(self, ctx, *, time_and_message: str):
        """Sends you a reminder
        
        Enter a time (or duration) in front of your reminder message. You can use natural language for this, such as `remind 2 days 3 hours continue project`. All times must be in UTC; use the `time` command to see the current time in UTC. The maximum reminder message length is 500 characters.
        """
        try:
            async with ctx.typing():
                start_time = ctx.message.created_at
                target_time, message = await parse_time_message(ctx, time_and_message)

                if target_time < start_time:
                    raise commands.BadArgument('Please choose a time in the future.')

                await self.save_reminder_to_db(ctx, start_time, target_time, message)

                await ctx.send(f'Reminder set! At {datetime.isoformat(target_time)}, I will remind you: {message}')

            seconds = (target_time - start_time).total_seconds()
            await asyncio.sleep(seconds)
            # The maximum reliable sleep duration is 24.85 days.
            # For details, see https://bugs.python.org/issue20493

            if datetime.utcnow() < target_time:
                raise ValueError('Reminder sleep failed.')

            await ctx.reply(f'{ctx.author.mention}, here is your reminder: {message}')
            await delete_reminder_from_db(self.bot, ctx.author.id, start_time)
        except Exception as e:
            await ctx.reply(f'{ctx.author.mention}, your reminder was canceled because of an error: {e}')


    @remind.command(name='list')
    async def list_reminders(self, ctx):
        """Shows all of your reminders"""
        reminder_records = await self.get_reminder_list(ctx.author.id)

        if not len(reminder_records):
            await ctx.send('You have no saved reminders.')
            return

        r_list = 'Here are your in-progress reminders:'
        for r in reminder_records:
            message = r['message']
            remaining = r['target_time'] - ctx.message.created_at
            remaining = await self.format_timedelta(remaining)

            r_list += f'\n\n{r["id"]}.) **in {remaining}**' \
                + f'\n{message}'

        embed = discord.Embed(description=r_list)
        await ctx.send(embed=embed)


    @remind.command(name='delete', aliases=['del'])
    async def delete_reminder(self, ctx, ID: int):
        """Deletes one of your reminders by its ID shown in the `remind list` command

        Currently, this only deletes a reminder from the database, not from the program. A deleted reminder will then only be canceled if the bot is restarted.
        """
        try:
            reminder_message = await self.bot.db.fetchval('''
                DELETE FROM reminders
                WHERE id = $1
                    AND author_id = $2
                RETURNING message
                ''', ID, ctx.author.id)
            await ctx.send(f'Reminder deleted: "{reminder_message}"')
        except Exception as e:
            await ctx.send(f'Error: {e}')


    @delete_reminder.error
    async def delete_reminder_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Error: missing argument. Use the reminder's ID shown in the `remind list` command.")
            await ctx.send(error)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Error: use the reminder's ID shown in the `remind list` command.")


    async def save_reminder_to_db(self, ctx, start_time: datetime, target_time: datetime, message: str) -> None:
        """Saves one reminder to the database"""
        if ctx.guild:
            is_dm = False
            server_id = ctx.guild.id
            channel_id = ctx.channel.id
        else:
            is_dm = True
            server_id = 0
            channel_id = 0

        await self.bot.db.execute('''
            INSERT INTO reminders
            (author_id, start_time, target_time, message, is_dm, server_id, channel_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7);
            ''', ctx.author.id, start_time, target_time, message, is_dm, server_id, channel_id)


    async def get_reminder_list(self, author_id: int) -> List[asyncpg.Record]:
        """Gets a list of reminder records belonging to one person
        
        Sorted by target time.
        """
        return await self.bot.db.fetch('''
            SELECT *
            FROM reminders
            WHERE author_id = $1
            ORDER BY target_time;
            ''', author_id)


    async def format_timedelta(self, remaining: timedelta) -> str:
        """Makes an easy-to-read timedelta string
        
        Some precision may be lost.
        """
        output = ''
        if remaining.days > 1:
            output = f'{remaining.days} days '
        elif remaining.days == 1:
            output = '1 day '

        hours = remaining.seconds // 3600
        if hours > 1:
            output += f'{hours} hours '
        elif hours == 1:
            output += '1 hour '

        minutes = remaining.seconds % 3600 // 60
        if minutes > 1:
            output += f'{minutes} minutes '
        elif minutes == 1:
            output += '1 minute '

        if len(output) >= 25:
            return output

        seconds = remaining.seconds % 3600 % 60
        if seconds > 1:
            output += f'{seconds} seconds'
        elif seconds == 1:
            output += '1 second'

        return output


def setup(bot):
    bot.add_cog(Reminders(bot))
