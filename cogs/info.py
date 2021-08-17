# external imports
import discord
from discord.ext import commands
import os
from typing import List, Tuple, Union
import platform
from functools import lru_cache
from textwrap import dedent
from datetime import datetime
from datetime import timezone as tz
import pytz
from typing import List

# internal imports
from cogs.utils.time import parse_time_message, format_datetime, format_timedelta, create_relative_timestamp, create_long_datetime_stamp
from cogs.utils.common import get_prefixes_list, dev_settings, get_bot_invite_link
from cogs.utils.paginator import paginate_search


'''
    CREATE TABLE timezones (
        user_id BIGINT PRIMARY KEY NOT NULL,
        timezone TEXT NOT NULL
    );
'''


def yes_or_no(boolean: bool) -> str:
    """Returns either 'yes' or 'no'"""
    if boolean:
        return 'yes'
    return 'no'


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
        current_time = await format_datetime(datetime.now(tz.utc))
        now_timestamp = await create_relative_timestamp(datetime.now(tz.utc))
        message = f'The current time in UTC is {current_time}\n' \
                f'The current time in your device\'s timezone is {now_timestamp}'
        await ctx.send(message)


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
                f'commands {ctx.author} can use here: {await self.count_available_cmds(ctx)}\n' \
                f'lines of code: {self.count_bot_loc()}')
        await ctx.send(embed=embed)


    @lru_cache
    def count_bot_loc(self) -> int:
        """Counts the lines of Python code in the entire bot"""
        return self.count_dir_loc('.')


    def count_dir_loc(self, dir_path: str) -> int:
        """Counts the lines of Python code in a directory and its subdirectories"""
        line_count = 0

        for name in os.listdir(dir_path):
            if name in ('.git', '__pycache__'):
                continue
            path = os.path.join(dir_path, name)
            if os.path.isdir(path):
                line_count += self.count_dir_loc(path)
            elif os.path.isfile(path):
                if path.endswith('.py'):
                    with open(path, 'r') as file:
                        line_count += len(file.readlines())

        return line_count


    @commands.command(hidden=True)
    async def invite(self, ctx):
        """Shows the link to invite this bot to another server"""
        bot_invite_link = await get_bot_invite_link(self.bot)
        await ctx.send(f"Here's the link to invite me to another server: <{bot_invite_link}>")


    @commands.command(aliases=['contact'], hidden=True)
    async def support(self, ctx):
        """Shows the link to this bot's support server"""
        await ctx.send(f"Here's the link to my support server: <{dev_settings.support_server_link}>")


    @commands.command(aliases=['privacy-policy', 'privacypolicy'], hidden=True)
    async def privacy(self, ctx):
        """Shows the link to this bot's privacy policy"""
        await ctx.send(f"Here's my privacy policy: <{dev_settings.privacy_policy_link}>")


    @commands.command()
    async def about(self, ctx):
        """Shows general info about this bot"""
        embed = discord.Embed(title=f'{self.bot.user.name}#{self.bot.user.discriminator}')
        owner = self.bot.get_user(self.bot.owner_id)
        prefixes = await get_prefixes_list(self.bot, ctx.message)
        bot_invite_link = await get_bot_invite_link(self.bot)

        embed.add_field(name='\u200b\u2800',
            value=f'Use `{prefixes[0]}help` for help\nwith commands.\u2800\n\u2800')
        embed.add_field(name='\u2800owner\u2800',
            value=f'\u2800{owner.name}#{owner.discriminator}\u2800\n\u2800')
        embed.add_field(name='\u200b',
            value='\u200b\n\u200b')

        embed.add_field(name='links\u2800',
            value=f'[bot invite]({bot_invite_link})\u2800\n' \
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


    @commands.command(name='timestamp')
    async def _timestamp(self, ctx, *, _time: str):
        """Shows how you can create timestamps that work with each device's timezone

        You can enter the date/time/duration in natural language,
        and you can copy and paste a raw timestamp into your discord messages.
        If you have not chosen a timezone with the `timezone set` command, UTC will be assumed.
        """
        dt, _ = await parse_time_message(ctx, _time)
        unix_time = int(dt.timestamp())
        output = dedent(f'''
            short time:
                `<t:{unix_time}:t>` → <t:{unix_time}:t>
            long time:
                `<t:{unix_time}:T>` → <t:{unix_time}:T>
            short date:
                `<t:{unix_time}:d>` → <t:{unix_time}:d>
            long date:
                `<t:{unix_time}:D>` → <t:{unix_time}:D>
            short date/time:
                `<t:{unix_time}:f>` → <t:{unix_time}:f>
            long date/time:
                `<t:{unix_time}:F>` → <t:{unix_time}:F>
            relative time:
                `<t:{unix_time}:R>` → <t:{unix_time}:R>
            ''')

        await ctx.send(output)


###########################
# _timezone command group #
###########################
    
    
    @commands.group(name='timezone', aliases=['tz'], invoke_without_command=True)
    async def _timezone(self, ctx):
        """Shows your current timezone setting if you have one
        
        Use the `timezone set` command to set a timezone for commands that need your time input. See the valid timezone options with the `timezone search` command, or by clicking here: <https://gist.github.com/wheelercj/86588a956b7912dfb24ec51d36c2f124>
        """
        # https://github.com/stub42/pytz/blob/master/src/README.rst
        timezone = await self.bot.db.fetchval('''
            SELECT timezone
            FROM timezones
            WHERE user_id = $1;
            ''', ctx.author.id)
        if timezone is not None:
            await ctx.send(f'Your current timezone setting is `{timezone}`')
        else:
            await ctx.send_help('timezone')


    @_timezone.command(name='search', aliases=['l', 'list'])
    async def search_timezones(self, ctx, *, query: str = None):
        """Shows all the valid timezone options that contain a search word
        
        You can also see the valid timezone options here: <https://gist.github.com/wheelercj/86588a956b7912dfb24ec51d36c2f124>.
        If the valid timezones change, the update to the GitHub gist may be delayed unlike this search command.
        """
        if query is None:
            title = 'timezones supported by the `timezone set` command'
        else:
            query = query.replace(' ', '_')
            title = f'supported timezones that contain `{query}`'
        await paginate_search(ctx, title, pytz.all_timezones, query)


    @_timezone.command(name='set')
    async def set_timezone(self, ctx, *, timezone: str):
        """Sets your timezone for commands that need your time input
        
        If you don't set a timezone, those commands will assume you are using the UTC timezone.
        See the valid timezone options with the `timezone search` command, or by clicking here: <https://gist.github.com/wheelercj/86588a956b7912dfb24ec51d36c2f124>
        """
        timezone = await self.parse_timezone(timezone)
        await self.save_timezone(ctx, timezone)
        await ctx.send(f'Your timezone has been set to `{timezone}`')


    async def parse_timezone(self, timezone: str) -> str:
        """Validates and formats a timezone input"""
        try:
            return pytz.timezone(timezone).zone
        except (pytz.exceptions.InvalidTimeError, pytz.exceptions.UnknownTimeZoneError):
            raise commands.BadArgument('Invalid timezone. See the valid timezone options with the `timezone search` command, or by clicking here: <https://gist.github.com/wheelercj/86588a956b7912dfb24ec51d36c2f124>')
        except Exception as error:
            raise commands.BadArgument(f'Unable to set timezone because of {error = }')


    async def save_timezone(self, ctx, timezone: str) -> None:
        """Saves a timezone string to the database
        
        Assumes the timezone is validated and formatted.
        """
        await self.bot.db.execute('''
            INSERT INTO timezones
            (user_id, timezone)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE
            SET timezone = $2
            WHERE timezones.user_id = $1;
            ''', ctx.author.id, timezone)


    @_timezone.command(name='delete', aliases=['del'])
    async def delete_timezone(self, ctx):
        """Deletes your timezone setting
        
        If you don't have a timezone setting, time-related commands will assume you are using the UTC timezone.
        """
        record = await self.bot.db.fetchrow('''
            DELETE FROM timezones
            WHERE user_id = $1
            RETURNING *;
            ''', ctx.author.id)
        if record is not None:
            await ctx.send('Your timezone setting has been deleted. Commands that need your input about time will expect you to use the UTC timezone now.')
        else:
            await ctx.send('You do not have a timezone setting.')


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
            raise commands.UserInputError("The server's data is unavailable.")

        server = self.bot.get_guild(ctx.guild.id)
        bot_count = await self.get_bot_count(server)
        cat_count = len(server.categories)
        created = await create_relative_timestamp(server.created_at)

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
    

    async def get_bot_count(self, server: discord.Guild) -> int:
        """Counts the bots in the server"""
        return sum(m.bot for m in server.members)


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
        creation_timestamp = await create_relative_timestamp(member.created_at)
        join_timestamp = await create_relative_timestamp(member.joined_at)

        embed = discord.Embed()
        embed.add_field(name=f'{member.name}#{member.discriminator}\n\u2800',
            value=f'**display name:** {member.display_name}\n'
                + await self.get_whether_bot(member)
                + f'**account created:** {creation_timestamp}\n'
                + f'**joined server:** {join_timestamp}\n'
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
        _uptime = datetime.now(tz.utc) - self.bot.launch_time
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
        creation_timestamp = await create_relative_timestamp(role.created_at)
        if role.tags is not None:
            if role.tags.bot_id is not None:
                managing_bot = ctx.guild.get_member(role.tags.bot_id)

        embed = discord.Embed()
        embed.add_field(name='role info',
            value=f'name: {role.name}\n'
                + f'members: {len(role.members)}\n'
                + f'hierarcy position: {role.position}\n'
                + f'created: {creation_timestamp}\n'
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
            raise commands.BadArgument('Could not find the user or role.')

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
        