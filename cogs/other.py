# External imports
from replit import db
import platform
import inspect
from datetime import datetime, timezone
import json
import discord
from discord.ext import commands

# Internal imports
from common import remove_backticks, send_traceback, get_prefixes_str, dev_settings


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['prefix'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def prefixes(self, ctx):
        """Lists the bot's current prefixes"""
        prefixes = get_prefixes_str(self.bot, ctx.message)
        await ctx.send(f'My current prefixes are {prefixes}')


    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def ping(self, ctx):
        """Pings the server"""
        await ctx.send(f'Pong! It took {round(self.bot.latency, 2)} ms.')


    @commands.command(aliases=['i', 'info', 'stats', 'uptime', 'invite', 'support', 'privacy-policy', 'privacy'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def about(self, ctx):
        """Shows general info about this bot"""
        embed = discord.Embed(title=f'{self.bot.user.name}#{self.bot.user.discriminator}')
        prefixes = await get_prefixes_str(self.bot, ctx.message)
        
        embed.add_field(name='prefixes\u2800', value=prefixes + '\u2800\n\u2800')
        embed.add_field(name='\u2800owner\u2800', value=f'\u2800{dev_settings.dev_name}\u2800\n\u2800')
        embed.add_field(name='\u2800uptime', value=f'\u2800{await self.uptime(ctx)}\n\u2800')

        embed.add_field(name='stats\u2800',
            value=f'servers: {len(self.bot.guilds)}\u2800\n' \
                f'users: {len(self.bot.users)}\u2800\n' \
                f'commands: {len(self.bot.commands)}\u2800\n' \
                f'tasks: {len(db)}\u2800\u2800')
        embed.add_field(name='\u2800links\u2800',
            value=f'\u2800[bot invite]({dev_settings.bot_invite_link})\u2800\n\u2800' \
                f'[support server]({dev_settings.support_server_link})\u2800\n\u2800' \
                f'[privacy policy]({dev_settings.privacy_policy_link})\u2800\n\u2800')
        embed.add_field(name='\u2800made with',
            value=f'\u2800Python v{platform.python_version()}\n\u2800' \
                f'and [discord.py](https://discordpy.readthedocs.io/en/latest/) v{discord.__version__}\n\u2800')

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
        """Shows the current time in UTC"""
        current_time = datetime.now(timezone.utc)
        await ctx.send(f'The current time is {current_time} UTC')


    @commands.command(name='server-info', aliases=['serverinfo'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def server_info(self, ctx):
        """Shows info about the current server"""
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


    @commands.command(aliases=['calc', 'solve', 'maths'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def math(self, ctx, *, expression: str):
        """Evaluates a math expression
        
        Evaluates multiple expressions if they're on separate lines, and supports code blocks.
        Uses the math.js API: https://mathjs.org/docs/expressions/syntax.html
        """
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
        """Rotates each letter n letters through the alphabet"""
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
