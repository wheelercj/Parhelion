from cogs.utils.common import escape_json
from cogs.utils.io import unwrap_code_block
from cogs.utils.time import get_14_digit_datetime
from discord.ext import commands
from textwrap import dedent
import aiohttp
import asyncio
import discord
import io
import os
import sys


class Owner(commands.Cog):
    """Commands that can only be used by the bot owner."""

    def __init__(self, bot):
        self.bot = bot
        self.log_file_path = "bot.log"

    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner
        return True

    @commands.command()
    async def echo(self, ctx, *, message: str):
        """Repeats a message"""
        await ctx.send(message)

    @commands.command()
    async def leave(self, ctx, *, server_name: str = None):
        """Makes the bot leave a server

        If no server name is given, the bot will leave the current server.
        """
        if server_name is None:
            if ctx.guild is None:
                await ctx.send(
                    "This command can only be used without an argument in a server."
                )
            else:
                await ctx.send(f"Now leaving the server. Goodbye!")
                await ctx.guild.leave()
        else:
            for server in ctx.bot.guilds:
                if server_name == server.name:
                    await ctx.send(f"Now leaving server: {server.name}")
                    await server.leave()
                    return

            await ctx.send("Server not found.")

    @commands.command()
    async def restart(self, ctx):
        """Restarts the bot

        If the bot is running in an IDE, this may only shut the bot down instead.
        """
        await ctx.send("Restarting")
        python = sys.executable
        os.execl(python, python, *sys.argv)

    @commands.command(name="reset-error-reporting", aliases=["rer"])
    async def reset_error_reporting(self, ctx):
        """Allows dev mail about the next unexpected error"""
        self.bot.error_is_reported = False
        await ctx.send("`self.bot.error_is_reported` has been reset")

    @commands.command(
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
        await ctx.send(f"I am in the following servers:\n{servers}")

    @commands.command(name="server-id", aliases=["sid", "serverid"])
    async def get_server_id(self, ctx, *, server_name: str):
        """Gets the ID of a server by its name, if the bot can see the server

        May send multiple server IDs if multiple servers have the same name.
        """
        # This can be useful for when I need to update the database manually for servers that I'm not in.
        servers = self.bot.guilds
        sent = False
        for server in servers:
            if server_name == server.name:
                await ctx.send(server.id)
                sent = True
        if not sent:
            await ctx.send("No servers found with that name.")

    @commands.command()
    async def gist(self, ctx, *, content: str):
        """Creates a new private gist on GitHub and gives you the link

        You can use a code block and specify syntax. You cannot
        specify syntax without a triple-backtick code block. The
        default syntax is `txt`.
        """
        # This command currently creates the gists with my own GitHub
        # account, so it should not be made available to others.
        async with ctx.typing():
            syntax, content, _ = await unwrap_code_block(content)
            content = await escape_json(dedent(content))
            file_name = await get_14_digit_datetime()
            url = "https://api.github.com/gists"
            data = '{"public":false,"files":{"%s.%s":{"content":"%s"}}}' % (
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

    @commands.command(name="repeat", aliases=["rep", "reinvoke"])
    async def repeat_command(self, ctx, n: int = 1, skip: int = 0):
        """Repeats the last command you used"""
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

    @commands.command(aliases=["SQL"])
    async def sql(self, ctx, *, statement: str):
        """Execute a PostgreSQL statement"""
        _, statement, _ = await unwrap_code_block(statement)
        try:
            if statement.upper().startswith("SELECT"):
                ret = await self.bot.db.fetch(statement)
            else:
                ret = await self.bot.db.execute(statement)

            await ctx.send(ret)
            await ctx.message.add_reaction("✅")
        except Exception as e:
            await ctx.message.add_reaction("❗")
            await ctx.reply(f"PostgreSQL error: {e}")

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
        """
        if log_level >= self.bot.logger.level:
            self.bot.logger.log(log_level, f"(`log` command)[{message}]")
            await ctx.message.add_reaction("✅")
        else:
            await ctx.reply(f"❌ The bot's current log level is {self.bot.logger.level}")

    @log.command()
    async def level(self, ctx):
        """Shows the logger's current log level"""
        await ctx.reply(self.bot.logger.level)

    @log.command()
    async def send(self, ctx):
        """Sends a copy of the log file to Discord"""
        with open(self.log_file_path, "rb") as file:
            file_bytes = file.read()
            with io.BytesIO(file_bytes) as binary_stream:
                discord_file = discord.File(binary_stream, "log")
                await ctx.send(file=discord_file)

    @log.command()
    async def clear(self, ctx):
        """Deletes all the current contents of the log file

        If command logging is enabled, this command's use will be logged after
        the log is cleared.
        """
        with open(self.log_file_path, "w") as _:
            pass
        await ctx.message.add_reaction("✅")


def setup(bot):
    bot.add_cog(Owner(bot))
