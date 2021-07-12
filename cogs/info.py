# external imports
import discord
from discord.ext import commands
from typing import List, Tuple, Union


def y_n(boolean: bool) -> str:
    """Returns 'yes' or 'no'"""
    return 'yes' if boolean else 'no'


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name='time', aliases=['clock', 'UTC', 'utc'])
    async def _time(self, ctx):
        """Shows the current time in UTC"""
        current_time = ctx.message.created_at
        await ctx.send(f'The current time is {current_time} UTC')


    @commands.group(aliases=['i'], invoke_without_command=True)
    @commands.guild_only()
    async def info(self, ctx):
        """Shows info about various topics. Use one of the subcommands listed below."""
        await ctx.send_help('info')


    @info.command(name='server', aliases=['s', 'g', 'guild'])
    @commands.guild_only()
    async def server_info(self, ctx):
        """Shows info about the current server"""
        if ctx.guild.unavailable:
            await ctx.send('The server\'s data is unavailable.')
            return

        guild = self.bot.get_guild(ctx.guild.id)
        bot_count = await self.get_bot_count(ctx, guild)
        cat_count = len(guild.categories)

        embed = discord.Embed(title='server info')
        embed.add_field(name='\u200b',
            value=f'name: {guild.name}\n'
                + f'owner: {guild.owner.name}#{guild.owner.discriminator}\n'
                + f'description: {guild.description}\n'
                + f'created: {guild.created_at}\n'
                + f'region: {guild.region}\n'
                + f'preferred locale: {guild.preferred_locale}\n'
                + f'total members: {guild.member_count}/{guild.max_members} ({bot_count} bots)\n'
                + f'roles: {len(guild.roles)}\n'
                + f'current boosts: {guild.premium_subscription_count}\n'
                + f'boost level: {guild.premium_tier}\n'
                + f'emojis: {len(guild.emojis)}/{guild.emoji_limit}\n'
                + f'file size limit: {guild.filesize_limit/1000000:.2f} MB\n'
                + f'bitrate limit: {guild.bitrate_limit/1000} kbps\n'
                + '\n'
                + '**channels**\n'
                + f'categories: {cat_count}\n'
                + f'total channels: {len(guild.channels) - cat_count}\n'
                + f'text channels: {len(guild.text_channels)}\n'
                + f'voice channels: {len(guild.voice_channels)}\n'
                + f'stages: {len(guild.stage_channels)}\n'
                + f'max video channel users: {guild.max_video_channel_users}\n'
        )

        features = await self.get_server_features(ctx, guild)
        if len(features):
            embed.add_field(name='\u2800',
                value='**features**\n' + features)

        embed.set_thumbnail(url=guild.icon_url)

        await ctx.send(embed=embed)
    

    async def get_bot_count(self, ctx, guild: discord.Guild) -> int:
        """Counts the bots in the server"""
        count = 0
        for member in guild.members:
            if member.bot:
                count += 1
        return count


    async def get_server_features(self, ctx, guild: discord.Guild) -> str:
        """Gets the server's features or returns any empty string if there are none"""
        features = ''
        for feature in sorted(guild.features):
            features += f'\n• ' + feature.replace('_', ' ').lower()
        return features


    @info.command(name='user', aliases=['u', 'm', 'member'])
    @commands.guild_only()
    async def user_info(self, ctx, member: discord.Member):
        """Shows info about a member of the current server
        
        To see member permissions, use the `info perms` command.
        """
        embed = discord.Embed()
        embed.add_field(name=f'{member.name}#{member.discriminator}\n\u2800',
            value=f'**display name:** {member.display_name}\n'
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
        
        Returns an empty string if the member does not have
        premium.
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


    @info.command(name='role', aliases=['r'])
    @commands.guild_only()
    async def role_info(self, ctx, role: discord.Role):
        """Shows info about a role on the current server
        
        To see role permissions, use the `info perms` command.
        """
        managing_bot = None
        if role.tags is not None:
            if role.tags.bot_id is not None:
                managing_bot = ctx.guild.get_member(role.tags.bot_id)

        embed = discord.Embed()
        embed.add_field(name='role info',
            value=f'name: {role.name}\n'
                + f'members: {len(role.members)}\n'
                + f'hierarcy position: {role.position}\n'
                + f'created: {role.created_at}\n'
                + f'mentionable: {y_n(role.mentionable)}\n'
                + f'default: {y_n(role.is_default())}\n'
                + f'premium: {y_n(role.is_premium_subscriber())}\n'
                + f'3rd-party integration: {y_n(role.managed)}\n'
                + f'managing bot: {managing_bot}\n'
        )

        await ctx.send(embed=embed)


    @info.command(name='perms', aliases=['permissions'])
    @commands.guild_only()
    async def server_permissions(self, ctx, member_or_role: Union[discord.Member, discord.Role] = None):
        """Shows the server and channel permissions of a member or role

        If a user and role have the same ID and/or name, the permissions
        for the user will be shown. User permissions include the
        permissions for all roles that user has.
        """
        if member_or_role is None:
            member_or_role = ctx.author
        server_perms, overwrites, title = await self.get_perms(ctx, member_or_role)
        if not len(server_perms):
            await ctx.send('Could not find the user or role.')
            return

        embed = discord.Embed(title=title)
        embed.add_field(name=f'server permissions', value=server_perms)
        if len(overwrites):
            embed = await self.embed_overwrites(embed, server_perms, overwrites)

        await ctx.send(embed=embed)


    async def embed_overwrites(self, embed, server_perms, overwrites):
        server_n = server_perms.count('\n')
        channel_n = overwrites.count('\n')
        if server_n > channel_n:
            embed.add_field(name='channel overwrites',
                value=overwrites)
        else:
            half = channel_n / 2
            embed.add_field(name='channel overwrites',
                value=overwrites[:half])
            embed.add_field(name='channel overwrites cont.',
                value=overwrites[half:])

        return embed


    async def format_perms(self, permissions: discord.Permissions) -> Union[str, bool]:
        """Converts a permissions object to a printable string
        
        Returns False if the permissions are for a hidden text
        channel.
        """
        if not permissions.read_messages \
                and permissions.read_messages is not None:
            return False
        perm_list = sorted(list(permissions), key=lambda x: x[0])
        return await self.perm_list_message(perm_list)


    async def get_perms(self, ctx, member_or_role: Union[discord.Member, discord.Role]) -> Tuple[str, str, str]:
        """Gets the formatted server perms, channel overwrites, and embed title"""
        if isinstance(member_or_role, discord.Member):
            member = member_or_role
            server_perms = await self.format_perms(member.guild_permissions)
            overwrites = await self.get_perm_overwrites(ctx, member)
            title = f'{member.name}#{member.discriminator}\'s permissions'
            return server_perms, overwrites, title
        elif isinstance(member_or_role, discord.Role):
            role = member_or_role
            if role is not None:
                server_perms = await self.format_perms(role.permissions)
                overwrites = await self.get_perm_overwrites(ctx, role)
                title = f'{role.name} role permissions'
                return server_perms, overwrites, title

        return '', '', ''


    async def get_perm_overwrites(self, ctx, member_or_role: Union[discord.Member, discord.Role]) -> str:
        """Gets the permissions for each channel that overwrite the server permissions
        
        Any hidden text channels are not named, but counted.
        """
        overwrites = ''
        hidden_text_count = 0
        for channel in ctx.guild.channels:
            channel_perms = await self.format_perms(channel.overwrites_for(member_or_role))
            if not channel_perms and channel_perms != '' and channel.category:
                hidden_text_count += 1
            elif len(channel_perms):
                overwrites += f'**\u2800{channel.name}**\n' \
                                     f'{channel_perms}\n'
        
        if hidden_text_count:
            overwrites += f'**\u2800({hidden_text_count} hidden text channels)**\n' \
                                 f'\u2800❌ read messages\n'
        
        return overwrites


    async def perm_list_message(self, perm_list: List[Tuple[str, bool]]) -> str:
        """Converts a permissions list to a printable string
        
        perm_list is a list of tuples in the format
        (perm_name, is_perm_granted). Using `list(perm_obj)` where
        `perm_obj` is of type discord.Permissions gives the
        correct format. If a permission's bool is set to None, the
        permission will be ignored.
        """
        perm_str = ''
        for name, value in perm_list:
            name = name.replace('_', ' ')
            if value:
                perm_str += f'\u2800✅ {name}\n'
            elif value is not None:
                perm_str += f'\u2800❌ {name}\n'

        return perm_str


def setup(bot):
    bot.add_cog(Info(bot))
        