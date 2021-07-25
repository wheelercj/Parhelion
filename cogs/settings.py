# external imports
import discord
from discord.ext import commands
import asyncpg


'''
    CREATE TABLE command_access_settings (
        id SERIAL PRIMARY KEY,
        command_name TEXT,
        access TEXT CONSTRAINT valid_access CHECK (access = ANY('{"allow", "deny", "limit", "owner-allow", "owner-deny", "owner-limit"}')),
        parent_server_id BIGINT,  -- this is null if object_type is 'global' or 'server', and may be null if it's 'user'
        parent_channel_id BIGINT,  -- this is null if object_type is anything but 'user', and may be null regardless
        object_type TEXT CONSTRAINT valid_type CHECK (object_type = ANY('{"global", "server", "role", "channel", "user"}')),
        object_ids BIGINT[],  -- this is [null] if and only if object_type is 'global'
        UNIQUE (command_name, access, parent_server_id, parent_channel_id, object_type)
    );
'''
# Each command may have multiple rows.


class Access(commands.Converter):
    """Converter to validate a string input for whether to grant access to a command
    
    Valid inputs: 'allow', 'deny', or 'limit'.
    """
    async def convert(self, ctx, argument):
        argument = argument.strip('"').lower()
        if argument not in ('allow', 'deny', 'limit'):
            raise commands.BadArgument('Please enter either "allow", "deny", or "limit" before the command that you are changing the settings of.')
        return argument


class ObjectType(commands.Converter):
    """Converter to validate a string argument to be either 'global', 'server', 'role', 'channel', or 'user'

    This is not intended to be used for command arguments.
    """
    async def convert(self, ctx, argument):
        argument = argument.strip('"').lower()
        if argument not in ('global', 'server', 'role', 'channel', 'user'):
            raise ValueError('Please use either "global", "server", "role", "channel", or "user".')
        return argument


class CommandName(commands.Converter):
    """Converter to validate a string input of a command name
    
    Command aliases are not considered valid.
    """
    async def convert(self, ctx, argument):
        all_command_names = [x.name for x in ctx.bot.commands]
        entered = argument.split(' ')
        for cmd_name in entered:
            if cmd_name not in all_command_names:
                raise commands.BadArgument(f'Command "{cmd_name}" not found.')
        return argument


class Channel(commands.Converter):
    """Converter for all types of Discord channels"""
    async def convert(self, ctx, argument):
        converters = [
            commands.TextChannelConverter,
            commands.VoiceChannelConverter,
            commands.StageChannelConverter,
            commands.StoreChannelConverter,
            commands.CategoryChannelConverter,
        ]

        for converter in converters:
            try:
                channel = await converter().convert(ctx, argument)
                return channel
            except commands.ChannelNotFound:
                if converter == converters[-1]:
                    raise commands.BadArgument(f'Channel "{argument}" not found.')


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner
        return True


    @commands.group(aliases=['set'], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def setting(self, ctx, *, command_name: CommandName):
        """Shows this server's settings for a command
        
        Some commands have extra requirements not listed in settings; for example, these setting commands require the user to have the 'manage guild' permission. Global settings and settings with descriptions that start with 'owner' can only be set and overridden by the bot owner. Please contact me in the support server if you believe there is a mistake.
        """
        view_setting_command = self.bot.get_command('setting view')
        await ctx.invoke(view_setting_command, command_name=command_name)


    @setting.command(name='view', aliases=['v'])
    @commands.has_guild_permissions(manage_guild=True)
    async def view_setting(self, ctx, *, command_name: CommandName):
        """An alias for `setting`"""
        records = await self.bot.db.fetch("""
            SELECT *
            FROM command_access_settings
            WHERE command_name = $1
                AND (parent_server_id = $2
                    OR object_type = 'global'
                    OR (object_type = 'server'
                        AND $2 = ANY(object_ids)));
            """, command_name, ctx.guild.id)

        if records is None or not len(records):
            await ctx.send(f'No settings found for "{command_name}".')
            return

        content = ''
        for r in records:
            content += f'\n\nID: {r["id"]}\n' \
                + r['access'] + ' use '
            if r['object_type'] == 'global':
                content += 'globally'
            else:
                if r['parent_channel_id']:
                    content += f'in channel {r["parent_channel_id"]}\n'
                if r['object_type'] == 'server':
                    content += 'by this server'
                else:
                    content += 'by ' + r['object_type'] + 's:'
                    for ID in r['object_ids']:
                        content += f'\n {ID}'

        embed = discord.Embed()
        embed.add_field(name=f'"{command_name}" settings', value=content)
        await ctx.send(embed=embed)


    @setting.command(name='global', aliases=['g'])
    @commands.is_owner()
    async def global_cmd_access(self, ctx, access: Access, *, command_name: CommandName):
        """Manages absolute commands access globally

        For the `access` argument, you may enter "allow", "deny", or "limit". Limited access is the same as denied access, except that it allows exceptions. The command name must not contain any aliases.
        """
        access = 'owner-' + access
        await self.save_cmd_setting('global', None, access, command_name)
        await ctx.send(f'New setting: {access} use of "{command_name}" globally.')


    @setting.command(name='a-server', aliases=['as'])
    @commands.is_owner()
    async def a_server_cmd_access(self, ctx, server: discord.Guild, access: Access, *, command_name: CommandName):
        """Manages absolute commands access for a server

        For the `access` argument, you may enter "allow" or "deny". The command name must not contain any aliases.
        """
        access = 'owner-' + access
        if access == "owner-limit":
            raise commands.BadArgument('Please enter either "allow" or "deny" before the command that you are changing the settings of.')
        await self.save_cmd_setting('server', server.id, access, command_name)
        await ctx.send(f'New setting: {access} use of "{command_name}" for server {server.name}.')


    @setting.command(name='server', aliases=['s'])
    @commands.has_guild_permissions(manage_guild=True)
    async def server_cmd_access(self, ctx, access: Access, *, command_name: CommandName):
        """Manages commands access for this server

        For the `access` argument, you may enter "allow", "deny", or "limit". Limited access is the same as denied access, except that it allows exceptions. The command name must not contain any aliases.
        """
        await self.save_cmd_setting('server', ctx.guild.id, access, command_name)
        await ctx.send(f'New setting: {access} use of "{command_name}" for this server.')


    @setting.command(name='role', aliases=['r'])
    @commands.has_guild_permissions(manage_guild=True)
    async def role_cmd_access(self, ctx, role: discord.Role, access: Access, *, command_name: CommandName):
        """Manages commands access for a role in this server

        For the `access` argument, you may enter "allow", "deny", or "limit". Limited access is the same as denied access, except that it allows exceptions. The command name must not contain any aliases.
        """
        await self.save_cmd_setting('server', role.id, access, command_name, ctx.guild.id)
        await ctx.send(f'New setting: {access} use of "{command_name}" for server {role.name}.')


    @setting.command(name='channel', aliases=['c'])
    @commands.has_guild_permissions(manage_guild=True)
    async def channel_cmd_access(self, ctx, channel: Channel, access: Access, *, command_name: CommandName):
        """Manages commands access for a channel in this server

        For the `access` argument, you may enter "allow", "deny", or "limit". Limited access is the same as denied access, except that it allows exceptions. The command name must not contain any aliases.
        """
        await self.save_cmd_setting('channel', channel.id, access, command_name, ctx.guild.id)
        await ctx.send(f'New setting: {access} use of "{command_name}" for channel {channel.name}.')


    @setting.command(name='channel-member', aliases=['cm', 'channelmember'])
    @commands.has_guild_permissions(manage_guild=True)
    async def channel_member_cmd_access(self, ctx, channel: Channel, member: discord.Member, access: Access, *, command_name: CommandName):
        """Manages commands access for a member for a channel in this server

        For the `access` argument, you may enter "allow", "deny", or "limit". Limited access is the same as denied access, except that it allows exceptions. The command name must not contain any aliases.
        """
        await self.save_cmd_setting('user', member.id, access, command_name, ctx.guild.id, channel.id)
        await ctx.send(f'New setting: {access} use of "{command_name}" for member {member.display_name} in channel {channel.name}.')


    @setting.command(name='member', aliases=['m'])
    @commands.has_guild_permissions(manage_guild=True)
    async def member_cmd_access(self, ctx, member: discord.Member, access: Access, *, command_name: CommandName):
        """Manages commands access for a member of this server

        For the `access` argument, you may enter "allow", "deny", or "limit". Limited access is the same as denied access, except that it allows exceptions. The command name must not contain any aliases.
        """
        await self.save_cmd_setting('user', member.id, access, command_name, ctx.guild.id)
        await ctx.send(f'New setting: {access} use of "{command_name}" for member {member.display_name}.')


    @setting.command(name='user', aliases=['u'])
    @commands.is_owner()
    async def user_cmd_access(self, ctx, user: discord.User, access: Access, *, command_name: CommandName):
        """Manages absolute commands access for a user

        For the `access` argument, you may enter "allow" or "deny". The command name must not contain any aliases.
        """
        access = 'owner-' + access
        if access == "owner-limit":
            raise commands.BadArgument('Please enter either "allow" or "deny" before the command that you are changing the settings of.')
        await self.save_cmd_setting('user', user.id, access, command_name)
        await ctx.send(f'New setting: {access} use of "{command_name}" for user {user.name}#{user.discriminator}.')


    async def save_cmd_setting(self, object_type: ObjectType, object_id: int, access: Access, command_name: CommandName, parent_server_id: int = None, parent_channel_id: int = None) -> None:
        """Saves a new command access setting to the database
        
        object_id should be None if object_type is 'global'. 
        parent_server_id should be None if object_type is 'global' or 'server', and may be None if it's 'user'. 
        parent_channel_id should be None if object_type is anything but 'user', and may be None regardless.
        """
        try:
            # Create a new row for this setting, but only if one does not
            # already exist for this type of setting.
            await self.bot.db.execute("""
                INSERT INTO command_access_settings
                (command_name, access, object_type, object_ids, parent_server_id, parent_channel_id)
                VALUES ($1, $2, $3, $4, $5, $6);
                """, command_name, access, object_type, [object_id], parent_server_id, parent_channel_id)
        except asyncpg.exceptions.UniqueViolationError:
            # If a row for this type of setting already exists,
            # update the existing row.
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET object_ids = object_ids || $1
                WHERE command_name = $2
                    AND access = $3
                    AND object_type = $4
                    AND parent_server_id = $5
                    AND parent_channel_id = $6
                    AND $1 != ANY(object_ids);
                """, object_id, command_name, access, object_type, parent_server_id, parent_channel_id)


def setup(bot):
    bot.add_cog(Settings(bot))
