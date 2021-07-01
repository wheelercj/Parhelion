# External imports
from datetime import datetime, timezone
import json
import discord
from discord.ext import commands
import typing
from typing import List, Tuple

# Internal imports
from common import remove_backticks, send_traceback


class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def ping(self, ctx):
        """Pings the server"""
        await ctx.send(f'Pong! It took {round(self.bot.latency, 2)} ms.')


    @commands.command(name='time', aliases=['clock', 'UTC', 'utc'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def _time(self, ctx):
        """Shows the current time in UTC"""
        current_time = datetime.now(timezone.utc)
        await ctx.send(f'The current time is {current_time} UTC')


    @commands.command(name='server-info', aliases=['serverinfo', 'guild-info', 'guildinfo'])
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def server_info(self, ctx):
        """Shows info about the current server"""
        if ctx.guild.unavailable:
            await ctx.send('The server\'s data is unavailable.')
            return

        guild = self.bot.get_guild(ctx.guild.id)
        bot_count = await self.get_bot_count(ctx, guild)
        human_count = guild.member_count - bot_count

        embed = discord.Embed()
        embed.add_field(name='server info',
            value=f'name: {guild.name}\n'
                + f'ID: {guild.id}\n'
                + f'owner: {guild.owner.name}#{guild.owner.discriminator}\n'
                + f'owner ID: {guild.owner_id}\n'
                + f'description: {guild.description}\n'
                + f'created: {guild.created_at}\n'
                + f'region: {guild.region}\n'
                + f'preferred locale: {guild.preferred_locale}\n'
                + f'current boosts: {guild.premium_subscription_count}\n'
                + f'roles: {len(guild.roles)}\n'
                + f'emojis: {len(guild.emojis)}/{guild.emoji_limit}\n'
                + f'file size limit: {guild.filesize_limit/1000000:.2f} MB\n'
                + f'bitrate limit: {guild.bitrate_limit/1000} kbps\n'
                + '\n'
                + '**members**\n'
                + f'total members: {guild.member_count}/{guild.max_members}\n'
                + f'humans: {human_count}\n'
                + f'bots: {bot_count}\n'
                + '\n'
                + '**channels**\n'
                + f'total channels: {len(guild.channels)}\n'
                + f'categories: {len(guild.categories)}\n'
                + f'text channels: {len(guild.text_channels)}\n'
                + f'voice channels: {len(guild.voice_channels)}\n'
                + f'stages: {len(guild.stage_channels)}\n'
                + f'max video channel users: {guild.max_video_channel_users}\n'
                + '\n'
                + await self.get_server_features(ctx, guild)
        )
        embed.set_thumbnail(url=guild.icon_url)

        await ctx.send(embed=embed)
    

    async def get_bot_count(self, ctx, guild):
        """Counts the bots in the server"""
        count = 0
        for member in guild.members:
            if member.bot:
                count += 1
        return count


    async def get_server_features(self, ctx, guild):
        """Gets the server's features or returns any empty string if there are none"""
        features = ', '.join(guild.features)
        if len(features):
            return '**features**\n' + features
        else:
            return ''


    async def _get_member(self, ctx, member_id: int = None, name: str = None) -> discord.Member:
        """Gets a member object from a member ID, display name, or context
        
        member_id can only be used in a guild.
        """
        if member_id is not None:
            return ctx.guild.get_member(member_id)
        elif name is not None:
            if ctx.guild is None:
                raise ValueError('member_id can only be used in a guild')
            return ctx.guild.get_member_named(name)
        else:
            return ctx.guild.get_member(ctx.author.id)


    @commands.command(name='user-info', aliases=['userinfo', 'who-is', 'whois', 'member-info', 'memberinfo'])
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def user_info(self, ctx, user_id: typing.Optional[int], *, name: typing.Optional[str]):
        """Shows info about a member of the current server
        
        This command works with either their user ID, nickname, or username.
        """
        member: discord.Member = await self._get_member(ctx, user_id, name)
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


    @commands.command(name='permissions', aliases=['perms'])
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def server_permissions(self, ctx, user_id: typing.Optional[int], *, name: typing.Optional[str]):
        """Shows the server and channel permissions of a user"""
        member: discord.Member = await self._get_member(ctx, user_id, name)
        if member is None:
            await ctx.send('User not found.')
            return

        embed = discord.Embed(title=f'{member.name}#{member.discriminator}\'s permissions')

        server_perms = await self.format_perms(member.guild_permissions)
        embed.add_field(name=f'server permissions', value=server_perms)

        all_channel_perms = await self.get_each_channels_perms(ctx, member)
        if len(all_channel_perms):
            server_n = server_perms.count('\n')
            channel_n = all_channel_perms.count('\n')
            if server_n > channel_n:
                embed.add_field(name='channel overwrites', value=all_channel_perms)
            else:
                half = channel_n / 2
                embed.add_field(name='channel overwrites', value=all_channel_perms[:half])
                embed.add_field(name='channel overwrites cont.', value=all_channel_perms[half:])
        
        await ctx.send(embed=embed)


    async def format_perms(self, permissions: discord.Permissions) -> str:
        """Convert a permissions object to a printable string
        
        Returns False if the permissions are for a hidden text channel.
        """
        if not permissions.read_messages and permissions.read_messages is not None:
            return False
        perm_list = sorted(list(permissions), key=lambda x: x[0])
        return await self.perm_list_message(perm_list)


    async def get_each_channels_perms(self, ctx, member: discord.Member) -> str:
        """Gets the permissions for each channel that overwrite the server permissions
        
        Any hidden text channels are not named, but counted.
        """
        all_channel_perms = ''
        hidden_text_count = 0
        for channel in ctx.guild.channels:
            channel_perms = await self.format_perms(channel.overwrites_for(member))
            if not channel_perms and channel_perms != '' and channel.category:
                hidden_text_count += 1
            elif len(channel_perms):
                all_channel_perms += f'**\u2800{channel.name}**\n' \
                                     f'{channel_perms}\n'
        
        if hidden_text_count:
            all_channel_perms += f'**\u2800({hidden_text_count} hidden text channels)**\n' \
                                 f'\u2800❌ read messages\n'
        
        return all_channel_perms


    async def perm_list_message(self, perm_list: List[Tuple[str, bool]]) -> str:
        """Convert a permissions list to a printable string
        
        perm_list is a list of tuples in the format (name_of_perm, if_perm_granted).
        Using `list(perm_obj)` where `perm_obj` is of type discord.Permissions gives 
        the correct format. If a permission's bool is set to None, the permission will
        be ignored.
        """
        perm_str = ''
        for name, value in perm_list:
            name = name.replace('_', ' ')
            if value:
                perm_str += f'\u2800✅ {name}\n'
            elif value is not None:
                perm_str += f'\u2800❌ {name}\n'

        return perm_str


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
