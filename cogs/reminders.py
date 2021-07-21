# external imports
import asyncio
from datetime import datetime
import discord
from discord.ext import commands

# internal imports
from common import parse_time_message, format_timestamp, s, safe_send


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


    @commands.group(aliases=['r', 'reminder', 'remindme', 'timer'], invoke_without_command=True)
    async def remind(self, ctx, *, time_and_message: str):
        """Sends you a reminder
        
        Enter a time (or duration) in front of your reminder message. You can use natural language for this, such as
        `remind friday at noon buy oranges`
        or
        `remind in 2 days 3 hours continue the project`
        or many more options. All times must be in UTC, and you can use the `time` command to see the current time in UTC.
        """
        if await self.count_authors_reminders(ctx) > 15:
            await ctx.send('The current limit to how many reminders each person can have is 15. This will increase in the future.')
            return

        async with ctx.typing():
            start_time = ctx.message.created_at
            target_time, message = await parse_time_message(ctx, time_and_message)

            if target_time < start_time:
                raise commands.BadArgument('Please choose a time in the future.')

            await self.save_reminder_to_db(ctx, start_time, target_time, message)
            await ctx.send(f'Reminder set! {await format_timestamp(target_time)} I will remind you: {message}')

        seconds = (target_time - start_time).total_seconds()
        await asyncio.sleep(seconds)
        # The maximum reliable sleep duration is 24.85 days.
        # For details, see https://bugs.python.org/issue20493

        if datetime.utcnow() < target_time:
            raise ValueError('Reminder sleep failed.')

        await ctx.reply(f'{ctx.author.mention}, here is your reminder: {message}')
        await delete_reminder_from_db(self.bot, ctx.author.id, start_time)


    @remind.command(name='create')
    async def create_reminder(self, ctx, *, time_and_message: str):
        """Sends you a reminder; this command is an alias for `remind`"""
        remind_command = self.bot.get_command('remind')
        await ctx.invoke(remind_command, time_and_message=time_and_message)


    @remind.command(name='list')
    async def list_reminders(self, ctx):
        """Shows all of your reminders"""
        reminder_records = await self.bot.db.fetch('''
            SELECT *
            FROM reminders
            WHERE author_id = $1
            ORDER BY target_time
            LIMIT 10;
            ''', ctx.author.id)

        if not len(reminder_records):
            await ctx.send('You have no saved reminders.')
            return

        n = len(reminder_records)
        if n < 10:
            r_list = f'You currently have {s(n, "reminder")}:'
        elif n == 10:
            r_list = 'Here are your first 10 reminders:'
        for r in reminder_records:
            message = r['message']
            remaining = await format_timestamp(r['target_time'])

            r_list += f'\n\n{r["id"]}.) **{remaining}**' \
                + f'\n{message}'

        embed = discord.Embed(description=r_list)
        await ctx.send(embed=embed)


    @remind.command(name='delete')
    async def delete_reminder(self, ctx, ID: int):
        """Deletes one of your reminders by its ID shown with the `remind list` command

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
            await safe_send(ctx, f'Error: {e}', protect_postgres_host=True)


    @delete_reminder.error
    async def delete_reminder_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Error: missing argument. Use the reminder's ID shown in the `remind list` command.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Error: use the reminder's ID shown in the `remind list` command.")


    @remind.command(name='mod-delete', aliases=['moddelete'])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_reminder(self, ctx, reminder_ID: int):
        """Delete's one of anyone's reminders made on this server
        
        Currently, this only deletes a reminder from the database, not from the program. A deleted reminder will then only be canceled if the bot is restarted.
        """
        try:
            record = await self.bot.db.fetch('''
                DELETE FROM reminders
                WHERE id = $1
                    AND server_id = $2
                RETURNING *
                ''', reminder_ID, ctx.guild.id)
        except Exception as e:
            await safe_send(ctx, f'Error: {e}', protect_postgres_host=True)
        else:
            message = record['message']
            author = ctx.guild.get_member(record['author'])
            if author is None:
                author = record['author']
            else:
                author = author.display_name
            await ctx.send(f'Successfully deleted the reminder {message} that was created by {author}')


    async def count_authors_reminders(self, ctx) -> int:
        """Counts ctx.author's total reminders"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM reminders
            WHERE author_id = $1
            ''', ctx.author.id)

        return len(records)


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


def setup(bot):
    bot.add_cog(Reminders(bot))
