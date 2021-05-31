# External imports
from replit import db
import platform
import inspect
from datetime import datetime, timezone
import requests
import json
import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

# Internal imports
from common import remove_backticks, send_traceback


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(hidden=True)
    @commands.cooldown(1, 15, BucketType.user)
    async def hhelp(self, ctx):
        '''Shows help for all the hidden commands'''
        hidden_commands = []
        for cmd in self.bot.commands:
            if cmd.hidden:
                hidden_commands.append(cmd)

        # Alphabetize.
        hidden_commands = sorted(hidden_commands, key=lambda x: x.name)

        # Get column width.
        hidden_names = [x.name for x in hidden_commands]
        width = len(max(hidden_names, key=len))

        message = 'Hidden Commands:'
        for cmd in hidden_commands:
            message += f'\n  {cmd.name:<{width}} {cmd.short_doc}'
            if len(cmd.checks):
                message += ' (bot owner only)'
        message += '\n\n Type ;help command for more info on a command.'

        await ctx.send(f'```{message}```')


    @commands.command(hidden=True)
    @commands.cooldown(1, 15, BucketType.user)
    async def echo(self, ctx, *, message: str):
        '''Repeats a message'''
        await ctx.send(message)


    @commands.command(hidden=True)
    @commands.cooldown(1, 15, BucketType.user)
    async def ping(self, ctx):
        '''Pings the server'''
        await ctx.send(f'Pong! It took {round(self.bot.latency, 2)} ms.')


    @commands.command(aliases=['info', 'stats', 'invite', 'uptime', 'servers'])
    @commands.cooldown(1, 15, BucketType.user)
    async def about(self, ctx):
        '''Shows general info about this bot'''
        embed = discord.Embed(title='Parhelion#3922')
        
        embed.add_field(name='servers\u2800', value=str(len(self.bot.guilds)))
        embed.add_field(name='\u2800uptime', value=f'\u2800{await self.uptime(ctx)}\u2800')
        embed.add_field(name='\u2800owner', value='\u2800Chris Wheeler')
        embed.add_field(name='bot invite\u2800', value='[link](https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3595328)')
        embed.add_field(name='\u2800repository\u2800', value='\u2800[link](https://replit.com/@wheelercj/simple-Discord-bot)')
        embed.add_field(name='\u2800made with', value=f'\u2800Python v{platform.python_version()} and [discord.py](https://discordpy.readthedocs.io/en/latest/) v{discord.__version__}.')
        
        await ctx.send(embed=embed)


    async def uptime(self, ctx) -> str:
        _uptime = datetime.now(timezone.utc) - self.bot.launch_time
        hours, remainder = divmod(int(_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f'{days}d, {hours}h, {minutes}m, {seconds}s'


    @commands.command(name='dev-about', hidden=True)
    @commands.cooldown(1, 15, BucketType.user)
    async def dev_about(self, ctx):
        '''Shows implementation info about this bot'''
        embed = discord.Embed(title='Parhelion#3922', description='Use the `about` command if you want to see general info.')
        
        embed.add_field(name='reminders\u2800', value=str(len(db)))
        
        await ctx.send(embed=embed)


    @commands.command(name='inspect', aliases=['source', 'src'])
    @commands.cooldown(1, 15, BucketType.user)
    async def _inspect(self, ctx, *, command: str):
        '''Shows the source code of a command'''
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


    @commands.command(aliases=['calc', 'solve'])
    @commands.cooldown(1, 15, BucketType.user)
    async def math(self, ctx, *, expression: str):
        '''Evaluates a math expression
        
        Evaluates multiple expressions if they're on separate lines.
        Uses the mathjs API: https://mathjs.org/
        '''
        try:
            expression = remove_backticks(expression)
            if '**' in expression:
                raise ValueError('This command uses ^ instead of ** for exponents.')
            raw_expressions = expression.split('\n')
            expressions = json.dumps(raw_expressions)
            expressions_json = '{\n"expr": ' + expressions + '\n}'

            response = requests.post('http://api.mathjs.org/v4/',
                data = expressions_json,
                headers = {'content-type': 'application/json'},
                timeout = 10
            )
            if not response and response.status_code != 400:
                raise ValueError(f'API request failed with status code {response.status_code}.')

            json_text = response.json()

            if response.status_code == 400:
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


    @commands.command(hidden=True)
    @commands.cooldown(1, 15, BucketType.user)
    async def reverse(self, ctx, *, message: str):
        '''Reverses a message'''
        await ctx.send(message[::-1])


    @commands.command(hidden=True)
    @commands.cooldown(1, 15, BucketType.user)
    async def rot13(self, ctx, *, message: str):
        '''Rotates each letter 13 letters through the alphabet'''
        message = message.lower()
        new_string = ''
        alphabet = 'abcdefghijklmnopqrstuvwxyz'
        for char in message:
            index = alphabet.find(char)
            if index != -1:
                new_index = (index + 13) % 26
                new_string += alphabet[new_index]
            else:
                new_string += char

        await ctx.send(new_string)


def setup(bot):
    bot.add_cog(Other(bot))
