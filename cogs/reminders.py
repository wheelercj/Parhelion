# external imports
import asyncpg
from datetime import datetime
import discord
from discord.ext import commands

# internal imports
from cogs.utils.io import safe_send
from cogs.utils.time import create_long_datetime_stamp, create_relative_timestamp, parse_time_message
from cogs.utils.paginator import Paginator
from cogs.utils.common import plural


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


class RunningReminderInfo():
    def __init__(self, target_time: datetime, id: int):
        self.target_time = target_time
        self.id = id


class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task = self.bot.loop.create_task(self.run_reminders())
        self.running_reminder_info: RunningReminderInfo = None


    def cog_unload(self):
        self._task.cancel()


    async def run_reminders(self):
        """A task that finds the next reminder time, waits for that time, and sends"""
        await self.bot.wait_until_ready()
        try:
            while not self.bot.is_closed():
                target_time, id, destination, author_id, message = await self.get_next_reminder_info()
                if target_time is None:
                    self.running_reminder_info = None
                    self._task.cancel()
                    return
                self.running_reminder_info = RunningReminderInfo(target_time, id)

                await discord.utils.sleep_until(target_time)

                await destination.send(f'<@!{author_id}>, here is your reminder: {message}')
                await self.delete_reminder_from_db(id)
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError) as error:
            print(f'  run_reminders {error = }')
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.run_reminders())


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
            target_time, message = await parse_time_message(ctx, time_and_message, 'UTC')
            if target_time < start_time:
                raise commands.BadArgument('Please choose a time in the future.')

            await self.save_reminder_to_db(ctx, start_time, target_time, message)
            if self.running_reminder_info is None:
                self._task = self.bot.loop.create_task(self.run_reminders())
            elif target_time < self.running_reminder_info.target_time:
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.run_reminders())

            relative_timestamp = await create_relative_timestamp(target_time)
            long_datetime_stamp = await create_long_datetime_stamp(target_time)
            await ctx.send(f'Reminder set! {relative_timestamp} ({long_datetime_stamp})' \
                ' I will remind you: {message}')


    @remind.command(name='create', aliases=['c'])
    async def create_reminder(self, ctx, *, time_and_message: str):
        """Sends you a reminder; this command is an alias for `remind`"""
        remind_command = self.bot.get_command('remind')
        await ctx.invoke(remind_command, time_and_message=time_and_message)


    @remind.command(name='list', aliases=['l'])
    async def list_reminders(self, ctx):
        """Shows all of your reminders"""
        records = await self.bot.db.fetch('''
            SELECT *
            FROM reminders
            WHERE author_id = $1
            ORDER BY target_time;
            ''', ctx.author.id)

        if not len(records):
            await ctx.send('You have no saved reminders.')
            return

        r_list = []
        for r in records:
            message = r['message']
            relative_timestamp = await create_relative_timestamp(r['target_time'])
            long_datetime_stamp = await create_long_datetime_stamp(r['target_time'])
            r_list.append(f'{r["id"]}.) **{relative_timestamp}** ({long_datetime_stamp})\n{message}')

        title = f'You currently have {plural(len(records), "reminder||s")}:'
        paginator = Paginator(title=title, embed=True, timeout=90, entries=r_list, length=10)
        await paginator.start(ctx)


    @remind.command(name='delete', aliases=['del'])
    async def delete_reminder(self, ctx, ID: int):
        """Deletes one of your reminders by its ID shown with the `remind list` command

        Currently, this only deletes a reminder from the database, not from the program. A deleted reminder will then only be canceled if the bot is restarted.
        """
        try:
            record = await self.bot.db.fetchrow('''
                DELETE FROM reminders
                WHERE id = $1
                    AND author_id = $2
                RETURNING *;
                ''', ID, ctx.author.id)
            if self.running_reminder_info is not None \
                    and record['id'] == self.running_reminder_info.id:
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.run_reminders())
            reminder_message = record['message']
            await ctx.send(f'Reminder deleted: "{reminder_message}"')
        except Exception as e:
            await safe_send(ctx, f'Error: {e}', protect_postgres_host=True)


    @delete_reminder.error
    async def delete_reminder_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Error: missing argument. Use the reminder's ID shown in the `remind list` command.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Error: use the reminder's ID shown in the `remind list` command.")


    @remind.command(name='delete-all', aliases=['deleteall'])
    async def delete_all_reminders(self, ctx):
        """Deletes all of your reminders

        Currently, this only deletes reminders from the database, not from the program. Deleted reminders will then only be canceled if the bot is restarted.
        """
        try:
            records = await self.bot.db.fetch('''
                DELETE FROM reminders
                WHERE author_id = $1
                RETURNING *;
                ''', ctx.author.id)
            for r in records:
                if self.running_reminder_info is not None \
                        and r['id'] == self.running_reminder_info.id:
                    self._task.cancel()
                    self._task = self.bot.loop.create_task(self.run_reminders())
                    break
        except Exception as e:
            await safe_send(ctx, f'Error: {e}', protect_postgres_host=True)
        else:
            await ctx.send('All of your reminders have been deleted.')


    @remind.command(name='mod-delete', aliases=['mdel', 'moddelete'])
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
                RETURNING *;
                ''', reminder_ID, ctx.guild.id)
            if self.running_reminder_info is not None \
                    and record['id'] == self.running_reminder_info.id:
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.run_reminders())
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


    async def get_next_reminder_info(self):
        """Gets from the database the info for the nearest (in time) reminder task

        Returns (target_time, id, destination, author_id, message).
        If there is no next daily quote, this function returns (None, None, None, None, None).
        """
        r = await self.bot.db.fetchrow('''
            SELECT *
            FROM reminders
            ORDER BY target_time
            LIMIT 1;
            ''')
        if r is None:
            return None, None, None, None, None

        target_time = r['target_time']
        author_id = r['author_id']
        id = r['id']
        message = r['message']
        if r['is_dm']:
            destination = self.bot.get_user(r['author_id'])
        else:
            server = self.bot.get_guild(r['server_id'])
            destination = server.get_channel(r['channel_id'])

        return target_time, id, destination, author_id, message


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


    async def delete_reminder_from_db(self, reminder_id: int) -> None:
        """Deletes a row of the reminder table"""
        await self.bot.db.execute('''
            DELETE FROM reminders
            WHERE id = $1;
            ''', reminder_id)


def setup(bot):
    bot.add_cog(Reminders(bot))
