# External imports
from replit import db
import platform
import inspect
from datetime import datetime, timezone
import json
import discord
from discord.ext import commands
from textwrap import dedent

# Internal imports
from common import remove_backticks, send_traceback, get_prefixes_str, dev_settings


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['prefix'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def prefixes(self, ctx):
        '''Lists the bot\'s current prefixes'''
        prefixes = get_prefixes_str(self.bot)
        await ctx.send(f'My current prefixes are {prefixes}')


    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def ping(self, ctx):
        '''Pings the server'''
        await ctx.send(f'Pong! It took {round(self.bot.latency, 2)} ms.')


    @commands.command(aliases=['i', 'info', 'stats', 'invite', 'uptime', 'servers', 'users'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def about(self, ctx):
        '''Shows general info about this bot'''
        embed = discord.Embed(title=f'{self.bot.user.name}#{self.bot.user.discriminator}')
        prefixes = await get_prefixes_str(self.bot)
        
        embed.add_field(name='prefixes\u2800', value=prefixes + '\u2800\n\u2800')
        embed.add_field(name='\u2800owner\u2800', value=f'\u2800{dev_settings.dev_name}\u2800\n\u2800')
        embed.add_field(name='\u2800uptime', value=f'\u2800{await self.uptime(ctx)}\n\u2800')

        embed.add_field(name='stats\u2800', value=f'servers: {len(self.bot.guilds)}\u2800\nusers: {len(self.bot.users)}\u2800\ncommands: {len(self.bot.commands)}\u2800\ntasks: {len(db)}\u2800\u2800')
        embed.add_field(name='\u2800links\u2800', value=f'\u2800[bot invite]({dev_settings.bot_invite_link})\u2800\n\u2800[repository]({dev_settings.bot_repository_link})\u2800\n\u2800')
        embed.add_field(name='\u2800made with', value=f'\u2800Python v{platform.python_version()}\n\u2800and [discord.py](https://discordpy.readthedocs.io/en/latest/) v{discord.__version__}\n\u2800')

        await ctx.send(embed=embed)


    async def uptime(self, ctx) -> str:
        _uptime = datetime.now(timezone.utc) - self.bot.launch_time
        hours, remainder = divmod(int(_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f'{days}d, {hours}h, {minutes}m, {seconds}s'


    @commands.command(name='time', aliases=['clock', 'UTC', 'utc'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def _time(self, ctx):
        '''Shows the current time in UTC'''
        current_time = datetime.now(timezone.utc)
        await ctx.send(f'The current time is {current_time} UTC')


    @commands.command(name='privacy-policy', aliases=['privacy'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def privacy_policy(self, ctx):
        '''Shows the bot\'s privacy policy'''
        embed = discord.Embed()
        embed.add_field(name='Privacy Policy',
            value=dedent('''
                Last updated: June 27, 2021
                This Privacy Policy may be updated at any time without any notification.

                **agreement**
                By using this bot or by being in a Discord channel that this bot can see, you agree to the following Privacy Policy.

                **what data is stored**
                * If you create reminder(s) or a daily quote, the bot will store your Discord user ID, the server ID (if applicable), the channel ID (if applicable), and any text input you give the bot.
                * If you send a message in a channel that the bot can see, some data may be temporarily logged and/or cached including but not limited to: the message and your Discord user ID, name, and discriminator. For more details, click [here](https://discordpy.readthedocs.io/en/latest/ext/commands/api.html?highlight=context#discord.ext.commands.Context).

                **why data is stored**
                Data is only stored and used to allow the bot to function properly, to fix bugs, and to investigate errors. Data is retained as long as needed to fulfill these purposes.

                **who has access to your data**
                Your data is not shared with any third parties.

                **questions and concerns**
                Please join the [support server](https://discord.gg/mCqGhPJVcN).

                **how to delete your data**
                You can use the `del-r` and `quote stop` commands, or join the [support server](https://discord.gg/mCqGhPJVcN) and ask about having your data deleted.
            ''')
        )

        await ctx.send(embed=embed)


    @commands.command(name='server-info', aliases=['serverinfo'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def server_info(self, ctx):
        '''Shows info about the current server'''
        embed = discord.Embed()
        embed.add_field(name='server info\n\u2800',
            value=f'**name:** {ctx.guild.name}\n'
                + f'**ID:** {ctx.guild.id}\n'
                + f'**description:** {ctx.guild.description}\n'
                + f'**owner:** {ctx.guild.owner}\n'
                + f'**roles:** {len(ctx.guild.roles)}\n'
                + f'**members:** {len(ctx.guild.members)}'
        )
        embed.set_thumbnail(url=ctx.guild.icon_url)

        await ctx.send(embed=embed)


    @commands.command(name='inspect', aliases=['source', 'src', 'getsource'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def _inspect(self, ctx, *, command: str = None):
        '''Shows the source code of a command'''
        if command is None:
            await ctx.send(f'Here is my source code: {dev_settings.bot_repository_link}')
        else:
            try:
                cmds = {cmd.name: cmd for cmd in self.bot.commands}
                if command not in cmds.keys():
                    raise NameError(f'Command {command} not found.')
                source = str(inspect.getsource(cmds[command].callback))
                await ctx.send(f'```py\n{source}```')
            except NameError as e:
                await ctx.send(e)
            except KeyError as e:
                await ctx.send(e)


    @commands.command(aliases=['calc', 'solve', 'maths'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def math(self, ctx, *, expression: str):
        '''Evaluates a math expression
        
        Evaluates multiple expressions if they're on separate lines, and supports code blocks.
        Uses the math.js API: https://mathjs.org/docs/expressions/syntax.html
        '''
        try:
            expression = remove_backticks(expression)
            if '**' in expression:
                raise ValueError('This command uses ^ rather than ** for exponents.')
            raw_expressions = expression.split('\n')
            expressions = json.dumps(raw_expressions)
            expressions_json = '{\n"expr": ' + expressions + '\n}'

            async with ctx.typing():
                async with self.bot.session.post('http://api.mathjs.org/v4/',
                    data = expressions_json,
                    headers = {'content-type': 'application/json'},
                    timeout = 10
                ) as response:
                    if not response and response.status != 400:
                        raise ValueError(f'API request failed with status code {response.status}.')

                    json_text = await response.json()

                    if response.status == 400:
                        raise ValueError(json_text['error'])

            result = ''
            for i, expr in enumerate(raw_expressions):
                result += '\n`' + expr + '` = `' + json_text['result'][i] + '`'

            embed = discord.Embed(description=result)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(e)
            if await self.bot.is_owner(ctx.author):
                await send_traceback(ctx, e)


    @commands.command(aliases=['rotate', 'rot', 'shift'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def cipher(self, ctx, n: int, *, message: str):
        '''Rotates each letter n letters through the alphabet'''
        message = message.lower()
        new_string = ''
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        for char in message:
            index = alphabet.find(char)
            if index != -1:
                new_index = (index + n) % 26
                new_string += alphabet[new_index]
            else:
                new_string += char

        await ctx.send(new_string)


def setup(bot):
    bot.add_cog(Other(bot))
