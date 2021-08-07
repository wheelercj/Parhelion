# external imports
import discord
from discord.ext import commands
import asyncpg
from typing import List, Tuple, Any, Optional, Dict, Callable
import json

# internal imports
from cogs.utils.paginator import Paginator


'''
    CREATE TABLE command_access_settings (
        id SERIAL PRIMARY KEY,
        cmd_name TEXT UNIQUE,
        cmd_settings JSONB NOT NULL 
            DEFAULT '{
                "global_users": {},
                "global_servers": {},
                "_global": null,
                "servers": {}
            }'::jsonb
    );
'''


class CommandName(commands.Converter):
    """Converter to validate a string input of a command name
    
    Command aliases and subcommands are not considered valid by this converter.
    """
    async def convert(self, ctx, argument):
        if ' ' in argument:
            raise commands.BadArgument('Currently, settings cannot be applied to subcommands')
            # Removing this would not be enough to support subcommands because the list below contains only root commands.
        all_command_names = [x.name for x in ctx.bot.commands]
        if argument not in all_command_names:
            raise commands.BadArgument(f'Command `{argument}` not found. If you are trying to choose a setting for a command alias, note that the settings commands do not work on aliases.')
        return argument


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task = bot.loop.create_task(self.load_settings())
        self.all_cmd_settings: Dict[str, dict] = dict()
        """
        Command access settings hierarchy, order, and types:
            self.all_cmd_settings = {
                f'{command_name}': {
                    'global_users': {
                        f'{user_id}': bool
                    },
                    'global_servers': {
                        f'{server_id}': bool
                    },
                    '_global': bool,
                    'servers': {
                        f'{server_id}': {
                            'members': {
                                f'{member_id}': bool
                            },
                            'channels': {
                                f'{channel_id}': bool
                            },
                            'roles': {
                                f'{role_id}': bool
                            },
                            'server': bool
                        }
                    }
                }
            }
        """

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

        self.default_server_settings_json = json.dumps(self.default_server_settings)


    async def load_settings(self):
        await self.bot.wait_until_ready()
        try:
            records = await self.bot.db.fetch('''
                SELECT *
                FROM command_access_settings;
                ''')
            for r in records:
                self.all_cmd_settings[r['cmd_name']] = json.loads(r['cmd_settings'])
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError) as error:
            print(f'{error = }')
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.load_settings())


    async def bot_check(self, ctx):
        """Checks if the settings allow ctx.command to be used by ctx"""
        # The order in which the settings are checked is important. Owner settings must be checked before the settings chosen by the mods/admin of ctx.guild, and within each of those two categories the settings must go from most specific to least specific.
        if await self.bot.is_owner(ctx.author):
            return True

        try:
            cmd = ctx.command.root_parent or ctx.command
            cmd_settings = self.all_cmd_settings[cmd.name]

            # Check owner settings.
            global_settings = [(cmd_settings['global_users'], ctx.author.id)]
            if ctx.guild:
                global_settings.append((cmd_settings['global_servers'], ctx.guild.id))
            owner_allow = False
            if await self.check_categories(ctx, global_settings):
                owner_allow = True  # Instead of returning True here, allow servers to disable commands that are enabled in global-server and/or global-user settings.

            global_settings = [(cmd_settings['_global'], None)]
            try:
                if await self.check_categories(ctx, global_settings):
                    return True
            except commands.CheckFailure:
                if not owner_allow:
                    raise

            # Check the settings chosen by the mods/admin of ctx.guild.
            if ctx.guild:
                all_server_settings = cmd_settings['server'][str(ctx.guild.id)]  # This must be after owner settings are checked because it might raise KeyError.
                # Gather the settings that don't include the roles ctx.author doesn't have.
                server_settings = [
                    (all_server_settings['members'], ctx.author.id),
                    (all_server_settings['channels'], ctx.channel.id)
                ]
                for role in ctx.author.roles[::-1]:  # Reversed to start with the most important roles.
                    server_settings.append((all_server_settings['roles'], role.id))
                server_settings.append((all_server_settings['server'], None))

                if await self.check_categories(ctx, server_settings):
                    return True
        except KeyError:
            pass
        # There are no relevant settings for this command.
        return True


    async def check_categories(self, ctx, settings_categories: List[Tuple]) -> Optional[bool]:
        """Determines whether to grant access if there is at least one setting"""
        for category, ID in settings_categories:
            setting = await self.check_category(category, ID)
            if setting is not None:
                if setting:
                    return True
                raise commands.CheckFailure(f'The `{ctx.invoked_with}` command has been disabled in this bot\'s command settings for some servers, roles, channels, and/or users.')


    async def check_category(self, setting_category: Any, ID: Optional[int]) -> Optional[bool]:
        """Gets the setting for an object ID in a setting category"""
        if ID is None:
            return setting_category
        try:
            return setting_category[str(ID)]
        except KeyError:
            return None


#########################
# setting command group #
#########################


    @commands.group(name='set', aliases=['setting'], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def setting(self, ctx, command_name: CommandName = None):
        """Shows this server's settings for a command

        Commands can be enabled or disabled for the entire server, or for a role, channel, or member. If a setting is not chosen for a command, most commands are enabled by default for most users. Some commands have extra requirements not listed in settings. For example, these setting commands require the user to have the "manage server" permission. 
        
        When creating or deleting a setting for a command, use the command's full name (not an alias). For commands that have subcommands (such as the `remind` commands), settings can only be applied to the root command. If two or more settings conflict, the most specific one will be used (except that some global settings cannot be overridden by server settings; global settings can only be set by the bot owner). For example, if the `remind` command is disabled for the server but enabled for one of its channels, then that command can only be used in that channel.
        """
        if command_name:
            view_setting_command = self.bot.get_command('setting view')
            await ctx.invoke(view_setting_command, command_name=command_name)
        else:
            await ctx.send_help('setting')


    @setting.command(name='rename')
    @commands.is_owner()
    async def rename_command(self, ctx, old_command_name: str, current_command_name: CommandName):
        """Changes a command's name in the settings database and dictionary

        Use this command each time a command is renamed in the code.
        """
        await self.bot.db.execute('''
            UPDATE command_access_settings
            SET cmd_name = $1
            WHERE cmd_name = $2;
            ''', current_command_name, old_command_name)
        try:
            self.all_cmd_settings[current_command_name] = self.all_cmd_settings.pop(old_command_name)
            await ctx.send('Command renamed in the settings database and dictionary.')
        except KeyError:
            await ctx.send('Command not found.')


    @setting.command(name='view', aliases=['v'])
    @commands.has_guild_permissions(manage_guild=True)
    async def view_settings(self, ctx, command_name: CommandName):
        """An alias for `setting`; shows the settings for a command"""
        try:
            settings = self.all_cmd_settings[command_name]
        except KeyError:
            await ctx.send(f'No settings found for the `{command_name}` command.')
            return

        embed = discord.Embed(title=f'`{command_name}` command settings')

        if settings['_global'] is not None:
            allowed = '✅' if settings['_global'] else '❌'
            embed.add_field(name='global', value=allowed, inline=False)

        # Show ctx.guild.name and its setting if it has a setting.
        try:
            allowed = settings['global_servers'][str(ctx.guild.id)]
            setting_dict = {str(ctx.guild.id): allowed}
            content = await self.get_settings_message(setting_dict, self.bot.get_guild)
            embed.add_field(name='global servers', value=content, inline=False)
        except KeyError:
            pass

        # For users in ctx.guild with a global setting, list their names and settings.
        members = dict()
        for user_id in settings['global_users']:
            member = ctx.guild.get_member(user_id)
            if member is None:
                continue
            members[user_id] = settings['global_users'][user_id]
        if len(settings['global_users']):
            content = await self.get_settings_message(members, self.bot.get_user)
            embed.add_field(name='global users', value=content, inline=False)

        # Show the settings chosen by ctx.guild.
        try:
            s_settings = settings['servers'][str(ctx.guild.id)]
            server = self.bot.get_guild(ctx.guild.id)

            if s_settings['server'] is not None:
                allowed = '✅' if settings['server'] else '❌'
                embed.add_field(name='server', value=allowed, inline=False)
            if len(s_settings['roles']):
                content = await self.get_settings_message(s_settings['roles'], server.get_role)
                embed.add_field(name='server roles', value=content, inline=False)
            if len(s_settings['channels']):
                content = await self.get_settings_message(s_settings['channels'], server.get_channel)
                embed.add_field(name='server channels', value=content, inline=False)
            if len(s_settings['members']):
                content = await self.get_settings_message(s_settings['members'], server.get_member)
                embed.add_field(name='server members', value=content, inline=False)
        except KeyError:
            pass

        await ctx.send(embed=embed)


    @setting.command(name='global', aliases=['g'])
    @commands.is_owner()
    async def global_cmd_setting(self, ctx, on_or_off: bool, command_name: CommandName):
        """Manages absolute commands access globally"""
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['_global'] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{_global}', $1::JSONB, TRUE)
            WHERE cmd_name = $2;
            """, setting_json, command_name)
        on_or_off = 'enabled' if on_or_off else 'disabled'
        await ctx.send(f'New global setting: command `{command_name}` {on_or_off}.')


    @setting.command(name='global-server', aliases=['gs', 'globalserver'])
    @commands.is_owner()
    async def global_server_cmd_setting(self, ctx, server: discord.Guild, on_or_off: bool, command_name: CommandName):
        """Manages absolute commands access for a server"""
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['global_servers'][str(server.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
            WHERE cmd_name = $4;
            """, 'global_servers', str(server.id), setting_json, command_name)
        on_or_off = 'enabled' if on_or_off else 'disabled'
        await ctx.send(f'New global setting: `{command_name}` {on_or_off} for server: {server.name}.')


    @setting.command(name='global-user', aliases=['gu', 'globaluser'])
    @commands.is_owner()
    async def global_user_cmd_setting(self, ctx, user: discord.User, on_or_off: bool, command_name: CommandName):
        """Manages absolute commands access for a user"""
        await self.set_default_settings(ctx, command_name)
        self.all_cmd_settings[command_name]['global_users'][str(user.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
            WHERE cmd_name = $4;
            """, 'global_users', str(user.id), setting_json, command_name)
        on_or_off = 'enabled' if on_or_off else 'disabled'
        await ctx.send(f'New global setting: `{command_name}` {on_or_off} for user: {user.name}#{user.discriminator}.')


    @setting.command(name='server', aliases=['s'])
    @commands.has_guild_permissions(manage_guild=True)
    async def server_cmd_setting(self, ctx, on_or_off: bool, command_name: CommandName):
        """Manages commands access for this server"""
        await self.set_default_settings(ctx, command_name, ctx.guild.id)
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['server'] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3]::TEXT[], $4::JSONB, TRUE)
            WHERE cmd_name = $5;
            """, 'servers', str(ctx.guild.id), 'server', setting_json, command_name)
        on_or_off = 'enabled' if on_or_off else 'disabled'
        await ctx.send(f'New setting: `{command_name}` {on_or_off} for this server.')


    @setting.command(name='role', aliases=['r'])
    @commands.has_guild_permissions(manage_guild=True)
    async def role_cmd_setting(self, ctx, role: discord.Role, on_or_off: bool, command_name: CommandName):
        """Manages commands access for a role in this server"""
        await self.set_default_settings(ctx, command_name, ctx.guild.id)
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['roles'][str(role.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
            WHERE cmd_name = $6;
            """, 'servers', str(ctx.guild.id), 'roles', str(role.id), setting_json, command_name)
        on_or_off = 'enabled' if on_or_off else 'disabled'
        await ctx.send(f'New setting: `{command_name}` {on_or_off} for role: {role.name}.')


    @setting.command(name='channel', aliases=['c'])
    @commands.has_guild_permissions(manage_guild=True)
    async def channel_cmd_setting(self, ctx, channel: discord.TextChannel, on_or_off: bool, command_name: CommandName):
        """Manages commands access for a text channel in this server"""
        await self.set_default_settings(ctx, command_name, ctx.guild.id)
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['channels'][str(channel.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
            WHERE cmd_name = $6;
            """, 'servers', str(ctx.guild.id), 'channels', str(channel.id), setting_json, command_name)
        on_or_off = 'enabled' if on_or_off else 'disabled'
        await ctx.send(f'New setting: `{command_name}` {on_or_off} for channel: {channel.name}.')


    @setting.command(name='member', aliases=['m'])
    @commands.has_guild_permissions(manage_guild=True)
    async def member_cmd_setting(self, ctx, member: discord.Member, on_or_off: bool, command_name: CommandName):
        """Manages commands access for a member of this server"""
        await self.set_default_settings(ctx, command_name, ctx.guild.id)
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['members'][str(member.id)] = on_or_off
        setting_json = json.dumps(on_or_off)
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
            WHERE cmd_name = $6;
            """, 'servers', str(ctx.guild.id), 'members', str(member.id), setting_json, command_name)
        on_or_off = 'enabled' if on_or_off else 'disabled'
        await ctx.send(f'New setting: `{command_name}` {on_or_off} for member: {member.name}.')


################################
# delete_setting command group #
################################


    @setting.group(name='delete', aliases=['del'], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_setting(self, ctx):
        """A group of commands for deleting command settings"""
        await ctx.send_help('setting delete')


    @delete_setting.command(name='global-all', aliases=['globalall'])
    @commands.is_owner()
    async def delete_all_global_cmd_settings(self, ctx, command_name: CommandName):
        """Deletes all settings for a command"""
        try:
            del self.all_cmd_settings[command_name]
            await self.bot.db.execute("""
                DELETE FROM command_access_settings
                WHERE cmd_name = $1;
                """, command_name)
            await ctx.send(f'Deleted all setting for command `{command_name}`, including the global settings.')
        except KeyError:
            await ctx.send('No settings found.')


    @delete_setting.command(name='all')
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_all_server_cmd_settings(self, ctx, command_name: CommandName):
        """Deletes all of this server's settings for a command"""
        try:
            del self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET cmd_settings = cmd_settings #- ARRAY[$1, $2]::TEXT[]
                WHERE cmd_name = $3;
                """, 'servers', str(ctx.guild.id), command_name)
            await ctx.send(f'Deleted all server setting for command `{command_name}`.')
        except KeyError:
            await ctx.send('No settings found.')


    @delete_setting.command(name='global', aliases=['g'])
    @commands.is_owner()
    async def delete_global_cmd_setting(self, ctx, command_name: CommandName):
        """Deletes a global command setting"""
        self.all_cmd_settings[command_name]['_global'] = None
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, '{_global}', $1::JSONB, TRUE)
            WHERE cmd_name = $2;
            """, 'null', command_name)
        await ctx.send(f'Deleted global setting for command `{command_name}`.')


    @delete_setting.command(name='global-server', aliases=['gs', 'globalserver'])
    @commands.is_owner()
    async def delete_global_server_cmd_setting(self, ctx, server: discord.Guild, command_name: CommandName):
        """Deletes the global setting for a server's access to a command"""
        try:
            del self.all_cmd_settings[command_name]['global_servers'][str(server.id)]
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET cmd_settings = cmd_settings #- ARRAY[$1, $2]::TEXT[]
                WHERE cmd_name = $3;
                """, 'global_servers', str(server.id), command_name)
            await ctx.send(f'Deleted global setting for command `{command_name}` for server: {server.name}.')
        except KeyError:
            await ctx.send('No settings found.')


    @delete_setting.command(name='global-user', aliases=['gu', 'globaluser'])
    @commands.is_owner()
    async def delete_global_user_cmd_setting(self, ctx, user: discord.User, command_name: CommandName):
        """Deletes the global setting for a user's access to a command"""
        try:
            del self.all_cmd_settings[command_name]['global_users'][str(user.id)]
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET cmd_settings = cmd_settings #- ARRAY[$1, $2]::TEXT[]
                WHERE cmd_name = $3;
                """, 'global_users', str(user.id), command_name)
            await ctx.send(f'Deleted global setting for command `{command_name}` for user: {user.name}#{user.discriminator}.')
        except KeyError:
            await ctx.send('No settings found.')


    @delete_setting.command(name='server', aliases=['s'])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_server_cmd_setting(self, ctx, command_name: CommandName):
        """Deletes this server's overall setting for a command"""
        self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['server'] = None
        await self.bot.db.execute("""
            UPDATE command_access_settings
            SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3]::TEXT[], $4::JSONB, TRUE)
            WHERE cmd_name = $5;
            """, 'servers', str(ctx.guild.id), 'server', 'null', command_name)
        await ctx.send(f'Deleted setting for command `{command_name}` for this server.')


    @delete_setting.command(name='role', aliases=['r'])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_role_cmd_setting(self, ctx, role: discord.Role, command_name: CommandName):
        """Deletes the setting for a role's access to a command"""
        try:
            del self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['roles'][str(role.id)]
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET cmd_settings = cmd_settings #- ARRAY[$1, $2, $3, $4]::TEXT[]
                WHERE cmd_name = $5;
                """, 'servers', str(ctx.guild.id), 'roles', str(role.id), command_name)
            await ctx.send(f'Deleted setting for command `{command_name}` for role: {role.name}.')
        except KeyError:
            await ctx.send('No settings found.')


    @delete_setting.command(name='channel', aliases=['c'])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_channel_cmd_setting(self, ctx, channel: discord.TextChannel, command_name: CommandName):
        """Deletes the setting for a channel's access to a command"""
        try:
            del self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['channels'][str(channel.id)]
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET cmd_settings = cmd_settings #- ARRAY[$1, $2, $3, $4]::TEXT[]
                WHERE cmd_name = $5;
                """, 'servers', str(ctx.guild.id), 'channels', str(channel.id), command_name)
            await ctx.send(f'Deleted setting for command `{command_name}` for channel: {channel.name}.')
        except KeyError:
            await ctx.send('No settings found.')


    @delete_setting.command(name='member', aliases=['m'])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_member_cmd_setting(self, ctx, member: discord.Member, command_name: CommandName):
        """Deletes the setting for a member's access to a command"""
        try:
            del self.all_cmd_settings[command_name]['servers'][str(ctx.guild.id)]['members'][str(member.id)]
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET cmd_settings = cmd_settings #- ARRAY[$1, $2, $3, $4]::TEXT[]
                WHERE cmd_name = $5;
                """, 'servers', str(ctx.guild.id), 'members', str(member.id), command_name)
            await ctx.send(f'Deleted setting for command `{command_name}` for member: {member.name}.')
        except KeyError:
            await ctx.send('No settings found.')


###############################
# list_settings command group #
###############################


    @setting.group(name='list', aliases=['l'], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def list_settings(self, ctx):
        """A group of commands that show lists of settings for multiple commands"""
        await ctx.send_help('setting list')


    @list_settings.command(name='all', aliases=['a'])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_all_settings(self, ctx):
        """Shows the names of commands that have any non-default settings for any server"""
        title = 'all commands with any non-default settings'
        names = sorted(list(self.all_cmd_settings.keys()))
        if len(names):
            paginator = Paginator(title=title, embed=True, timeout=90, entries=names, length=15)
            await paginator.start(ctx)
        else:
            await ctx.send('No settings found.')


    @list_settings.command(name='non-default-servers', aliases=['nds'])
    @commands.is_owner()
    async def list_non_default_servers(self, ctx, command_name: CommandName):
        """Shows all servers that have non-default server settings for a command"""
        # nds: non-default-servers
        nds = self.all_cmd_settings[command_name]['servers']
        nds_IDs: List[str] = list(nds.keys())
        nds_names = []
        for server in self.bot.guilds:
            if str(server.id) in nds_IDs:
                nds_names.append(server.name)

        if len(nds_names):
            title = f'servers with non-default settings for `{command_name}`'
            paginator = Paginator(title=title, embed=True, timeout=90, entries=nds_names, length=15)
            await paginator.start(ctx)
        else:
            await ctx.send('No servers found with non-default settings for this command.')


    @list_settings.command(name='global', aliases=['g'])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_global_settings(self, ctx):
        """Shows the names and global settings of commands that have non-default global settings"""
        entries = await self.get_setting_entries(['_global'])
        if len(entries):
            await self.paginate_settings(ctx, 'for global', entries)
        else:
            await ctx.send('No settings found.')


    @list_settings.command(name='global-server', aliases=['gs', 'globalserver'])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_global_server_settings(self, ctx, server: discord.Guild = None):
        """Shows the global-server command settings that apply to a server"""
        if server is None:
            server = ctx.guild
        entries = await self.get_setting_entries(['global_servers', str(server.id)])
        if len(entries):
            await self.paginate_settings(ctx, f'for global-server: {server.name}', entries)
        else:
            await ctx.send('No settings found.')


    @list_settings.command(name='global-user', aliases=['gu', 'globaluser'])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_global_user_settings(self, ctx, user: discord.User = None):
        """Shows the global-user command settings that apply to a user"""
        if user is None:
            user = ctx.author
        entries = await self.get_setting_entries(['global_users', str(user.id)])
        if len(entries):
            await self.paginate_settings(ctx, f'for global-user: {user.name}#{user.discriminator}', entries)
        else:
            await ctx.send('No settings found.')


    @list_settings.command(name='server', aliases=['s'])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_server_settings(self, ctx):
        """Shows the serverwide command settings for this server"""
        entries = await self.get_setting_entries(['servers', str(ctx.guild.id), 'server'])
        if len(entries):
            await self.paginate_settings(ctx, 'for this server', entries)
        else:
            await ctx.send('No settings found.')


    @list_settings.command(name='role', aliases=['r'])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_role_settings(self, ctx, role: discord.Role):
        """Shows the command settings that apply to a role"""
        entries = await self.get_setting_entries(['servers', str(ctx.guild.id), 'roles', str(role.id)])
        if len(entries):
            await self.paginate_settings(ctx, f'for role: {role.name}', entries)
        else:
            await ctx.send('No settings found.')


    @list_settings.command(name='channel', aliases=['c'])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_channel_settings(self, ctx, channel: discord.TextChannel):
        """Shows the command settings that apply to a text channel"""
        entries = await self.get_setting_entries(['servers', str(ctx.guild.id), 'channels', str(channel.id)])
        if len(entries):
            await self.paginate_settings(ctx, f'for channel: {channel.name}', entries)
        else:
            await ctx.send('No settings found.')


    @list_settings.command(name='member', aliases=['m'])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_member_settings(self, ctx, member: discord.Member):
        """Shows the command settings that apply to a member of this server"""
        entries = await self.get_setting_entries(['servers', str(ctx.guild.id), 'members', str(member.id)])
        if len(entries):
            await self.paginate_settings(ctx, f'for member: {member.name}#{member.discriminator}', entries)
        else:
            await ctx.send('No settings found.')


    async def paginate_settings(self, ctx, title: str, entries: List[str]) -> None:
        """Sends ctx a list of settings and their names, paginated and with reaction buttons"""
        if len(entries):
            title = f'command settings {title}'
            paginator = Paginator(title=title, embed=True, timeout=90, entries=entries, length=15)
            await paginator.start(ctx)
        else:
            await ctx.send(f'No command settings found {title}')


    async def get_setting_entries(self, keys: List[str]) -> List[str]:
        """Gets the setting and command name of non-default settings for all commands for a specific object

        The name or ID of that specific object must be the last key. The last key may only be a server ID if the second-to-last key is 'global_servers'.
        """
        if len(keys) <= 2:
            if keys[0] == 'servers':
                raise ValueError
        else:
            if keys[0] != 'servers':
                raise ValueError

        entries = []
        for command_name, sub_dict in self.all_cmd_settings.items():
            try:
                if len(keys) == 1:
                    allowed = sub_dict[keys[0]]
                elif len(keys) == 2:
                    allowed = sub_dict[keys[0]][keys[1]]
                elif len(keys) == 3:
                    allowed = sub_dict[keys[0]][keys[1]][keys[2]]
                elif len(keys) == 4:
                    allowed = sub_dict[keys[0]][keys[1]][keys[2]][keys[3]]
                else:
                    raise ValueError

                if allowed is not None:
                    allowed = '✅' if allowed else '❌'
                    entries.append(allowed + ' ' + command_name)
            except KeyError:
                pass

        return entries


    async def set_default_settings(self, ctx, command_name: str, server_id: int = None) -> None:
        """Sets default settings for a command if and only if it has no settings yet

        The defaults are set in both this program and in the database.
        """
        self.all_cmd_settings.setdefault(command_name, self.default_cmd_settings)
        await self.bot.db.execute("""
            INSERT INTO command_access_settings
            (cmd_name)
            VALUES ($1)
            ON CONFLICT (cmd_name)
            DO NOTHING;
            """, command_name)
        if server_id:
            self.all_cmd_settings[command_name]['servers'].setdefault(str(server_id), self.default_server_settings)
            await self.bot.db.execute("""
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
                WHERE cmd_name = $4;
                """, 'servers', str(server_id), self.default_server_settings_json, command_name)


    async def get_settings_message(self, settings_dict: Dict[str, bool], get_function: Callable[[int], object]) -> str:
        """Creates a str listing whether each setting in a settings dict is on or off
        
        The dict keys must be Discord object IDs, and the values must be booleans. The function to get the objects must be synchronous.
        """
        content = ''
        for ID, allowed in settings_dict.items():
            name = get_function(int(ID))
            allowed = '✅' if allowed else '❌'
            content += f'{allowed} {name}\n'

        return content


def setup(bot):
    bot.add_cog(Settings(bot))
