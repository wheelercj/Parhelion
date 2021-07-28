# external imports
import discord
from discord.ext import commands
import asyncio
import asyncpg
from typing import Dict, Any, Optional
import json


'''
    CREATE TABLE command_access_settings (
        id SERIAL PRIMARY KEY,
        cmd_name TEXT UNIQUE,
        cmd_settings JSONB NOT NULL 
            DEFAULT '{
                "global_users": {},
                "global_servers": {},
                "_global": NULL,
                "servers": {
                    "members": {},
                    "channels": {},
                    "roles": {},
                    "server": NULL
                }
            }'::jsonb
    );
'''


class ServerSettings:
    """The server settings for one command"""
    def __init__(self):
        self.members: Dict[str, bool] = dict()
        self.channels: Dict[str, bool] = dict()
        self.roles: Dict[str, bool] = dict()
        self.server: bool = None


class CmdSettings:
    """The global and server settings for one command"""
    def __init__(self):
        self.global_users: Dict[str, bool] = dict()
        self.global_servers: Dict[str, bool] = dict()
        self._global: bool = None
        self.servers: Dict[str, ServerSettings] = dict()


class CommandName(commands.Converter):
    """Converter to validate a string input of a command name
    
    Command aliases are not considered valid.
    """
    async def convert(self, ctx, argument):
        all_command_names = [x.name for x in ctx.bot.commands]
        if argument not in all_command_names:
            raise commands.BadArgument(f'Command "{argument}" not found.')
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
                pass
        
        raise commands.BadArgument(f'Channel "{argument}" not found.')


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task = bot.loop.create_task(self.load_settings())


    async def load_settings(self):
        try:
            records = await self.bot.db.fetch('''
                SELECT *
                FROM command_access_settings;
                ''')
            for r in records:
                self.bot.all_cmd_settings[r['cmd_name']] = json.loads(r['cmd_settings'])
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError) as error:
            print(f'{error = }')
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.load_settings())


    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner
        return True


    async def bot_check(self, ctx):
        """Checks if ctx.author has permission to use ctx.command"""
        # The order in which the settings are checked is important. Owner settings must be checked before the settings chosen by the mods/admin of ctx.guild, and within each of those two categories the settings must go from most specific to least specific.

        # Settings hierarchy and order:
        #     all_cmd_settings  # The settings for all commands.
        #         cmd_settings  # The settings for one command.
        #             owner_settings
        #                 global_users
        #                 global_servers
        #                 _global
        #             server_settings
        #                 members
        #                 channels
        #                 roles
        #                 server

        if await self.bot.is_owner(ctx.author):
            return True

        try:
            cmd = ctx.command.root_parent or ctx.command
            cmd_settings = self.bot.all_cmd_settings[cmd.name]

            # Check owner settings.
            owner_settings = [
                (cmd_settings.global_users, ctx.author.id),
                (cmd_settings.global_servers, ctx.guild.id),
                (cmd_settings._global, None)
            ]

            for category, ID in owner_settings:
                setting = await self.has_access(category, ID)
                if setting is not None:
                    return setting

            # Check the settings chosen by the mods/admin of ctx.guild.
            all_server_settings = cmd_settings.server[str(ctx.guild.id)]  # This must be after owner settings are checked because it might raise KeyError.
            # Gather the settings that don't include the roles ctx.author doesn't have.
            server_settings = [
                (all_server_settings.members, ctx.author.id),
                (all_server_settings.channels, ctx.channel.id)
            ]
            for role in ctx.author.roles[::-1]:
                server_settings.append((all_server_settings.roles, role.id))
            server_settings.append((all_server_settings.server, None))

            for c, ID in server_settings:
                setting = await self.has_access(c, ID)
                if setting is not None:
                    return setting
        except KeyError:
            pass
        # There are no settings for this command.
        return True


    async def has_access(self, setting_category: Any, ID: str = None) -> Optional[bool]:
        """Gets the setting for an object ID in a setting category"""
        if ID is None or ID == 'None':
            return setting_category
        else:
            try:
                return setting_category[ID]
            except KeyError:
                return None


    @commands.group(aliases=['set'], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def setting(self, ctx, command_name: CommandName):
        """Shows this server's settings for a command

        Some commands have extra requirements not listed in settings; for example, these setting commands require the user to have the 'manage guild' permission. _global settings can only be set and overridden by the bot owner. Please contact me in the support server if you believe there is a mistake.
        """
        view_setting_command = self.bot.get_command('setting view')
        await ctx.invoke(view_setting_command, command_name=command_name)


    @setting.command(name='view', aliases=['v'])
    @commands.has_guild_permissions(manage_guild=True)
    async def view_setting(self, ctx, command_name: CommandName):
        """An alias for `setting`"""
        try:
            s = self.bot.all_cmd_settings[command_name]
        except KeyError:
            await ctx.send(f'No settings found for the `{command_name}` command.')
            return

        embed = discord.Embed(title=f'`{command_name}` command settings')
        if s._global is not None:
            embed.add_field(name='global', value=s._global, inline=False)
        if len(s.global_servers):
            embed.add_field(name='global servers', value=s.global_servers, inline=False)
        if len(s.global_users):
            embed.add_field(name='global users', value=s.global_users, inline=False)

        try:
            ss = s.servers[str(ctx.guild.id)]

            if ss.server is not None:
                embed.add_field(name='server', value=ss.server, inline=False)
            if len(ss.roles):
                embed.add_field(name='server roles', value=ss.roles, inline=False)
            if len(ss.channels):
                embed.add_field(name='server channels', value=ss.channels, inline=False)
            if len(ss.members):
                embed.add_field(name='server members', value=ss.members, inline=False)
        except KeyError:
            pass

        await ctx.send(embed=embed)


    @setting.command(name='global', aliases=['g'])
    @commands.is_owner()
    async def global_cmd_access(self, ctx, on_or_off: bool, command_name: CommandName):
        """Manages absolute commands access globally

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.bot.all_cmd_settings[command_name]._global = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{_global}', $1::JSONB, TRUE)
            WHERE cmd_name = $2;
            """, setting_json, command_name)
        await ctx.send(f'New global setting: command `{command_name}` access: {on_or_off}.')


    @setting.command(name='global-server', aliases=['gs', 'globalserver'])
    @commands.is_owner()
    async def global_server_cmd_access(self, ctx, server: discord.Guild, on_or_off: bool, command_name: CommandName):
        """Manages absolute commands access for a server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.bot.all_cmd_settings[command_name].global_servers = {str(server.id): on_or_off}
        setting_json = json.dumps({server.id: on_or_off})
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{global_servers}', $1::JSONB, TRUE)
            WHERE cmd_name = $2;
            """, setting_json, command_name)
        await ctx.send(f'New setting: "{command_name}" {on_or_off} for server {server.name}.')


    @setting.command(name='global-user', aliases=['gu', 'globaluser'])
    @commands.is_owner()
    async def global_user_cmd_access(self, ctx, user: discord.User, on_or_off: bool, command_name: CommandName):
        """Manages absolute commands access for a user

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.bot.all_cmd_settings[command_name].global_users = {str(user.id): on_or_off}
        setting_json = json.dumps({user.id: on_or_off})
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{global_users}', $1::JSONB, TRUE)
            WHERE cmd_name = $2;
            """, setting_json, command_name)
        await ctx.send(f'New setting: "{command_name}" {on_or_off} for user {user.name}#{user.discriminator}.')


    @setting.command(name='server', aliases=['s'])
    @commands.has_guild_permissions(manage_guild=True)
    async def server_cmd_access(self, ctx, on_or_off: bool, command_name: CommandName):
        """Manages commands access for this server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.bot.all_cmd_settings[command_name].servers[str(ctx.guild.id)].server = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{servers, $1, server}', $2::JSONB, TRUE)
            WHERE cmd_name = $3;
            """, str(ctx.guild.id), setting_json, command_name)
        await ctx.send(f'New setting: "{command_name}" {on_or_off} for this server.')


    @setting.command(name='role', aliases=['r'])
    @commands.has_guild_permissions(manage_guild=True)
    async def role_cmd_access(self, ctx, role: discord.Role, on_or_off: bool, command_name: CommandName):
        """Manages commands access for a role in this server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.bot.all_cmd_settings[command_name].servers[str(ctx.guild.id)].roles[str(role.id)] = on_or_off
        setting_json = json.dumps({role.id: on_or_off})
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{servers, $1, roles}', $2::JSONB, TRUE)
            WHERE cmd_name = $3;
            """, str(ctx.guild.id), setting_json, command_name)
        await ctx.send(f'New setting: "{command_name}" {on_or_off} for role {role.name}.')


    @setting.command(name='channel', aliases=['c'])
    @commands.has_guild_permissions(manage_guild=True)
    async def channel_cmd_access(self, ctx, channel: Channel, on_or_off: bool, command_name: CommandName):
        """Manages commands access for a channel in this server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.bot.all_cmd_settings[command_name].servers[str(ctx.guild.id)].channels[str(channel.id)] = on_or_off
        setting_json = json.dumps({channel.id: on_or_off})
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{servers, $1, channels}', $2::JSONB, TRUE)
            WHERE cmd_name = $3;
            """, str(ctx.guild.id), setting_json, command_name)
        await ctx.send(f'New setting: "{command_name}" {on_or_off} for channel {channel.name}.')


    @setting.command(name='member', aliases=['m'])
    @commands.has_guild_permissions(manage_guild=True)
    async def member_cmd_access(self, ctx, member: discord.Member, on_or_off: bool, command_name: CommandName):
        """Manages commands access for a member of this server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.bot.all_cmd_settings[command_name].servers[str(ctx.guild.id)].members[str(member.id)] = on_or_off
        setting_json = json.dumps({member.id: on_or_off})
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{servers, $1, members}', $2::JSONB, TRUE)
            WHERE cmd_name = $3;
            """, str(ctx.guild.id), setting_json, command_name)
        await ctx.send(f'New setting: "{command_name}" {on_or_off} for member {member.name}.')


    async def set_default_settings(self, ctx, command_name: str) -> None:
        """Sets default settings for a command if and only if it has no settings yet
        
        The defaults are set in both this program and in the database.
        """
        self.bot.all_cmd_settings.setdefault(command_name, CmdSettings())
        self.bot.all_cmd_settings[command_name].servers.setdefault(str(ctx.guild.id), ServerSettings())
        await self.bot.db.execute("""
            INSERT INTO command_access_settings
            (cmd_name)
            VALUES ($1)
            ON CONFLICT (cmd_name)
            DO NOTHING;
            """, command_name)


def setup(bot):
    bot.add_cog(Settings(bot))
