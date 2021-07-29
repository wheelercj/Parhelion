# external imports
import discord
from discord.ext import commands
import asyncio
import asyncpg
from typing import Any, Optional, Dict, Callable
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


def ooo(boolean: bool) -> str:
    """Returns either 'on' or 'off'"""
    if boolean:
        return 'on'
    return 'off'


def emoji(boolean: bool) -> str:
    """Returns either '✅' or '❌'"""
    if boolean:
        return '✅'
    return '❌'


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
        self.all_cmd_settings: Dict[str, dict] = dict()
        # Command access settings hierarchy, order, and types:
        #     all_cmd_settings: Dict[str, dict]  # The settings for all commands.
        #         'cmd_settings': Dict[str, Union[dict, bool]]  # The settings for one command.
        #             'global_users': Dict[str, bool]
        #             'global_servers': Dict[str, bool]
        #             '_global': bool
        #             'server_settings': Dict[str, Union[dict, bool]]
        #                 'members': Dict[str, bool]
        #                 'channels': Dict[str, bool]
        #                 'roles': Dict[str, bool]
        #                 'server': bool

    # The default global and server settings for one command.
        self.default_cmd_settings = {
            'global_users': dict(),
            'global_servers': dict(),
            '_global': None,
            'servers': dict()
        }

    # The default server settings for one command.
        self.default_server_settings = {
            'members': dict(),
            'channels': dict(),
            'roles': dict(),
            'server': None
        }


    async def load_settings(self):
        await self.bot.wait_until_ready()
        while self.bot.db is None:
            print('Error: self.bot.db is None')
            return
        print('  Loading settings')
        try:
            records = await self.bot.db.fetch('''
                SELECT *
                FROM command_access_settings;
                ''')
            if records is None or not len(records):
                print('  No settings found')
            for r in records:
                self.all_cmd_settings[r['cmd_name']] = json.loads(r['cmd_settings'])
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
        if await self.bot.is_owner(ctx.author):
            return True

        try:
            cmd = ctx.command.root_parent or ctx.command
            cmd_settings = self.all_cmd_settings[cmd.name]

            # Check owner settings.
            owner_settings = [
                (cmd_settings['global_users'], ctx.author.id),
                (cmd_settings['global_servers'], ctx.guild.id),
                (cmd_settings['_global'], None)
            ]

            for category, ID in owner_settings:
                setting = await self.has_access(category, ID)
                if setting is not None:
                    return setting

            # Check the settings chosen by the mods/admin of ctx.guild.
            all_server_settings = cmd_settings['server'][str(ctx.guild.id)]  # This must be after owner settings are checked because it might raise KeyError.
            # Gather the settings that don't include the roles ctx.author doesn't have.
            server_settings = [
                (all_server_settings['members'], ctx.author.id),
                (all_server_settings['channels'], ctx.channel.id)
            ]
            for role in ctx.author.roles[::-1]:
                server_settings.append((all_server_settings['roles'], role.id))
            server_settings.append((all_server_settings['server'], None))

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
            s = self.all_cmd_settings[command_name]
        except KeyError:
            await ctx.send(f'No settings found for the `{command_name}` command.')
            return

        embed = discord.Embed(title=f'`{command_name}` command settings')
        if s['_global'] is not None:
            embed.add_field(name='global', value=emoji(s['_global']), inline=False)
        if len(s['global_servers']):
            content = await self.get_settings_message(s, 'global_servers', self.bot.get_guild)
            embed.add_field(name='global servers', value=content, inline=False)
        if len(s['global_users']):
            content = await self.get_settings_message(s, 'global_users', self.bot.get_user)
            embed.add_field(name='global users', value=content, inline=False)

        try:
            ss = s['servers'][str(ctx.guild.id)]
            server = self.bot.get_guild(ctx.guild.id)

            if ss['server'] is not None:
                embed.add_field(name='server', value=emoji(ss['server']), inline=False)
            if len(ss['roles']):
                content = await self.get_settings_message(ss, 'roles', server.get_role)
                embed.add_field(name='server roles', value=content, inline=False)
            if len(ss['channels']):
                content = await self.get_settings_message(ss, 'channels', server.get_channel)
                embed.add_field(name='server channels', value=content, inline=False)
            if len(ss['members']):
                content = await self.get_settings_message(ss, 'members', server.get_member)
                embed.add_field(name='server members', value=content, inline=False)
        except KeyError:
            pass

        await ctx.send(embed=embed)


    @setting.command(name='global', aliases=['g'])
    @commands.is_owner()
    async def global_cmd_access(self, ctx, command_name: CommandName, on_or_off: bool):
        """Manages absolute commands access globally

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['_global'] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{_global}', $1::JSONB, TRUE)
            WHERE cmd_name = $2;
            """, setting_json, command_name)
        await ctx.send(f'New global setting: command `{command_name}` {ooo(on_or_off)}.')


    @setting.command(name='global-server', aliases=['gs', 'globalserver'])
    @commands.is_owner()
    async def global_server_cmd_access(self, ctx, server: discord.Guild, command_name: CommandName, on_or_off: bool):
        """Manages absolute commands access for a server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['global_servers'][str(server.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
            WHERE cmd_name = $4;
            """, 'global_servers', str(server.id), setting_json, command_name)
        await ctx.send(f'New global setting: `{command_name}` {ooo(on_or_off)} for server {server.name}.')


    @setting.command(name='global-user', aliases=['gu', 'globaluser'])
    @commands.is_owner()
    async def global_user_cmd_access(self, ctx, user: discord.User, command_name: CommandName, on_or_off: bool):
        """Manages absolute commands access for a user

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['global_users'][str(user.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
            WHERE cmd_name = $4;
            """, 'global_users', str(user.id), setting_json, command_name)
        await ctx.send(f'New global setting: `{command_name}` {ooo(on_or_off)} for user {user.name}#{user.discriminator}.')


    @setting.command(name='server', aliases=['s'])
    @commands.has_guild_permissions(manage_guild=True)
    async def server_cmd_access(self, ctx, command_name: CommandName, on_or_off: bool):
        """Manages commands access for this server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['server'] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3]::TEXT[], $4::JSONB, TRUE)
            WHERE cmd_name = $5;
            """, 'servers', str(ctx.guild.id), 'server', setting_json, command_name)
        await ctx.send(f'New setting: `{command_name}` {ooo(on_or_off)} for this server.')


    @setting.command(name='role', aliases=['r'])
    @commands.has_guild_permissions(manage_guild=True)
    async def role_cmd_access(self, ctx, role: discord.Role, command_name: CommandName, on_or_off: bool):
        """Manages commands access for a role in this server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['roles'][str(role.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
            WHERE cmd_name = $6;
            """, 'servers', str(ctx.guild.id), 'roles', str(role.id), setting_json, command_name)
        await ctx.send(f'New setting: `{command_name}` {ooo(on_or_off)} for role {role.name}.')


    @setting.command(name='channel', aliases=['c'])
    @commands.has_guild_permissions(manage_guild=True)
    async def channel_cmd_access(self, ctx, channel: discord.TextChannel, command_name: CommandName, on_or_off: bool):
        """Manages commands access for a text channel in this server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['channels'][str(channel.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
            WHERE cmd_name = $6;
            """, 'servers', str(ctx.guild.id), 'channels', str(channel.id), setting_json, command_name)
        await ctx.send(f'New setting: `{command_name}` {ooo(on_or_off)} for channel {channel.name}.')


    @setting.command(name='member', aliases=['m'])
    @commands.has_guild_permissions(manage_guild=True)
    async def member_cmd_access(self, ctx, member: discord.Member, command_name: CommandName, on_or_off: bool):
        """Manages commands access for a member of this server

        The command name must not contain any aliases.
        """
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['members'][str(member.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
            WHERE cmd_name = $6;
            """, 'servers', str(ctx.guild.id), 'members', str(member.id), setting_json, command_name)
        await ctx.send(f'New setting: `{command_name}` {ooo(on_or_off)} for member {member.name}.')


    async def set_default_settings(self, ctx, command_name: str) -> None:
        """Sets default settings for a command if and only if it has no settings yet
        
        The defaults are set in both this program and in the database.
        """
        self.all_cmd_settings.setdefault(command_name, self.default_cmd_settings)
        self.all_cmd_settings[command_name]['servers'].setdefault(str(ctx.guild.id), self.default_server_settings)
        await self.bot.db.execute("""
            INSERT INTO command_access_settings
            (cmd_name)
            VALUES ($1)
            ON CONFLICT (cmd_name)
            DO NOTHING;
            """, command_name)


    async def get_settings_message(self, dictionary: dict, key: str, get_function: Callable) -> str:
        """Creates a str listing whether each element of dict[key] has access"""
        content = ''
        for ID_str, boolean in dictionary[key].items():
            name = get_function(int(ID_str))
            content += f'{emoji(boolean)} {name}\n'

        return content


def setup(bot):
    bot.add_cog(Settings(bot))
