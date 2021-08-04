# external imports
import discord
from discord.ext import commands
from typing import List, Tuple, Union
import platform

# internal imports
from common import format_datetime, format_timestamp, format_timedelta, get_prefixes_list, dev_settings, yes_or_no


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(hidden=True)
    async def ping(self, ctx):
        """Shows the bot's latency"""
        await ctx.send(f'Pong! Websocket latency: {self.bot.latency * 1000:.2f} ms')


    @commands.command(name='time', aliases=['clock', 'UTC', 'utc'])
    async def _time(self, ctx):
        """Shows the current time in UTC"""
        current_time = await format_datetime(ctx.message.created_at)
        await ctx.send(f'The current time in UTC is {current_time}')


    @commands.command(hidden=True)
    async def uptime(self, ctx):
        """Shows the time since the bot last restarted"""
        _uptime = await self.get_uptime(ctx)
        await ctx.send(f'Uptime: {_uptime}')

    
    @commands.command(hidden=True)
    async def stats(self, ctx):
        """Shows statistics about this bot"""
        embed = discord.Embed()
        embed.add_field(name='stats',
            value=f'websocket latency: {self.bot.latency * 1000:.2f} ms\n' \
                f'uptime: {await self.get_uptime(ctx)}\n' \
                f'servers: {len(self.bot.guilds)}\n' \
                f'users: {len(self.bot.users)}\n' \
                f'commands: {len(self.bot.commands)}\n' \
                f'commands used since last restart: {self.bot.command_use_count}\n' \
                f'commands {ctx.author} can use here: {await self.count_available_cmds(ctx)}\n')
        await ctx.send(embed=embed)


    @commands.command(hidden=True)
    async def invite(self, ctx):
        """Shows the link to invite this bot to another server"""
        await ctx.send(f'<{dev_settings.bot_invite_link}>')


    @commands.command(aliases=['contact'], hidden=True)
    async def support(self, ctx):
        """Shows the link to this bot's support server"""
        await ctx.send(f'<{dev_settings.support_server_link}>')


    @commands.command(aliases=['privacy-policy', 'privacypolicy'], hidden=True)
    async def privacy(self, ctx):
        """Shows the link to this bot's privacy policy"""
        await ctx.send(f'<{dev_settings.privacy_policy_link}>')


    @commands.command()
    async def about(self, ctx):
        """Shows general info about this bot"""
        embed = discord.Embed(title=f'{self.bot.user.name}#{self.bot.user.discriminator}')
        owner = self.bot.get_user(self.bot.owner_id)
        prefixes = await get_prefixes_list(self.bot, ctx.message)

        embed.add_field(name='\u200b\u2800',
            value=f'Use `{prefixes[0]}help` for help\nwith commands.\u2800\n\u2800')
        embed.add_field(name='\u2800owner\u2800',
            value=f'\u2800{owner.name}#{owner.discriminator}\u2800\n\u2800')
        embed.add_field(name='\u200b',
            value='\u200b\n\u200b')

        embed.add_field(name='links\u2800',
            value=f'[bot invite]({dev_settings.bot_invite_link})\u2800\n' \
                f'[support server]({dev_settings.support_server_link})\u2800\n' \
                f'[privacy policy]({dev_settings.privacy_policy_link})\u2800\n')
        embed.add_field(name='\u2800made with\u2800',
            value=f'\u2800Python v{platform.python_version()}\u2800\n' \
                f'\u2800and [discord.py](https://discordpy.readthedocs.io/en/latest/) v{discord.__version__}\u2800\n')
        embed.add_field(name='\u200b',
            value='\u200b')

        await ctx.send(embed=embed)


    @commands.command(hidden=True)
    async def source(self, ctx):
        await ctx.send('I am closed source.')


######################
# info command group #
######################


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
            await ctx.send("The server's data is unavailable.")
            return

        server = self.bot.get_guild(ctx.guild.id)
        bot_count = await self.get_bot_count(ctx, server)
        cat_count = len(server.categories)
        created = await format_timestamp(server.created_at)

        embed = discord.Embed(title='server info')
        embed.add_field(name='\u200b',
            value=f'name: {server.name}\n'
                + f'owner: {server.owner.name}#{server.owner.discriminator}\n'
                + f'description: {server.description}\n'
                + f'created: {created}\n'
                + f'region: {server.region}\n'
                + f'preferred locale: {server.preferred_locale}\n'
                + f'total members: {server.member_count}/{server.max_members} ({bot_count} bots)\n'
                + f'roles: {len(server.roles)}\n'
                + f'current boosts: {server.premium_subscription_count}\n'
                + f'boost level: {server.premium_tier}\n'
                + f'emojis: {len(server.emojis)}/{server.emoji_limit}\n'
                + f'file size limit: {server.filesize_limit/1000000:.2f} MB\n'
                + f'bitrate limit: {server.bitrate_limit/1000} kbps\n'
                + '\n'
                + '**channels**\n'
                + f'categories: {cat_count}\n'
                + f'total channels: {len(server.channels) - cat_count}\n'
                + f'text channels: {len(server.text_channels)}\n'
                + f'voice channels: {len(server.voice_channels)}\n'
                + f'stages: {len(server.stage_channels)}\n'
                + f'max video channel users: {server.max_video_channel_users}\n'
        )

        features = await self.get_server_features(ctx, server)
        if len(features):
            embed.add_field(name='\u2800',
                value='**features**\n' + features)

        embed.set_thumbnail(url=server.icon_url)

        await ctx.send(embed=embed)
    

    async def get_bot_count(self, ctx, server: discord.Guild) -> int:
        """Counts the bots in the server"""
        count = 0
        for member in server.members:
            if member.bot:
                count += 1
        return count


    async def get_server_features(self, ctx, server: discord.Guild) -> str:
        """Gets the server's features or returns any empty string if there are none"""
        features = ''
        for feature in sorted(server.features):
            features += f'\n• ' + feature.replace('_', ' ').lower()
        return features


    @info.command(name='member', aliases=['m', 'u', 'user'])
    @commands.guild_only()
    async def member_info(self, ctx, member: discord.Member):
        """Shows info about a member of the current server
        
        To see member permissions, use the `info perms` command.
        """
        created = await format_timestamp(member.created_at)
        joined = await format_timestamp(member.joined_at)

        embed = discord.Embed()
        embed.add_field(name=f'{member.name}#{member.discriminator}\n\u2800',
            value=f'**display name:** {member.display_name}\n'
                + await self.get_whether_bot(member)
                + f'**account created:** {created}\n'
                + f'**joined server:** {joined}\n'
                + f'**top server role:** {member.top_role}\n'
                + await self.get_server_roles(member)
                + await self.get_premium_since(member)
                + await self.get_global_roles(member)
        )
        embed.set_thumbnail(url=member.avatar_url)

        await ctx.send(embed=embed)


    async def get_whether_bot(self, member: discord.Member) -> str:
        """Returns a message if member is a bot, otherwise returns an empty string"""
        if member.bot:
            return f'**{member.display_name} is a bot**\n'
        else:
            return ''


    async def get_server_roles(self, member: discord.Member) -> str:
        """Returns a message listing all of a member's server roles, but only if they have 10 or fewer
        
        Otherwise returns an empty string.
        """
        if len(member.roles) <= 10:
            return f'**server roles:** ' + ', '.join(x.name for x in member.roles)
        else:
            return ''


    async def get_premium_since(self, member: discord.Member) -> str:
        """Gets the datetime of when a member's premium began
        
        Returns an empty string if the member does not have
        premium.
        """
        r = member.premium_since
        if r is not None:
            return f'**premium since:** {r}\n'
        else:
            return ''


    async def get_global_roles(self, member: discord.Member) -> str:
        """Gets the global Discord roles of a member
        
        E.g. Discord staff, bug hunter, verified bot, etc.
        Returns an empty string if the member has no global roles.
        """
        flags = ', '.join(member.public_flags.all())
        if len(flags):
            return f'**global roles:**: {flags}\n'
        else:
            return ''


    @info.command(name='bot', aliases=['b'])
    async def _bot_info(self, ctx):
        """Shows info about this bot"""
        about_command = self.bot.get_command('about')
        await ctx.invoke(about_command)
        stats_command = self.bot.get_command('stats')
        await ctx.invoke(stats_command)


    async def get_uptime(self, ctx) -> str:
        """Returns the amount of time the bot has been running"""
        _uptime = ctx.message.created_at - self.bot.launch_time
        time_message = await format_timedelta(_uptime)
        return time_message


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


    @info.command(name='role', aliases=['r'])
    @commands.guild_only()
    async def role_info(self, ctx, role: discord.Role):
        """Shows info about a role on the current server
        
        To see role permissions, use the `info perms` command.
        """
        managing_bot = None
        created = await format_timestamp(role.created_at)
        if role.tags is not None:
            if role.tags.bot_id is not None:
                managing_bot = ctx.guild.get_member(role.tags.bot_id)

        embed = discord.Embed()
        embed.add_field(name='role info',
            value=f'name: {role.name}\n'
                + f'members: {len(role.members)}\n'
                + f'hierarcy position: {role.position}\n'
                + f'created: {created}\n'
                + f'mentionable: {yes_or_no(role.mentionable)}\n'
                + f'default: {yes_or_no(role.is_default())}\n'
                + f'premium: {yes_or_no(role.is_premium_subscriber())}\n'
                + f'3rd-party integration: {yes_or_no(role.managed)}\n'
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
        