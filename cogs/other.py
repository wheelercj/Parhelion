# External imports
import platform
from datetime import datetime, timezone
import json
import discord
from discord.ext import commands
import typing

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


    @commands.command(aliases=['i', 'info', 'stats', 'uptime', 'invite', 'support', 'owner', 'privacy-policy', 'privacy'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def about(self, ctx):
        """Shows general info about this bot"""
        embed = discord.Embed(title=f'{self.bot.user.name}#{self.bot.user.discriminator}')
        prefixes = await get_prefixes_str(self.bot, ctx.message)
        
        embed.add_field(name='prefixes\u2800',
            value=f'{prefixes}\u2800\n')
        embed.add_field(name='\u2800owner\u2800',
            value=f'\u2800{dev_settings.dev_name}\u2800\n')
        embed.add_field(name='\u2800uptime',
            value=f'\u2800{await self.uptime(ctx)}\n')

        embed.add_field(name='stats\u2800',
            value=f'servers: {len(self.bot.guilds)}\u2800\n' \
                f'users: {len(self.bot.users)}\u2800\n' \
                f'commands: {len(self.bot.commands)}\u2800\n' \
                f'commands you can use: {await self.count_available_cmds(ctx)}\u2800\n')
        embed.add_field(name='\u2800links\u2800',
            value=f'\u2800[bot invite]({dev_settings.bot_invite_link})\u2800\n' \
                f'\u2800[support server]({dev_settings.support_server_link})\u2800\n' \
                f'\u2800[privacy policy]({dev_settings.privacy_policy_link})\u2800\n')
        embed.add_field(name='\u2800made with',
            value=f'\u2800Python v{platform.python_version()}\n' \
                f'\u2800and [discord.py](https://discordpy.readthedocs.io/en/latest/) v{discord.__version__}\n')

        await ctx.send(embed=embed)


    async def uptime(self, ctx) -> str:
        """Returns the amount of time the bot has been running"""
        _uptime = datetime.now(timezone.utc) - self.bot.launch_time
        hours, remainder = divmod(int(_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f'{days}d, {hours}h, {minutes}m, {seconds}s'


    async def count_available_cmds(self, ctx) -> int:
        """Counts the commands that ctx.author can use"""
        count = 0
        for cmd in self.bot.commands:
            try:
                if await cmd.can_run(ctx):
                    count += 1
            except commands.CommandError:
                pass
        return count


    @commands.command(name='time', aliases=['clock', 'UTC', 'utc'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def _time(self, ctx):
        """Shows the current time in UTC"""
        current_time = datetime.now(timezone.utc)
        await ctx.send(f'The current time is {current_time} UTC')


    @commands.command(name='server-info', aliases=['serverinfo'])
    @commands.guild_only()
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
    

    @commands.command(name='user-info', aliases=['whois', 'who-is', 'member-info'])
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def user_info(self, ctx, user_id: typing.Optional[int], *, name: typing.Optional[str]):
        """Shows info about a member of the current server
        
        This command works with either their user ID, nickname, or username.
        """
        member = None
        if user_id is not None:
            member: discord.Member = ctx.guild.get_member(user_id)
        elif name is not None:
            member: discord.Member = ctx.guild.get_member_named(name)

        if member is None:
            await ctx.send('User not found.')
            return

        embed = discord.Embed()
        embed.add_field(name=f'{member.name}#{member.discriminator}\n\u2800',
            value=f'**display name:** {member.display_name}\n'
                + f'**ID:** {member.id}\n'
                + await self.get_whether_bot(ctx, member)
                + f'**account created:** {member.created_at}\n'
                + f'**joined server:** {member.joined_at}\n'
                + f'**top server role:** {member.top_role}\n'
                + f'**server roles:** ' + ', '.join(x.name for x in member.roles) + '\n'
                + await self.get_mutual_server_count(ctx, member)
                + await self.get_premium_since(ctx, member)
                + await self.get_global_roles(ctx, member)
        )
        embed.set_thumbnail(url=member.avatar_url)

        await ctx.send(embed=embed)


    async def get_whether_bot(self, ctx, member: discord.Member) -> str:
        """Returns a message if member is a bot, otherwise returns an empty string"""
        if member.bot:
            return f'**{member.display_name} is a bot**\n'
        else:
            return ''


    async def get_mutual_server_count(self, ctx, member: discord.Member) -> str:
        """Gets the number of servers in common between ctx.author and a member
        
        Returns an empty string if member is ctx.author or a bot.
        """
        if ctx.author != member and not member.bot:
            return f'**mutual servers with you:** {len(member.mutual_guilds)}\n'
        else:
            return ''


    async def get_premium_since(self, ctx, member: discord.Member) -> str:
        """Gets the datetime of when a member's premium began
        
        Returns an empty string if the member does not have premium.
        """
        r = member.premium_since
        if r is not None:
            return f'**premium since:** {r}\n'
        else:
            return ''


    async def get_global_roles(self, ctx, member: discord.Member) -> str:
        """Gets the global Discord roles of a member
        
        E.g. Discord staff, bug hunter, verified bot, etc.
        Returns an empty string if the member has no global roles.
        """
        flags = ', '.join(member.public_flags.all())
        if len(flags):
            return f'**global roles:**: {flags}\n'
        else:
            return ''


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
