import asyncio
import inspect
import io
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from textwrap import dedent
from typing import NamedTuple

import aiohttp  # https://pypi.org/project/aiohttp/
import discord  # https://pypi.org/project/discord.py/
import psutil  # https://pypi.org/project/psutil/
from discord import app_commands  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/

from cogs.utils.common import escape_json
from cogs.utils.io import dev_mail
from cogs.utils.io import send_traceback
from cogs.utils.io import unwrap_code_block
from cogs.utils.paginator import Paginator
from cogs.utils.time import get_14_digit_datetime


@dataclass
class CmdParam:
    """Holds info about a command parameter"""

    name: str
    desc: str
    cmd_name: str


class Owner(commands.Cog):
    """Commands that can only be used by the bot owner."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner
        return True

    @commands.hybrid_command(name="raise")
    async def raise_exception(self, ctx):
        """Raises an exception"""
        raise Exception("The `raise` command was used.")

    @commands.hybrid_command()
    async def echo(self, ctx, *, message: str):
        """Repeats a message

        Parameters
        ----------
        message: str
            The message to repeat.
        """
        await ctx.send(message)

    @commands.hybrid_command()
    async def leave(self, ctx, *, server_name: str | None = None):
        """Makes the bot leave a server

        If no server name is given, the bot will leave the current server.

        Parameters
        ----------
        server_name: str | None
            The name of the server to leave.
        """
        if server_name is None:
            if ctx.guild is None:
                await ctx.send(
                    "This command can only be used without an argument in a server."
                )
            else:
                await ctx.send("Now leaving the server. Goodbye!")
                await ctx.guild.leave()
        else:
            for server in ctx.bot.guilds:
                if server_name == server.name:
                    await ctx.send(f"Now leaving server: {server.name}")
                    await server.leave()
                    return
            await ctx.send("Server not found.")

    @commands.hybrid_command()
    async def restart(self, ctx):
        """Restarts the bot

        If the bot is running in an IDE, this may only shut the bot down instead.
        """
        await ctx.send("Restarting")
        python = sys.executable
        os.execl(python, python, *sys.argv)

    @commands.hybrid_command(name="reset-error-reporting", aliases=["rer"])
    async def reset_error_reporting(self, ctx):
        """Allows dev mail about the next unexpected error"""
        self.bot.error_is_reported = False
        await ctx.send("`self.bot.error_is_reported` has been reset", ephemeral=True)

    @commands.hybrid_command(
        name="list-servers",
        aliases=[
            "ls",
            "servers",
            "s",
            "sl",
            "listservers",
            "server-list",
            "serverlist",
        ],
    )
    async def list_servers(self, ctx):
        """Lists the names of all servers the bot is in"""
        servers = [server.name for server in self.bot.guilds]
        servers = "\n".join(servers)
        await ctx.send(f"I am in the following servers:\n{servers}", ephemeral=True)

    @commands.hybrid_command(name="server-id", aliases=["sid", "serverid"])
    async def get_server_id(self, ctx, *, server_name: str):
        """Gets the ID of a server by its name, if the bot can see the server

        May send multiple server IDs if multiple servers have the same name. This can be
        useful for when I need to update the database manually for servers that I'm not
        in.

        Parameters
        ----------
        server_name: str
            The name of the server to get the ID of.
        """
        servers = self.bot.guilds
        sent = False
        for server in servers:
            if server_name == server.name:
                await ctx.send(server.id, ephemeral=True)
                sent = True
        if not sent:
            await ctx.send("No servers found with that name.", ephemeral=True)

    @commands.hybrid_command(aliases=["utilization"])
    async def usage(self, ctx):
        """Shows the bot's resource utilization"""
        virtual_memory_: NamedTuple = psutil.virtual_memory()
        ram_percent = (
            (virtual_memory_.total - virtual_memory_.available)
            / virtual_memory_.total  # noqa: W503
            * 100  # noqa: W503
        )
        process = psutil.Process()
        memory_info_: NamedTuple = process.memory_info()
        ram_mb = memory_info_.rss / 1024 / 1024  # rss is short for "resident set size"
        await ctx.send(
            dedent(
                f"""\
                process RAM: {round(ram_mb, 2)} MB
                virtual RAM: {round(ram_percent, 2)}%
                CPU: {psutil.cpu_percent(interval=1)}%
                disk: {psutil.disk_usage('/').percent}%
                """
            )
        )

    @commands.hybrid_command()
    async def src(self, ctx, command_name: str):
        """Shows the bot's source code for a command

        CAUTION: this command uses the ``eval`` function. Currently, this command
        doesn't work with commands defined with a ``name`` parameter.

        Parameters
        ----------
        command_name: str
            The name of the command to view the source code of.
        """
        if command_name == "help":
            raise commands.BadArgument(
                "<https://github.com/wheelercj/Parhelion/search?q=Help>"
            )
        cog_name = None
        for cmd in self.bot.commands:
            if command_name == cmd.qualified_name:
                try:
                    cog_name = cmd.cog.qualified_name
                except AttributeError:
                    raise commands.BadArgument(f"`{command_name}` is not in a cog.")
                break
        if not cog_name:
            raise commands.BadArgument(f"`{command_name}` is not a command.")
        if cog_name == self.qualified_name:
            command_obj_name = f"{cog_name}.{command_name}"
        else:
            command_obj_name = f"self.bot.cogs['{cog_name}'].{command_name}"
        try:
            source_code = str(inspect.getsource(eval(command_obj_name).callback))
            await ctx.send(f"```py\n{source_code}```")
        except Exception as e:
            await ctx.send(e)

    @commands.hybrid_command()
    async def gist(self, ctx, *, content: str):
        """Creates a new private gist on GitHub and gives you the link

        You can use a code block and specify syntax. You cannot
        specify syntax without a triple-backtick code block. The
        default syntax is `txt`.

        Parameters
        ----------
        content: str
            The content the gist will have.
        """
        # This command currently creates the gists with my own GitHub
        # account, so it should not be made available to others.
        async with ctx.typing():
            syntax, content, _ = await unwrap_code_block(content)
            content = await escape_json(dedent(content))
            file_name = await get_14_digit_datetime()
            url = "https://api.github.com/gists"
            data = '{{"public":false,"files":{{"{}.{}":{{"content":"{}"}}}}}}'.format(
                file_name,
                syntax,
                content,
            )
            github_token = os.environ["MAIN_GITHUB_GISTS_TOKEN"]
            auth = aiohttp.BasicAuth("wheelercj", password=github_token)
            async with self.bot.session.post(url, data=data, auth=auth) as response:
                if not response.ok:
                    raise ValueError(
                        f"GitHub API request failed with status code {response.status}."
                    )
                json_text = await response.json()
                html_url = json_text["html_url"]
            await ctx.reply(f"New gist created at <{html_url}>")

    @commands.hybrid_command(name="repeat", aliases=["rep", "reinvoke"])
    async def repeat_command(self, ctx, n: int = 1, skip: int = 0):
        """Repeats the last command you used

        Parameters
        ----------
        n: int
            The number of times to repeat.
        skip: int
            The number of previously used commands to skip over for choosing which
            command to repeat.
        """
        previous = ctx.bot.previous_command_ctxs
        if not len(previous):
            await ctx.send("No previous commands saved.")
        else:
            for i in range(n + skip, skip, -1):
                try:
                    c = previous[-i]
                    if c.author.id != ctx.author.id:
                        raise ValueError
                    else:
                        await c.reinvoke()
                        await asyncio.sleep(n * 1.5)
                except IndexError:
                    pass

    @commands.hybrid_command()
    async def sql(self, ctx, *, statement: str):
        """Execute a PostgreSQL statement in the bot's database

        Parameters
        ----------
        statement: str
            The SQL statement to run in the bot's database.
        """
        _, statement, _ = await unwrap_code_block(statement)
        try:
            if statement.upper().startswith("SELECT"):
                ret = await self.bot.db.fetch(statement)
            else:
                ret = await self.bot.db.execute(statement)
            await ctx.send(ret, ephemeral=True)
            await ctx.message.add_reaction("✅")
        except Exception as e:
            await ctx.message.add_reaction("❗")
            await ctx.reply(f"PostgreSQL error: {e}", ephemeral=True)

    #####################
    # log command group #
    #####################

    @commands.group(invoke_without_command=True)
    async def log(self, ctx, log_level: int, *, message: str):
        """A group of commands for viewing and modifying the bot's logs

        Without a subcommand, this command writes a message into the log file
        if the logger is set to log_level or lower. Built-in definitions for
        what log_level can be:
            50 (CRITICAL)
            40 (ERROR)
            30 (WARNING)
            20 (INFO)
            10 (DEBUG)
            0 (NONSET)

        Parameters
        ----------
        log_level: int
            The importance level of the new log message.
        message: str
            The message to log.
        """
        if log_level >= self.bot.logger.level:
            self.bot.logger.log(log_level, f"(`log` command)[{message}]")
            await ctx.message.add_reaction("✅")
        else:
            log_level_message = await self.humanize_log_level(self.bot.logger.level)
            await ctx.reply(f"The bot's current log level is {log_level_message}")
            await ctx.message.add_reaction("❌")

    @log.command()
    async def level(self, ctx, new_level: int = None):
        """Sets or shows the logger's current log level"""
        if new_level is None:
            log_level_message = await self.humanize_log_level(self.bot.logger.level)
            await ctx.reply(log_level_message)
        else:
            self.bot.logger.setLevel(new_level)
            log_level_message = await self.humanize_log_level(self.bot.logger.level)
            await ctx.reply(f"Logging level set to {log_level_message}")

    @log.command()
    async def send(self, ctx):
        """DMs a copy of the log file to the bot's owner"""
        with open(self.bot.dev_settings.log_file_path, "rb") as file:
            file_bytes = file.read()
            with io.BytesIO(file_bytes) as binary_stream:
                discord_file = discord.File(binary_stream, "log")
                await dev_mail(self.bot, file=discord_file)
                await ctx.message.add_reaction("✅")

    @log.command()
    async def clear(self, ctx):
        """Deletes all the current contents of the log file

        If command logging is enabled, this command's use will be logged after
        the log is cleared.
        """
        with open(self.bot.dev_settings.log_file_path, "w") as _:
            pass
        await ctx.message.add_reaction("✅")

    async def humanize_log_level(self, log_level: int) -> str:
        """Changes the log level into a message with a description"""
        if log_level > 50:
            return f"{log_level} (critical < log level)"
        if log_level == 50:
            return f"{log_level} (critical)"
        if log_level > 40:
            return f"{log_level} (error < log level < critical)"
        if log_level == 40:
            return f"{log_level} (error)"
        if log_level > 30:
            return f"{log_level} (warning < log level < error)"
        if log_level == 30:
            return f"{log_level} (warning)"
        if log_level > 20:
            return f"{log_level} (info < log level < warning)"
        if log_level == 20:
            return f"{log_level} (info)"
        if log_level > 10:
            return f"{log_level} (debug < log level < info)"
        if log_level == 10:
            return f"{log_level} (debug)"
        if log_level > 0:
            return f"{log_level} (nonset < log level < debug)"
        if log_level == 0:
            return f"{log_level} (nonset)"
        return f"{log_level} (unknown log level)"

    ######################
    # sync command group #
    ######################

    @commands.group(invoke_without_command=True)
    async def sync(self, ctx):
        """A group of commands for syncing slash commands to Discord

        Without a subcommand, this command syncs all global commands globally. Sync when
        a slash command changes, unless the change made was only to its function's body
        or a library-side check.
        """
        # When syncing a bot's slash commands for the first time, use ``jishaku sync .``
        # first because it can give more feedback if something is wrong. Then use
        # ``sync gts`` to sync global commands to only the current server for testing.
        # Error code 30034 means the max number of daily application command creates has
        # been reached (200). See other error codes here:
        # https://discord.com/developers/docs/topics/opcodes-and-status-codes
        async with ctx.typing():
            try:
                synced = await ctx.bot.tree.sync()
            except Exception as e:
                await send_traceback(ctx, e)
            else:
                await ctx.send(f"Synced {len(synced)} global slash commands globally.")

    @sync.command()
    async def lint(self, ctx):
        """Detects potential problems that might prevent syncing app commands"""
        async with ctx.typing():
            messages: list[str] = []
            cmd_char_counts: dict[str, int] = defaultdict(int)
            app_cmd_count = 0
            for cmd in self.bot.commands:
                if not isinstance(
                    cmd,
                    (
                        commands.HybridCommand,
                        commands.HybridGroup,
                        app_commands.AppCommand,
                        app_commands.AppCommandGroup,
                    ),
                ):
                    continue
                app_cmd_count += 1
                new_messages, char_count = await self.lint_cmd(cmd)
                messages.extend(new_messages)
                cmd_char_counts[cmd.name] += char_count
            if app_cmd_count > 100:
                messages.append(
                    f"the bot has {app_cmd_count} slash commands (max: 100)"
                )
            for cmd_name, char_count in cmd_char_counts.items():
                if char_count > 4000:
                    messages.append(
                        f"commmand `{cmd_name}`'s combined name, description, parameter"
                        " descriptions, subcommand names, etc. character count is"
                        f" {char_count} (max: 4000)"
                    )
            if messages:
                paginator = Paginator(
                    "potential problems detected", messages, prefix="• "
                )
                await paginator.run(ctx)
            else:
                await ctx.send("No problems detected.")

    @sync.command()
    @commands.guild_only()
    async def server(self, ctx):
        """Syncs the current server's slash commands to the current server"""
        async with ctx.typing():
            try:
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            except Exception as e:
                await send_traceback(ctx, e)
            else:
                await ctx.send(
                    f"Synced {len(synced)} of this server's slash commands to this"
                    " server."
                )

    @sync.command(name="clear", aliases=["reset"])
    async def clear_(self, ctx):
        """Clears all global slash commands globally"""
        async with ctx.typing():
            ctx.bot.tree.clear_commands(guild=None)
            try:
                await ctx.bot.tree.sync()
            except Exception as e:
                await send_traceback(ctx, e)
            else:
                await ctx.send("Cleared all global slash commands globally.")

    @sync.command(name="resync-server", aliases=["rs"])
    @commands.guild_only()
    async def resync_server(self, ctx):
        """Clears and syncs the current server's slash commands to the current server"""
        async with ctx.typing():
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            try:
                await ctx.bot.tree.sync(guild=ctx.guild)
            except Exception as e:
                await send_traceback(ctx, e)
            else:
                await ctx.send("Cleared and resynced this server's slash commands.")

    @sync.command(name="global-to-server", aliases=["gts"])
    @commands.guild_only()
    async def global_to_server(self, ctx):
        """Syncs global slash commands to the current server"""
        async with ctx.typing():
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            try:
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            except Exception as e:
                await send_traceback(ctx, e)
            else:
                await ctx.send(
                    f"Synced {len(synced)} global slash commands to this server."
                )

    @sync.command()
    async def servers(self, ctx, servers: list[discord.Object]):
        """Syncs servers' slash commands to their respective servers

        Parameters
        ----------
        servers: list[discord.Object]
            The servers to sync slash commands to.
        """
        async with ctx.typing():
            server_count = 0
            try:
                for server_ in servers:
                    try:
                        await ctx.bot.tree.sync(guild=server_)
                    except discord.HTTPException:
                        pass
                    else:
                        server_count += 1
            except Exception as e:
                await send_traceback(ctx, e)
            else:
                await ctx.send(
                    f"Synced server slash commands to {server_count}/{len(servers)}"
                    " servers."
                )

    async def lint_cmd(self, cmd: app_commands.Command) -> tuple[list[str], int]:
        """Detects potential command problems for syncing app commands"""
        messages: list[str] = []
        char_count = len(cmd.name)
        messages.extend(await self.lint_cmd_name(cmd.name))
        if cmd.cog_name:
            char_count += len(cmd.cog_name)
        char_count += len(cmd.full_parent_name)
        char_count += len(cmd.help)
        if cmd.brief:
            char_count += len(cmd.brief)
            if len(cmd.brief) > 100:
                messages.append(
                    f"command `{cmd.name}`'s brief has length {len(cmd.brief)} (max:"
                    " 100)"
                )
        if cmd.description:
            char_count += len(cmd.description)
            if len(cmd.description) > 100:
                messages.append(
                    f"command `{cmd.name}`'s description has length"
                    f" {len(cmd.description)} (max: 100)"
                )
        char_count += len(cmd.qualified_name)
        if cmd.short_doc:
            char_count += len(cmd.short_doc)
        char_count += len(cmd.signature)
        if cmd.usage:
            char_count += len(cmd.usage)
        if hasattr(cmd, "parameters"):
            if len(cmd.parameters) > 25:
                messages.append(
                    f"command `{cmd.name}` has {cmd.parameters} parameters (max: 25)"
                )
            for param in cmd.parameters:
                new_messages, new_char_count = await self.lint_cmd_param(
                    param, cmd.name
                )
                messages.extend(new_messages)
                char_count += new_char_count
        if isinstance(cmd, commands.Group):
            for subcmd in cmd.commands:
                new_messages, new_char_count = await self.lint_cmd(subcmd)
                messages.extend(new_messages)
                char_count += new_char_count
        return messages, char_count

    async def lint_cmd_name(self, cmd_name: str) -> list[str]:
        """Detects potential command name problems for app commands"""
        messages: list[str] = []
        cmd_name_pattern = re.compile(r"^[-_\w\d]{1,32}$")
        if len(cmd_name) > 32:
            messages.append(
                f"command `{cmd_name}` name has length {len(cmd_name)} (max: 32)"
            )
        if not cmd_name_pattern.match(cmd_name):
            messages.append(
                f"command `{cmd_name}` name doesn't match regex"
                f" `{cmd_name_pattern.pattern}`"
            )
        for ch in cmd_name:
            if ch.isupper():
                messages.append(
                    f"command `{cmd_name}` name has 1 or more uppercase letters"
                )
                break
        return messages

    async def lint_cmd_param(
        self, param: app_commands.Parameter, cmd_name: str
    ) -> tuple[list[str], int]:
        """Detects potential command parameter problems for app commands"""
        messages: list[str] = []
        char_count = 0
        if param.type not in (
            discord.AppCommandOptionType.subcommand,
            discord.AppCommandOptionType.subcommand_group,
        ):
            char_count += len(param.display_name)
            if len(param.display_name) > 32:
                messages.append(
                    f"command `{cmd_name}`'s `{param.display_name}` parameter"
                    f" display_name has length {len(param.display_name)} (max: 32)"
                )
            if len(param.description) > 100:
                messages.append(
                    f"command `{cmd_name}`'s `{param.display_name}` parameter"
                    f" has description of length {len(param.description)} (max: 100)"
                )
        return messages, char_count


async def setup(bot):
    await bot.add_cog(Owner(bot))
