# external imports
import os
from discord.ext import commands
import asyncio
import aiohttp
from textwrap import dedent

# internal imports
from cogs.utilities.time import get_14_digit_datetime
from common import unwrap_code_block, escape_json


class Owner(commands.Cog):
    """Commands that can only be used by the bot owner"""
    def __init__(self, bot):
        self.bot = bot


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
                await ctx.send('This command can only be used without an argument in a server.')
            else:
                await ctx.send(f'Now leaving the server. Goodbye!')
                await ctx.guild.leave()
        else:
            for server in ctx.bot.guilds:
                if server_name == server.name:
                    await ctx.send(f'Now leaving server: {server.name}')
                    await server.leave()
                    return

            await ctx.send('Server not found.')


    @commands.command(name='server-id', aliases=['sid', 'serverid'])
    async def get_server_id(self, ctx, *, server_name: str):
        """Gets the ID of a server by its name, if the bot can see the server"""
        servers = self.bot.guilds
        for server in servers:
            if server_name == server.name:
                await ctx.send(server.id)
        await ctx.message.add_reaction('✅')


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
            syntax, content = await unwrap_code_block(content)
            content = await escape_json(dedent(content))
            file_name = await get_14_digit_datetime()
            url = 'https://api.github.com/gists'
            data = '{"public":false,"files":{"%s.%s":{"content":"%s"}}}' \
                % (file_name, syntax, content)
            github_token = os.environ['MAIN_GITHUB_GISTS_TOKEN']
            auth = aiohttp.BasicAuth('wheelercj', password=github_token)

            async with self.bot.session.post(url, data=data, auth=auth) as response:
                if not response.ok:
                    raise ValueError(f'GitHub API request failed with status code {response.status}.')
                
                json_text = await response.json()
                html_url = json_text['html_url']

            await ctx.reply(f'New gist created at <{html_url}>')


    @commands.command(name='repeat', aliases=['rep', 'reinvoke'])
    async def repeat_command(self, ctx, n : int = 1, skip: int = 0):
        """Repeats the last command you used"""
        previous = ctx.bot.previous_command_ctxs
        if not len(previous):
            await ctx.send('No previous commands saved.')
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


    @commands.command(aliases=['SQL'])
    async def sql(self, ctx, *, statement: str):
        """Execute a PostgreSQL statement"""
        _, statement = await unwrap_code_block(statement)
        try:
            if statement.upper().startswith('SELECT'):
                ret = await self.bot.db.fetch(statement)
            else:
                ret = await self.bot.db.execute(statement)

            await ctx.send(ret)
            await ctx.message.add_reaction('✅')
        except Exception as e:
            await ctx.message.add_reaction('❗')
            await ctx.reply(f'PostgreSQL error: {e}')


def setup(bot):
    bot.add_cog(Owner(bot))
