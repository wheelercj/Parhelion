from datetime import datetime
from datetime import timezone

import asyncpg  # https://pypi.org/project/asyncpg/
import discord  # https://pypi.org/project/discord.py/
from discord.abc import Messageable  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/

from cogs.utils.common import block_nsfw_channels
from cogs.utils.common import plural
from cogs.utils.io import LinkButton
from cogs.utils.io import safe_send
from cogs.utils.paginator import Paginator
from cogs.utils.time import create_long_datetime_stamp
from cogs.utils.time import create_relative_timestamp
from cogs.utils.time import parse_time_message


class RunningReminderInfo:
    def __init__(self, target_time: datetime, id: int):
        self.target_time = target_time
        self.id = id


class Reminders(commands.Cog):
    """Send yourself messages at specific times."""

    def __init__(self, bot):
        self.bot = bot
        self._task = self.bot.loop.create_task(self.run_reminders())
        self.running_reminder_info: RunningReminderInfo = None
        self.reminder_ownership_limit = 20

    def cog_unload(self):
        self._task.cancel()

    async def create_table_if_not_exists(self) -> None:
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id SERIAL PRIMARY KEY,
                author_id BIGINT NOT NULL,
                start_time TIMESTAMPTZ NOT NULL,
                target_time TIMESTAMPTZ NOT NULL,
                message VARCHAR(500) NOT NULL,
                is_dm BOOLEAN NOT NULL,
                server_id BIGINT,
                channel_id BIGINT,
                jump_url TEXT,  -- The URL to the message that created the reminder.
                UNIQUE (author_id, start_time)
            );
            """
        )

    async def run_reminders(self, jump_url: str = None) -> None:
        """A task that finds the next reminder time, waits for that time, and sends

        Parameters
        ----------
        jump_url: Optional[str]
            The jump URL to the reminder that should be run first. This may be required
            to avoid race conditions if the reminder that should run first was just
            created.
        """
        await self.bot.wait_until_ready()
        await self.create_table_if_not_exists()
        try:
            while not self.bot.is_closed():
                (
                    start_time,
                    target_time,
                    id,
                    destination,
                    author_id,
                    message,
                    jump_url_,
                ) = await self.get_next_reminder_info()
                if jump_url is None:
                    jump_url = jump_url_
                if target_time is None:
                    self.running_reminder_info = None
                    self._task.cancel()
                    return
                self.running_reminder_info = RunningReminderInfo(target_time, id)
                await discord.utils.sleep_until(target_time)
                relative_start = await create_relative_timestamp(start_time)
                await destination.send(
                    f"<@!{author_id}> {relative_start}: {message}",
                    view=LinkButton("see original message", jump_url),
                )
                jump_url = None
                await self.delete_reminder_from_db(id)
        except (
            OSError,
            discord.ConnectionClosed,
            asyncpg.PostgresConnectionError,
        ) as error:
            print(f"  run_reminders {error = }")
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.run_reminders())

    @commands.hybrid_group(
        aliases=["r", "reminder", "remindme", "timer"], invoke_without_command=True
    )
    async def remind(self, ctx, *, time_and_message: str):
        """Sends you a reminder

        If you have not chosen a timezone with the `timezone set` command, UTC will be
        assumed.

        Parameters
        ----------
        time_and_message: str
            A description of when you want to receive the reminder followed by what you
            want to be reminded of.
        """
        await block_nsfw_channels(ctx.channel)
        await self.check_reminder_ownership_permission(ctx.author.id)
        async with ctx.typing():
            start_time = datetime.now(timezone.utc)
            target_time, message = await parse_time_message(ctx, time_and_message)
            if target_time < start_time:
                raise commands.BadArgument("Please choose a time in the future.")
            id_ = await self.save_reminder_to_db(ctx, start_time, target_time, message)
            relative_timestamp = await create_relative_timestamp(target_time)
            long_datetime_stamp = await create_long_datetime_stamp(target_time)
            msg = await ctx.send(
                f"Reminder set! {relative_timestamp} ({long_datetime_stamp})"
                f" I will remind you: {message}"
            )
            await self.save_jump_url(msg.jump_url, id_)
            if self.running_reminder_info is None:
                self._task = self.bot.loop.create_task(self.run_reminders(msg.jump_url))
            elif target_time < self.running_reminder_info.target_time:
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.run_reminders(msg.jump_url))

    @remind.command(name="create", aliases=["c"])
    async def create_reminder(self, ctx, *, time_and_message: str):
        """Sends you a reminder

        Parameters
        ----------
        time_and_message: str
            A description of when you want to receive the reminder followed by what you
            want to be reminded of.
        """
        remind_command = self.bot.get_command("remind")
        await ctx.invoke(remind_command, time_and_message=time_and_message)

    @remind.command(name="list", aliases=["l"])
    async def list_reminders(self, ctx):
        """Shows all of your reminders"""
        records = await self.bot.db.fetch(
            """
            SELECT *
            FROM reminders
            WHERE author_id = $1
            ORDER BY target_time;
            """,
            ctx.author.id,
        )
        if not len(records):
            raise commands.UserInputError("You have no saved reminders.")
        r_list = []
        for r in records:
            message = r["message"]
            relative_timestamp = await create_relative_timestamp(r["target_time"])
            long_datetime_stamp = await create_long_datetime_stamp(r["target_time"])
            r_list.append(
                f'[**{r["id"]}**.]({r["jump_url"]}) **{relative_timestamp}**'
                f" ({long_datetime_stamp})\n{message}"
            )
        title = f'You currently have {plural(len(records), "reminder||s")}:'
        paginator = Paginator(title=title, entries=r_list, length=10)
        await paginator.run(ctx)

    @remind.command(name="delete", aliases=["del"])
    async def delete_reminder(self, ctx, id: int):
        """Deletes a reminder by its ID shown with the `remind list` command

        Parameters
        ----------
        id: int
            The ID of the reminder to delete. Reminder IDs can be seen with the `remind
            list` command.
        """
        try:
            record = await self.bot.db.fetchrow(
                """
                DELETE FROM reminders
                WHERE id = $1
                    AND author_id = $2
                RETURNING *;
                """,
                id,
                ctx.author.id,
            )
            if (
                self.running_reminder_info is not None
                and record["id"] == self.running_reminder_info.id  # noqa: W503
            ):
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.run_reminders())
            reminder_message = record["message"]
            await ctx.send(f'Reminder deleted: "{reminder_message}"')
        except Exception as e:
            await safe_send(
                ctx, f"Error: {e}", protect_postgres_host=True, ephemeral=True
            )

    @delete_reminder.error
    async def delete_reminder_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "Error: missing argument. Use the reminder's ID shown in the `remind"
                " list` command.",
                ephemeral=True,
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                "Error: use the reminder's ID shown in the `remind list` command.",
                ephemeral=True,
            )

    @remind.command(name="delete-all", aliases=["deleteall"])
    async def delete_all_reminders(self, ctx):
        """Deletes all of your reminders"""
        try:
            records = await self.bot.db.fetch(
                """
                DELETE FROM reminders
                WHERE author_id = $1
                RETURNING *;
                """,
                ctx.author.id,
            )
            for r in records:
                if (
                    self.running_reminder_info is not None
                    and r["id"] == self.running_reminder_info.id  # noqa: W503
                ):
                    self._task.cancel()
                    self._task = self.bot.loop.create_task(self.run_reminders())
                    break
        except Exception as e:
            await safe_send(
                ctx, f"Error: {e}", protect_postgres_host=True, ephemeral=True
            )
        else:
            await ctx.send("All of your reminders have been deleted.")

    @remind.command(name="mod-delete", aliases=["mdel", "moddelete"])
    @commands.has_guild_permissions(manage_messages=True)
    async def mod_delete_reminder(self, ctx, reminder_id: int):
        """Delete's one of anyone's reminders made on this server

        Parameters
        ----------
        reminder_id: int
            The ID of the reminder to delete.
        """
        try:
            record = await self.bot.db.fetch(
                """
                DELETE FROM reminders
                WHERE id = $1
                    AND server_id = $2
                RETURNING *;
                """,
                reminder_id,
                ctx.guild.id,
            )
            if (
                self.running_reminder_info is not None
                and record["id"] == self.running_reminder_info.id  # noqa: W503
            ):
                self._task.cancel()
                self._task = self.bot.loop.create_task(self.run_reminders())
        except Exception as e:
            await safe_send(
                ctx, f"Error: {e}", protect_postgres_host=True, ephemeral=True
            )
        else:
            message = record["message"]
            author = ctx.guild.get_member(record["author"])
            if author is None:
                author = record["author"]
            else:
                author = author.display_name
            await ctx.send(
                f"Successfully deleted the reminder {message} that was created by"
                f" {author}"
            )

    async def check_reminder_ownership_permission(self, author_id: int) -> None:
        """Raises commands.UserInputError if author has >= the max # of reminders"""
        members_reminder_count = await self.count_authors_reminders(author_id)
        if (
            members_reminder_count >= self.reminder_ownership_limit
            and self.bot.owner_id != author_id  # noqa: W503
        ):
            raise commands.UserInputError(
                "The current limit to how many reminders each person can have is"
                f" {self.reminder_ownership_limit}."
            )

    async def count_authors_reminders(self, author_id: int) -> int:
        """Counts the author's total reminders"""
        records = await self.bot.db.fetch(
            """
            SELECT *
            FROM reminders
            WHERE author_id = $1
            """,
            author_id,
        )
        return len(records)

    async def get_next_reminder_info(
        self,
    ) -> tuple[datetime, datetime, int, Messageable, int, str, str]:
        """Gets from the database the info for the nearest (in time) reminder task

        Returns (start_time, target_time, id, destination, author_id, message,
        jump_url). If there is no next daily quote, this function returns (None, None,
        None, None, None, None, None).
        """
        r = await self.bot.db.fetchrow(
            """
            SELECT *
            FROM reminders
            ORDER BY target_time
            LIMIT 1;
            """
        )
        if r is None:
            return None, None, None, None, None, None, None
        start_time = r["start_time"]
        target_time = r["target_time"]
        author_id = r["author_id"]
        id = r["id"]
        message = r["message"]
        jump_url = r["jump_url"]
        if r["is_dm"]:
            destination = self.bot.get_user(r["author_id"])
        else:
            server = self.bot.get_guild(r["server_id"])
            destination = server.get_channel(r["channel_id"])
        return start_time, target_time, id, destination, author_id, message, jump_url

    async def save_reminder_to_db(
        self, ctx, start_time: datetime, target_time: datetime, message: str
    ) -> int:
        """Saves one reminder to the database"""
        if ctx.guild:
            is_dm = False
            server_id = ctx.guild.id
            channel_id = ctx.channel.id
        else:
            is_dm = True
            server_id = 0
            channel_id = 0
        return await self.bot.db.fetchval(
            """
            INSERT INTO reminders
            (author_id, start_time, target_time, message, is_dm, server_id, channel_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id;
            """,
            ctx.author.id,
            start_time,
            target_time,
            message,
            is_dm,
            server_id,
            channel_id,
        )

    async def save_jump_url(self, jump_url: str, id_: int) -> None:
        """Saves the jump URL for a reminder already in the database"""
        await self.bot.db.execute(
            """
            UPDATE reminders
            SET jump_url = $1
            WHERE id = $2;
            """,
            jump_url,
            id_,
        )

    async def delete_reminder_from_db(self, reminder_id: int) -> None:
        """Deletes a row of the reminder table"""
        await self.bot.db.execute(
            """
            DELETE FROM reminders
            WHERE id = $1;
            """,
            reminder_id,
        )


async def setup(bot):
    await bot.add_cog(Reminders(bot))
