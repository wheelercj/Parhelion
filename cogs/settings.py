from cogs.utils.common import get_prefixes_message
from cogs.utils.common import get_prefixes_str
from cogs.utils.paginator import MyPaginator
from cogs.utils.paginator import paginate_search
from discord.ext import commands
from textwrap import dedent
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
import asyncpg
import discord
import json
import pytz


class DevSettings:
    default_bot_prefixes = [";", "par ", "Par "]
    support_server_link = "https://discord.gg/mCqGhPJVcN"
    privacy_policy_link = (
        "https://gist.github.com/wheelercj/033bbaf78b08ff0335943d5119347853"
    )
    donations_link = "https://buymeacoffee.com/Parhelion"
    error_log_channel_id = 881374348441694258


"""
    CREATE TABLE timezones (
        user_id BIGINT PRIMARY KEY NOT NULL,
        timezone TEXT NOT NULL
    );

    CREATE TABLE prefixes (
        id SERIAL PRIMARY KEY,
        server_id BIGINT UNIQUE,
        custom_prefixes TEXT[],
        removed_default_prefixes TEXT[]
    );

    CREATE TABLE command_access_settings (
        id SERIAL PRIMARY KEY,
        cmd_name TEXT UNIQUE,
        cmd_settings JSONB NOT NULL
            DEFAULT '{
                "global_users": {},
                "global_servers": {},
                "global": null,
                "servers": {}
            }'::jsonb
    );

    CREATE TABLE bot_access_settings (
        -- This table should only ever have one row and one column. Note its similarity to the table above.
        bot_settings JSONB NOT NULL
            DEFAULT '{
                "global_users": {},
                "global_servers": {},
                "global": null,
                "servers": {}
            }'::jsonb
    );
"""


class CommandName(commands.Converter):
    """Converter to validate a string input of a command name

    Command aliases and subcommands are not considered valid by this converter.
    """

    async def convert(self, ctx, argument):
        if " " in argument:
            raise commands.BadArgument(
                "Currently, settings cannot be applied to subcommands"
            )
            # If adding support for subcommands, many more changes may be needed.
        all_command_names = [x.name for x in ctx.bot.commands]
        if argument not in all_command_names:
            raise commands.BadArgument(
                f"Command `{argument}` not found. If you are trying to choose a setting for a command alias, note that the settings commands do not work on aliases."
            )
        return argument


class Settings(commands.Cog):
    """Customize how this bot works."""

    def __init__(self, bot):
        self.bot = bot
        self.settings_task = bot.loop.create_task(self.load_settings())
        self.prefixes_task = bot.loop.create_task(self.load_custom_prefixes())

        self.all_cmd_settings: Dict[str, dict] = dict()
        """
        Command access settings hierarchy and types:
            self.all_cmd_settings = {
                f'{command_name}': {
                    'global_users': {
                        f'{user_id}': bool
                    },
                    'global_servers': {
                        f'{server_id}': bool
                    },
                    'global': bool,
                    'servers': {
                        f'{server_id}': {
                            'members': {
                                f'{member_id}': bool
                            },
                            'roles': {
                                f'{role_id}': bool
                            },
                            'channels': {
                                f'{channel_id}': bool
                            },
                            'server': bool
                        }
                    }
                }
            }
        """
        # The default global and server settings for one command.
        self.default_cmd_settings = {
            "global_users": dict(),
            "global_servers": dict(),
            "global": None,
            "servers": dict(),
        }
        # The default server settings for one command.
        self.default_server_cmd_settings = {
            "members": dict(),
            "channels": dict(),
            "roles": dict(),
            "server": None,
        }
        self.default_server_cmd_settings_json = json.dumps(
            self.default_server_cmd_settings
        )

        self.all_bot_settings: Dict[str, Union[dict, bool]] = dict()
        """
        Bot access settings hierarchy and types:
            self.all_bot_settings = {
                'global_users': {
                    f'{user_id}': bool
                },
                'global_servers': {
                    f'{server_id}': bool
                },
                'global': bool,
                'servers': {
                    f'{server_id}': {
                        'members': {
                            f'{member_id}': bool
                        },
                        'roles': {
                            f'{role_id}': bool
                        },
                        'channels': {
                            f'{channel_id}': bool
                        },
                        'server': bool
                    }
                }
            }
        """
        # The default global and server settings for the bot.
        self.default_bot_settings = {
            "global_users": dict(),
            "global_servers": dict(),
            "global": None,
            "servers": dict(),
        }
        # The default server settings for the bot.
        self.default_server_bot_settings = {
            "members": dict(),
            "roles": dict(),
            "channels": dict(),
            "server": None,
        }
        self.default_server_bot_settings_json = json.dumps(
            self.default_server_bot_settings
        )

    async def load_custom_prefixes(self):
        await self.bot.wait_until_ready()
        try:
            records = await self.bot.db.fetch(
                """
                SELECT *
                FROM prefixes;
                """
            )
            for r in records:
                self.bot.custom_prefixes[r["server_id"]] = r["custom_prefixes"]
                self.bot.removed_default_prefixes[r["server_id"]] = r[
                    "removed_default_prefixes"
                ]
        except (
            OSError,
            discord.ConnectionClosed,
            asyncpg.PostgresConnectionError,
        ) as error:
            print(f"{error = }")
            self.prefixes_task.cancel()
            self.prefixes_task = self.bot.loop.create_task(self.load_custom_prefixes())

    async def load_settings(self):
        await self.bot.wait_until_ready()
        try:
            records = await self.bot.db.fetch(
                """
                SELECT *
                FROM command_access_settings;
                """
            )
            for r in records:
                self.all_cmd_settings[r["cmd_name"]] = json.loads(r["cmd_settings"])

            record = await self.bot.db.fetchrow(
                """
                SELECT *
                FROM bot_access_settings
                LIMIT 1;
                """
            )
            self.all_bot_settings = json.loads(record["bot_settings"])
        except (
            OSError,
            discord.ConnectionClosed,
            asyncpg.PostgresConnectionError,
        ) as error:
            print(f"{error = }")
            self.settings_task.cancel()
            self.settings_task = self.bot.loop.create_task(self.load_settings())

    async def bot_check(self, ctx):
        """Checks whether the settings allow the bot and ctx.command to be used by ctx

        Either returns True or raises commands.CheckFailure.
        The order in which the settings are checked is important. Generally, if multiple
        settings conflict, the most specific one will be used. Owner settings must be checked
        before the settings chosen by the mods/admin of ctx.guild, and within each of those two
        categories the settings must generally go from most specific to least specific, except
        that mods/admin of ctx.guild can deny bot/commands access that was granted by the
        owners' global_users/global_servers settings.
        """
        if await self.bot.is_owner(ctx.author):
            return True

        try:
            cmd = ctx.command.root_parent or ctx.command
            cmd_settings = self.all_cmd_settings[cmd.name]
            bot_settings = self.all_bot_settings

            # Check owner settings.
            global_settings = [
                (cmd_settings["global_users"], ctx.author.id),
                (bot_settings["global_users"], ctx.author.id),
            ]
            if ctx.guild:
                global_settings.extend(
                    [
                        (cmd_settings["global_servers"], ctx.guild.id),
                        (bot_settings["global_servers"], ctx.guild.id),
                    ]
                )
            owner_allow = False
            if await self.check_categories(ctx, global_settings):
                owner_allow = True
                # Instead of returning True here, allow servers to disable commands that
                # are enabled in global-server and/or global-user settings.

            global_settings = [
                (cmd_settings["global"], None),
                (bot_settings["global"], None),
            ]
            try:
                if await self.check_categories(ctx, global_settings):
                    return True
            except commands.CheckFailure:
                if not owner_allow:
                    raise

            # Check the settings chosen by the mods/admin of ctx.guild.
            if ctx.guild:
                all_cmd_server_settings = cmd_settings["servers"][
                    str(ctx.guild.id)
                ]  # Might raise KeyError.
                all_bot_server_settings = bot_settings["servers"][str(ctx.guild.id)]

                # Gather the settings that don't include the roles ctx.author doesn't have.
                server_settings = [
                    (all_cmd_server_settings["members"], ctx.author.id),
                    (all_bot_server_settings["members"], ctx.author.id),
                ]
                for role in ctx.author.roles[
                    ::-1
                ]:  # Reversed to start with the most important roles.
                    server_settings.extend(
                        [
                            (all_cmd_server_settings["roles"], role.id),
                            (all_bot_server_settings["roles"], role.id),
                        ]
                    )
                server_settings.extend(
                    [
                        (all_cmd_server_settings["channels"], ctx.channel.id),
                        (all_bot_server_settings["channels"], ctx.channel.id),
                        (all_cmd_server_settings["server"], None),
                        (all_bot_server_settings["server"], None),
                    ]
                )

                if await self.check_categories(ctx, server_settings):
                    return True
        except KeyError:
            pass
        # There are no relevant settings for this command.
        return True

    async def check_categories(
        self, ctx, settings_categories: List[Tuple]
    ) -> Optional[bool]:
        """Determines whether to grant access if there is at least one setting

        Returns either True or None, or raises commands.CheckFailure.
        """
        for category, ID in settings_categories:
            setting = await self.check_category(category, ID)
            if setting is not None:
                if setting:
                    return True
                raise commands.CheckFailure(
                    f"The `{ctx.invoked_with}` command has been disabled in this bot's settings for some servers, roles, channels, and/or users."
                )

    async def check_category(
        self, setting_category: Any, ID: Optional[int]
    ) -> Optional[bool]:
        """Gets the setting for an object ID in a setting category

        Should not raise any exceptions.
        """
        if ID is None or setting_category is None:
            return setting_category
        try:
            return setting_category[str(ID)]
        except KeyError:
            return None

    ###########################
    # _timezone command group #
    ###########################

    @commands.group(name="timezone", aliases=["tz"], invoke_without_command=True)
    async def _timezone(self, ctx):
        """Shows your current timezone setting if you have one

        Use the `timezone set` command to set a timezone for commands that need your time input. See the valid timezone options with the `timezone search` command, or by clicking here: <https://gist.github.com/wheelercj/86588a956b7912dfb24ec51d36c2f124>
        """
        # https://github.com/stub42/pytz/blob/master/src/README.rst
        timezone = await self.bot.db.fetchval(
            """
            SELECT timezone
            FROM timezones
            WHERE user_id = $1;
            """,
            ctx.author.id,
        )
        if timezone is not None:
            await ctx.send(f"Your current timezone setting is `{timezone}`")
        else:
            await ctx.send_help("timezone")

    @_timezone.command(name="search", aliases=["l", "list"])
    async def search_timezones(self, ctx, *, query: str = None):
        """Shows all the valid timezone options that contain a search word

        You can also see the valid timezone options here: <https://gist.github.com/wheelercj/86588a956b7912dfb24ec51d36c2f124>.
        If the valid timezones change, the update to the GitHub gist may be delayed unlike this search command.
        """
        if query is None:
            title = "timezones supported by the `timezone set` command"
        else:
            query = query.replace(" ", "_")
            title = f"supported timezones that contain `{query}`"
        await paginate_search(ctx, title, pytz.all_timezones, query)

    @_timezone.command(name="set")
    async def set_timezone(self, ctx, *, timezone: str):
        """Sets your timezone for commands that need your time input

        If you don't set a timezone, those commands will assume you are using the UTC timezone.
        See the valid timezone options with the `timezone search` command, or by clicking here: <https://gist.github.com/wheelercj/86588a956b7912dfb24ec51d36c2f124>
        """
        timezone = await self.parse_timezone(timezone)
        await self.save_timezone(ctx, timezone)
        await ctx.send(f"Your timezone has been set to `{timezone}`")

    async def parse_timezone(self, timezone: str) -> str:
        """Validates and formats a timezone input"""
        try:
            return pytz.timezone(timezone).zone
        except (pytz.exceptions.InvalidTimeError, pytz.exceptions.UnknownTimeZoneError):
            raise commands.BadArgument(
                "Invalid timezone. See the valid timezone options with the `timezone search` command, or by clicking here: <https://gist.github.com/wheelercj/86588a956b7912dfb24ec51d36c2f124>"
            )
        except Exception as error:
            raise commands.BadArgument(f"Unable to set timezone because of {error = }")

    async def save_timezone(self, ctx, timezone: str) -> None:
        """Saves a timezone string to the database

        Assumes the timezone is validated and formatted.
        """
        await self.bot.db.execute(
            """
            INSERT INTO timezones
            (user_id, timezone)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE
            SET timezone = $2
            WHERE timezones.user_id = $1;
            """,
            ctx.author.id,
            timezone,
        )

    @_timezone.command(name="delete", aliases=["del"])
    async def delete_timezone(self, ctx):
        """Deletes your timezone setting

        If you don't have a timezone setting, time-related commands will assume you are using the UTC timezone.
        """
        record = await self.bot.db.fetchrow(
            """
            DELETE FROM timezones
            WHERE user_id = $1
            RETURNING *;
            """,
            ctx.author.id,
        )
        if record is not None:
            await ctx.send(
                "Your timezone setting has been deleted. Commands that need your input about time will expect you to use the UTC timezone now."
            )
        else:
            await ctx.send("You do not have a timezone setting.")

    ########################
    # prefix command group #
    ########################

    @commands.group(invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def prefix(self, ctx):
        """A group of commands for managing this bot's command prefixes for this server"""
        prefixes = await get_prefixes_message(self.bot, ctx.message)
        await ctx.send(
            f"My current {prefixes}. You can use the `prefix add` and `prefix delete` commands to manage my command prefixes for this server."
        )

    @prefix.command(name="list", aliases=["l"])
    async def list_prefixes(self, ctx):
        """An alias for `prefix`; lists the current prefixes"""
        prefixes = await get_prefixes_message(self.bot, ctx.message)
        await ctx.send(
            f'My current {prefixes}. If you have the "manage server" permission, you can use the `prefix add` and `prefix delete` commands to manage my command prefixes for this server.'
        )

    @prefix.command(name="add", aliases=["a"])
    @commands.has_guild_permissions(manage_guild=True)
    async def add_prefix(self, ctx, *, new_prefix: str):
        """Adds a command prefix to the bot for this server

        If the prefix contains any spaces, surround it with double quotes.
        """
        new_prefix = await self.strip_quotes(new_prefix)
        if new_prefix.startswith(" "):
            raise commands.BadArgument("Prefixes cannot begin with a space.")
        if not new_prefix or new_prefix == "":
            raise commands.BadArgument(
                "Prefixless command invocation is not supported in servers."
            )
        if len(new_prefix) > 15:
            raise commands.BadArgument(
                "The maximum length of each command prefix is 15 characters."
            )

        # Remove the new prefix from the removed default prefixes, if it is there.
        try:
            self.bot.removed_default_prefixes[ctx.guild.id].remove(new_prefix)
            await self.bot.db.execute(
                """
                UPDATE prefixes
                SET removed_default_prefixes = $1
                WHERE server_id = $2;
                """,
                self.bot.removed_default_prefixes[ctx.guild.id],
                ctx.guild.id,
            )
            await ctx.send(f"Successfully added the command prefix `{new_prefix}`")
            return
        except (KeyError, ValueError, AttributeError):
            pass

        try:
            custom_prefixes: List[str] = self.bot.custom_prefixes[ctx.guild.id]
            if custom_prefixes is None:
                custom_prefixes = []
        except KeyError:
            custom_prefixes = []
        if new_prefix in custom_prefixes:
            raise commands.BadArgument(
                f"The `{new_prefix}` command prefix already exists."
            )
        if len(custom_prefixes) >= 10:
            raise commands.UserInputError(
                "The maximum number of custom command prefixes per server is 10."
            )

        custom_prefixes.append(new_prefix)
        self.bot.custom_prefixes[ctx.guild.id] = custom_prefixes
        await self.bot.db.execute(
            """
            INSERT INTO prefixes
            (server_id, custom_prefixes)
            VALUES ($1, $2)
            ON CONFLICT (server_id)
            DO UPDATE
            SET custom_prefixes = $2
            WHERE prefixes.server_id = $1;
            """,
            ctx.guild.id,
            custom_prefixes,
        )

        await ctx.send(f"Successfully added the command prefix `{new_prefix}`")

    @prefix.command(name="delete", aliases=["del"])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_prefix(self, ctx, *, old_prefix: str):
        """Deletes one of the bot's command prefixes for this server

        If the prefix contains any spaces, surround it with double quotes.
        You cannot delete the bot mention prefix.
        """
        default_prefixes: List[str] = DevSettings.default_bot_prefixes
        try:
            custom_prefixes: List[str] = self.bot.custom_prefixes[ctx.guild.id]
            if custom_prefixes is None:
                custom_prefixes = []
        except KeyError:
            custom_prefixes = []

        if old_prefix in custom_prefixes:
            custom_prefixes.remove(old_prefix)
            self.bot.custom_prefixes[ctx.guild.id] = custom_prefixes
            await self.bot.db.execute(
                """
                UPDATE prefixes
                SET custom_prefixes = $1
                WHERE server_id = $2;
                """,
                custom_prefixes,
                ctx.guild.id,
            )
            await ctx.send(f"Successfully deleted the command prefix `{old_prefix}`")
            return

        elif old_prefix in default_prefixes:
            # Save the old prefix to the list of removed default prefixes.
            try:
                removed_default_prefixes = self.bot.removed_default_prefixes[
                    ctx.guild.id
                ]
                if removed_default_prefixes is None:
                    removed_default_prefixes = []
            except KeyError:
                removed_default_prefixes = []
            if old_prefix in removed_default_prefixes:
                raise commands.BadArgument(
                    f"The `{old_prefix}` command prefix has already been deleted."
                )
            removed_default_prefixes.append(old_prefix)
            self.bot.removed_default_prefixes[ctx.guild.id] = removed_default_prefixes
            await self.bot.db.execute(
                """
                INSERT INTO prefixes
                (server_id, removed_default_prefixes)
                VALUES ($1, $2)
                ON CONFLICT (server_id)
                DO UPDATE
                SET removed_default_prefixes = $2
                WHERE prefixes.server_id = $1;
                """,
                ctx.guild.id,
                removed_default_prefixes,
            )
            await ctx.send(f"Successfully deleted the command prefix `{old_prefix}`")
            return

        await ctx.send("Prefix not found.")

    @prefix.command(name="delete-all", aliases=["del-all", "delall", "deleteall"])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_all_prefixes(self, ctx):
        """Deletes all of the bot's command prefixes for this server except the mention prefix

        You cannot delete the bot mention prefix.
        """
        default_prefixes: List[str] = DevSettings.default_bot_prefixes
        self.bot.removed_default_prefixes[ctx.guild.id] = default_prefixes

        try:
            del self.bot.custom_prefixes[ctx.guild.id]
        except KeyError:
            pass

        await self.bot.db.execute(
            """
            INSERT INTO prefixes
            (server_id, custom_prefixes, removed_default_prefixes)
            VALUES ($1, $2, $3)
            ON CONFLICT (server_id)
            DO UPDATE
            SET custom_prefixes = $2,
                removed_default_prefixes = $3
            WHERE prefixes.server_id = $1;
            """,
            ctx.guild.id,
            [],
            default_prefixes,
        )

        await ctx.send(
            f"Successfully deleted all command prefixes except `@{self.bot.user.display_name}`"
        )

    @prefix.command(name="reset")
    @commands.has_guild_permissions(manage_guild=True)
    async def reset_prefixes(self, ctx):
        """Resets the bot's command prefixes for this server to the defaults"""
        try:
            del self.bot.custom_prefixes[ctx.guild.id]
        except KeyError:
            pass
        try:
            del self.bot.removed_default_prefixes[ctx.guild.id]
        except KeyError:
            pass

        await self.bot.db.execute(
            """
            DELETE FROM prefixes
            WHERE server_id = $1;
            """,
            ctx.guild.id,
        )

        default_prefixes = await get_prefixes_str(self.bot, ctx.message)
        await ctx.send(
            f"Successfully reset the command prefixes to the defaults: {default_prefixes}"
        )

    #########################
    # setting command group #
    #########################

    @commands.group(name="set", aliases=["setting"], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def setting(self, ctx, command_name: CommandName = None):
        """A group of commands for managing the bot's settings for this server

        Without a subcommand, this command shows all the settings for a command and/or the entire bot.
        Only settings that are relevant to this server are shown.
        Use the `set guide` command for more help with settings.
        """
        view_setting_command = self.bot.get_command("setting view")
        await ctx.invoke(view_setting_command, command_name=command_name)

    @setting.command(name="guide", aliases=["h", "help"])
    @commands.has_guild_permissions(manage_guild=True)
    async def settings_guide(self, ctx):
        """Explains how the settings work"""
        entries = [
            dedent(
                """
            A command or the entire bot can be enabled or disabled for the entire server, or for
            a channel, a role, or a member. If a setting is not chosen, most of the bot's features
            are enabled by default for most users. Some commands have extra requirements
            not listed in settings. For example, these setting commands require the user
            to have the "manage server" permission."""
            ),
            dedent(
                """
            When creating or deleting a setting for a command, use the command's full
            name (not an alias). For commands that have subcommands (such as the `remind`
            commands), settings can only be applied to the root command. If two or more
            settings conflict, the most specific one will be used (except that some global
            settings cannot be overridden by server settings; global settings can only be
            set by the bot owner). For example, if the `remind` command is disabled for the
            server but enabled for one of its users, then that command can only be used by
            that user. Role settings are considered more specific than channel settings."""
            ),
            dedent(
                """
            Here is the precedence of the settings:
                1. Does the bot owner allow the command invoker to use the command?
                2. Does the bot owner allow the command invoker to use the bot?
                3. Does the bot owner allow the server to use the command?
                4. Does the bot owner allow the server to use the bot?
                5. Does the bot owner allow the command to be used?
                6. Does the bot owner allow the bot to be used?
                7. Does the server allow the command invoker to use the command?
                8. Does the server allow the command invoker to use the bot?
                9. Does the server allow the command invoker's roles (sorted by decreasing importance) to use the command?
                10. Does the server allow the command invoker's roles (sorted by decreasing importance) to use the bot?
                11. Does the server allow the channel to use the command?
                12. Does the server allow the channel to use the bot?
                13. Does the server allow the server to use the command?
                14. Does the server allow the server to use the bot?"""
            ),
            dedent(
                """
            There are three possible answers to each of the questions on the previous page:
            allow, deny, or undefined. Each time someone tries to use a command, the bot
            starts checking the questions. If an answer is undefined, the next question is
            checked. If all the answers are undefined, use of the command will be allowed.
            If an answer is to allow or deny, the bot will immediately stop checking the
            questions and allow or deny access to the command, except that a server can
            choose to deny access even if the owner is allowing access to that specific
            server or to a user in that server. If the owner is denying access in any way or
            globally allowing access to all servers, then that cannot be overridden by
            server settings."""
            ),
            dedent(
                """
            Since the bot's and each command's use is allowed by default, most settings will
            be to deny access except in cases where it is easier to deny access by default
            and allow access by exception.
            
            Please let me know in the support server (use the `support` command) if you have
            any questions/concerns/etc. Some commands, such as the `tag` commands, may be
            disabled by default and only enabled for servers that have requested them and
            have a good use for them."""
            ),
        ]

        title = "how the settings work"
        paginator = MyPaginator(
            title=title,
            embed=True,
            timeout=90,
            use_defaults=True,
            entries=entries,
            length=1,
        )
        await paginator.start(ctx)

    @setting.command(name="view", aliases=["v"])
    @commands.has_guild_permissions(manage_guild=True)
    async def view_settings(self, ctx, command_name: CommandName = None):
        """An alias for `set`; shows all the settings for a command and/or the entire bot

        Only settings that are relevant to this server are shown.
        """
        cmd_settings = None
        bot_settings = self.all_bot_settings
        entries = []
        try:
            cmd_settings = self.all_cmd_settings[command_name]
            title = f"**bot settings and `{command_name}` command settings**"
        except KeyError:
            title = "**bot settings**"
            if command_name:
                await ctx.send(f"settings for command `{command_name}` not found")

        entries.extend(
            await self.get_global_settings_messages(ctx, bot_settings, cmd_settings)
        )
        entries.extend(
            await self.get_server_settings_messages(ctx, bot_settings, cmd_settings)
        )

        if len(entries):
            paginator = MyPaginator(
                title=title,
                embed=True,
                timeout=90,
                use_defaults=True,
                entries=entries,
                length=20,
            )
            await paginator.start(ctx)
        else:
            await ctx.send("No settings found.")

    @setting.command(name="non-default-servers", aliases=["nds"])
    @commands.is_owner()
    async def list_non_default_servers(self, ctx, command_name: CommandName = None):
        """Shows all servers that have non-default server settings

        If a command_name is given, only servers with non-default server settings for
        that command will be shown. If a command_name is not given, only servers with
        non-default server bot settings will be shown.
        """
        if command_name:
            nds = self.all_cmd_settings[command_name][
                "servers"
            ]  # nds: non-default-servers
            nds_IDs: List[str] = list(nds.keys())
            nds_names = []
            for server in self.bot.guilds:
                if str(server.id) in nds_IDs:
                    nds_names.append(server.name)

            if len(nds_names):
                title = f"servers with non-default settings for `{command_name}`"
                paginator = MyPaginator(
                    title=title, embed=True, timeout=90, entries=nds_names, length=15
                )
                await paginator.start(ctx)
            else:
                await ctx.send(
                    f"No servers found with non-default settings for the `{command_name}` command."
                )
        else:
            nds = self.all_bot_settings["servers"]  # nds: non-default-servers
            nds_IDs: List[str] = list(nds.keys())
            nds_names = []
            for server in self.bot.guilds:
                if str(server.id) in nds_IDs:
                    nds_names.append(server.name)

            if len(nds_names):
                title = f"servers with non-default settings for the bot"
                paginator = MyPaginator(
                    title=title, embed=True, timeout=90, entries=nds_names, length=15
                )
                await paginator.start(ctx)
            else:
                await ctx.send(
                    "No servers found with non-default settings for the bot."
                )

    @setting.command(name="rename")
    @commands.is_owner()
    async def rename_command(
        self, ctx, old_command_name: str, current_command_name: CommandName
    ):
        """Changes a command's name in the command settings table and dictionary

        Use this command each time a command is renamed in the code.
        """
        await self.bot.db.execute(
            """
            UPDATE command_access_settings
            SET cmd_name = $1
            WHERE cmd_name = $2;
            """,
            current_command_name,
            old_command_name,
        )
        try:
            self.all_cmd_settings[current_command_name] = self.all_cmd_settings.pop(
                old_command_name
            )
            await ctx.send(
                "Command renamed in the command settings table and dictionary."
            )
        except KeyError:
            await ctx.send("Command not found.")

    @setting.command(name="global", aliases=["g"])
    @commands.is_owner()
    async def global_setting(
        self, ctx, on_or_off: bool, command_name: CommandName = None
    ):
        """Manages absolute bot or commands access globally"""
        setting_json = json.dumps(on_or_off)
        if command_name:
            await self.set_default_settings(None, command_name)
            self.all_cmd_settings[command_name]["global"] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, '{global}', $1::JSONB, TRUE)
                WHERE cmd_name = $2;
                """,
                setting_json,
                command_name,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(f"New global setting: command `{command_name}` {on_or_off}.")
        else:
            self.all_bot_settings["global"] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, '{global}', $1::JSONB, TRUE);
                """,
                setting_json,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(f"New global setting: bot {on_or_off}.")

    @setting.command(name="global-server", aliases=["gs", "globalserver"])
    @commands.is_owner()
    async def global_server_setting(
        self,
        ctx,
        server: discord.Guild,
        on_or_off: bool,
        command_name: CommandName = None,
    ):
        """Manages absolute bot or commands access for a server"""
        setting_json = json.dumps(on_or_off)
        if command_name:
            await self.set_default_settings(None, command_name)
            self.all_cmd_settings[command_name]["global_servers"][
                str(server.id)
            ] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
                WHERE cmd_name = $4;
                """,
                "global_servers",
                str(server.id),
                setting_json,
                command_name,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(
                f"New global setting: `{command_name}` {on_or_off} for server: {server.name}."
            )
        else:
            self.all_bot_settings["global_servers"][str(server.id)] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE);
                """,
                "global_servers",
                str(server.id),
                setting_json,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(
                f"New global setting: bot {on_or_off} for server: {server.name}."
            )

    @setting.command(name="global-user", aliases=["gu", "globaluser"])
    @commands.is_owner()
    async def global_user_setting(
        self, ctx, user: discord.User, on_or_off: bool, command_name: CommandName = None
    ):
        """Manages absolute bot or commands access for a user"""
        await self.set_default_settings(None, command_name)
        setting_json = json.dumps(on_or_off)
        if command_name:
            self.all_cmd_settings[command_name]["global_users"][
                str(user.id)
            ] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
                WHERE cmd_name = $4;
                """,
                "global_users",
                str(user.id),
                setting_json,
                command_name,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(
                f"New global setting: `{command_name}` {on_or_off} for user: {user.name}#{user.discriminator}."
            )
        else:
            self.all_bot_settings["global_users"][str(user.id)] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
                """,
                "global_users",
                str(user.id),
                setting_json,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(
                f"New global setting: bot {on_or_off} for user: {user.name}#{user.discriminator}."
            )

    @setting.command(name="server", aliases=["s"])
    @commands.has_guild_permissions(manage_guild=True)
    async def server_setting(
        self, ctx, on_or_off: bool, command_name: CommandName = None
    ):
        """Manages bot or commands access for this server"""
        await self.set_default_settings(ctx.guild.id, command_name)
        setting_json = json.dumps(on_or_off)
        if command_name:
            self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)][
                "server"
            ] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3]::TEXT[], $4::JSONB, TRUE)
                WHERE cmd_name = $5;
                """,
                "servers",
                str(ctx.guild.id),
                "server",
                setting_json,
                command_name,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(
                f"New setting: `{command_name}` {on_or_off} for this server."
            )
        else:
            self.all_bot_settings["servers"][str(ctx.guild.id)]["server"] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, ARRAY[$1, $2, $3]::TEXT[], $4::JSONB, TRUE);
                """,
                "servers",
                str(ctx.guild.id),
                "server",
                setting_json,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(f"New setting: bot {on_or_off} for this server.")

    @setting.command(name="channel", aliases=["c"])
    @commands.has_guild_permissions(manage_guild=True)
    async def channel_setting(
        self,
        ctx,
        channel: discord.TextChannel,
        on_or_off: bool,
        command_name: CommandName = None,
    ):
        """Manages bot or commands access for a text channel in this server"""
        await self.set_default_settings(ctx.guild.id, command_name)
        setting_json = json.dumps(on_or_off)
        if command_name:
            self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)][
                "channels"
            ][str(channel.id)] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
                WHERE cmd_name = $6;
                """,
                "servers",
                str(ctx.guild.id),
                "channels",
                str(channel.id),
                setting_json,
                command_name,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(
                f"New setting: `{command_name}` {on_or_off} for channel: {channel.name}."
            )
        else:
            self.all_bot_settings["servers"][str(ctx.guild.id)]["channels"][
                str(channel.id)
            ] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE);
                """,
                "servers",
                str(ctx.guild.id),
                "channels",
                str(channel.id),
                setting_json,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(f"New setting: bot {on_or_off} for channel: {channel.name}.")

    @setting.command(name="role", aliases=["r"])
    @commands.has_guild_permissions(manage_guild=True)
    async def role_setting(
        self, ctx, role: discord.Role, on_or_off: bool, command_name: CommandName = None
    ):
        """Manages bot or commands access for a role in this server"""
        await self.set_default_settings(ctx.guild.id, command_name)
        setting_json = json.dumps(on_or_off)
        if command_name:
            self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)]["roles"][
                str(role.id)
            ] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
                WHERE cmd_name = $6;
                """,
                "servers",
                str(ctx.guild.id),
                "roles",
                str(role.id),
                setting_json,
                command_name,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(
                f"New setting: `{command_name}` {on_or_off} for role: {role.name}."
            )
        else:
            self.all_bot_settings["servers"][str(ctx.guild.id)]["roles"][
                str(role.id)
            ] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE);
                """,
                "servers",
                str(ctx.guild.id),
                "roles",
                str(role.id),
                setting_json,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(f"New setting: bot {on_or_off} for role: {role.name}.")

    @setting.command(name="member", aliases=["m"])
    @commands.has_guild_permissions(manage_guild=True)
    async def member_setting(
        self,
        ctx,
        member: discord.Member,
        on_or_off: bool,
        command_name: CommandName = None,
    ):
        """Manages bot or commands access for a member of this server"""
        await self.set_default_settings(ctx.guild.id, command_name)
        setting_json = json.dumps(on_or_off)
        if command_name:
            self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)][
                "members"
            ][str(member.id)] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE)
                WHERE cmd_name = $6;
                """,
                "servers",
                str(ctx.guild.id),
                "members",
                str(member.id),
                setting_json,
                command_name,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(
                f"New setting: `{command_name}` {on_or_off} for member: {member.name}."
            )
        else:
            self.all_cmd_settings["servers"][str(ctx.guild.id)]["members"][
                str(member.id)
            ] = on_or_off
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, ARRAY[$1, $2, $3, $4]::TEXT[], $5::JSONB, TRUE);
                """,
                "servers",
                str(ctx.guild.id),
                "members",
                str(member.id),
                setting_json,
            )
            on_or_off = "enabled" if on_or_off else "disabled"
            await ctx.send(f"New setting: bot {on_or_off} for member: {member.name}.")

    async def set_default_settings(
        self, server_id: int = None, command_name: str = None
    ) -> None:
        """Sets default settings for the bot or a command, but never overwrites any existing settings

        The defaults are set in both this program and in the database.
        """
        if command_name:
            self.all_cmd_settings.setdefault(command_name, self.default_cmd_settings)
            await self.bot.db.execute(
                """
                INSERT INTO command_access_settings
                (cmd_name)
                VALUES ($1)
                ON CONFLICT (cmd_name)
                DO NOTHING;
                """,
                command_name,
            )
            if server_id:
                self.all_cmd_settings[command_name]["servers"].setdefault(
                    str(server_id), self.default_server_cmd_settings
                )
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE)
                    WHERE cmd_name = $4;
                    """,
                    "servers",
                    str(server_id),
                    self.default_server_cmd_settings_json,
                    command_name,
                )
        elif server_id:
            self.all_bot_settings["servers"].setdefault(
                str(server_id), self.default_server_bot_settings
            )
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, ARRAY[$1, $2]::TEXT[], $3::JSONB, TRUE);
                """,
                "servers",
                str(server_id),
                self.default_server_bot_settings_json,
            )

    async def get_global_settings_messages(
        self, ctx, bot_settings: dict, cmd_settings: Optional[dict]
    ) -> List[str]:
        """Gets the settings chosen by the bot owner"""
        entries = []
        if cmd_settings and cmd_settings["global_users"]:
            entries.extend(
                await self.add_global_users_field(ctx, cmd_settings, "command")
            )
        if bot_settings and bot_settings["global_users"]:
            entries.extend(await self.add_global_users_field(ctx, bot_settings, "bot"))
        if cmd_settings and cmd_settings["global_servers"]:
            entries.extend(
                await self.get_global_server_setting_message(
                    ctx, cmd_settings, "command"
                )
            )
        if bot_settings and bot_settings["global_servers"]:
            entries.extend(
                await self.get_global_server_setting_message(ctx, bot_settings, "bot")
            )
        if cmd_settings and cmd_settings["global"] is not None:
            is_allowed = "???" if cmd_settings["global"] else "???"
            entries.append(f"\n**global command**\n{is_allowed}")
        if bot_settings and bot_settings["global"] is not None:
            is_allowed = "???" if bot_settings["global"] else "???"
            entries.append(f"\n**global bot**\n{is_allowed}")

        return entries

    async def get_server_settings_messages(
        self, ctx, bot_settings: dict, cmd_settings: Optional[dict]
    ) -> List[str]:
        """Gets the settings chosen by ctx.guild"""
        entries = []
        try:
            server = self.bot.get_guild(ctx.guild.id)
            if not server:
                raise KeyError

            s_cmd_settings = None
            if cmd_settings:
                try:
                    s_cmd_settings = cmd_settings["servers"][str(ctx.guild.id)]
                except KeyError:
                    pass
            s_bot_settings = None
            try:
                s_bot_settings = bot_settings["servers"][str(ctx.guild.id)]
            except KeyError:
                pass

            if s_cmd_settings and len(s_cmd_settings["members"]):
                content = await self.get_settings_message(
                    s_cmd_settings["members"], server.get_member
                )
                entries.append(f"\n**server members command**{content}")
            if s_bot_settings and len(s_bot_settings["members"]):
                content = await self.get_settings_message(
                    s_bot_settings["members"], server.get_member
                )
                entries.append(f"\n**server members bot**{content}")
            if s_cmd_settings and len(s_cmd_settings["roles"]):
                content = await self.get_settings_message(
                    s_cmd_settings["roles"], server.get_role
                )
                entries.append(f"\n**server roles command**{content}")
            if s_bot_settings and len(s_bot_settings["roles"]):
                content = await self.get_settings_message(
                    s_bot_settings["roles"], server.get_role
                )
                entries.append(f"\n**server roles bot**{content}")
            if s_cmd_settings and len(s_cmd_settings["channels"]):
                content = await self.get_settings_message(
                    s_cmd_settings["channels"], server.get_channel
                )
                entries.append(f"\n**server channels command**{content}")
            if s_bot_settings and len(s_bot_settings["channels"]):
                content = await self.get_settings_message(
                    s_bot_settings["channels"], server.get_channel
                )
                entries.append(f"\n**server channels bot**{content}")
            if s_cmd_settings and s_cmd_settings["server"] is not None:
                is_allowed = "???" if cmd_settings["server"] else "???"
                entries.append(f"\n**server command**\n{is_allowed}")
            if s_bot_settings and s_bot_settings["server"] is not None:
                is_allowed = "???" if bot_settings["server"] else "???"
                entries.append(f"\n**server bot**\n{is_allowed}")
        except KeyError:
            pass

        return entries

    async def add_global_users_field(
        self, ctx, settings: dict, title_suffix: str
    ) -> List[str]:
        """Gets the names and settings of users in ctx.guild that have a global setting"""
        entries = []
        members = dict()
        for user_id in settings["global_users"]:
            member = ctx.guild.get_member(user_id)
            if member is None:
                continue
            members[user_id] = settings["global_users"][user_id]
        if len(settings["global_users"]):
            content = await self.get_settings_message(members, self.bot.get_user)
            title = "global users " + title_suffix
            entries.append(f"\n**{title}**\n{content}")

        return entries

    async def get_global_server_setting_message(
        self, ctx, settings: dict, title_suffix: str
    ) -> List[str]:
        """Gets ctx.guild.name and ctx.guild's setting if and only if it has a setting"""
        entries = []
        try:
            is_allowed = settings["global_servers"][str(ctx.guild.id)]
            setting_dict = {str(ctx.guild.id): is_allowed}
            content = await self.get_settings_message(setting_dict, self.bot.get_guild)
            title = "global servers " + title_suffix
            entries.append(f"\n**{title}**{content}")
        except KeyError:
            pass

        return entries

    async def get_settings_message(
        self, settings_dict: Dict[str, bool], get_function: Callable[[int], object]
    ) -> str:
        """Creates a str listing whether each setting in a settings dict is on or off

        The dict keys must be Discord object IDs, and the values must be booleans. The function to get the objects must be synchronous.
        """
        content = ""
        for ID, is_allowed in settings_dict.items():
            name = get_function(int(ID))
            is_allowed = "???" if is_allowed else "???"
            content += f"\n{is_allowed} {name}"

        return content

    ################################
    # delete_setting command group #
    ################################

    @setting.group(name="delete", aliases=["del"], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_setting(self, ctx):
        """A group of commands for deleting settings"""
        await ctx.send_help("setting delete")

    @delete_setting.command(name="global-all", aliases=["globalall"])
    @commands.is_owner()
    async def delete_all_global_settings(self, ctx, command_name: CommandName = None):
        """Deletes all settings for a command, or all settings that are for the bot but not commands"""
        if command_name:
            try:
                del self.all_cmd_settings[command_name]
                await self.bot.db.execute(
                    """
                    DELETE FROM command_access_settings
                    WHERE cmd_name = $1;
                    """,
                    command_name,
                )
                await ctx.send(
                    f"Deleted all setting for command `{command_name}`, including the global settings."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")
        else:
            try:
                del self.all_bot_settings
                await self.bot.db.execute("""TRUNCATE TABLE bot_access_settings;""")
                await self.bot.db.execute("""INSERT INTO bot_access_settings;""")
                await ctx.send(
                    f"Deleted all setting for the bot, including the global settings."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")

    @delete_setting.command(name="all")
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_all_server_settings(self, ctx, command_name: CommandName = None):
        """Deletes all of this server's settings for a command, or all settings that are for the bot but not commands"""
        if command_name:
            try:
                del self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)]
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET cmd_settings = cmd_settings #- ARRAY[$1, $2]::TEXT[]
                    WHERE cmd_name = $3;
                    """,
                    "servers",
                    str(ctx.guild.id),
                    command_name,
                )
                await ctx.send(
                    f"Deleted all server setting for command `{command_name}`."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")
        else:
            try:
                del self.all_bot_settings["servers"][str(ctx.guild.id)]
                await self.bot.db.execute(
                    """
                    UPDATE bot_access_settings
                    SET bot_settings = bot_settings #- ARRAY[$1, $2]::TEXT[];
                    """,
                    "servers",
                    str(ctx.guild.id),
                )
                await ctx.send(f"Deleted all server setting for the bot.")
            except KeyError:
                raise commands.BadArgument("No settings found.")

        await self.cleanup_after_setting_delete(command_name, ctx.guild.id)

    @delete_setting.command(name="global", aliases=["g"])
    @commands.is_owner()
    async def delete_global_setting(self, ctx, command_name: CommandName = None):
        """Deletes a global command setting or the global bot setting"""
        if command_name:
            self.all_cmd_settings[command_name]["global"] = None
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, '{global}', $1::JSONB, TRUE)
                WHERE cmd_name = $2;
                """,
                "null",
                command_name,
            )
            await ctx.send(f"Deleted global setting for command `{command_name}`.")
        else:
            self.all_bot_settings["global"] = None
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, '{global}', $1::JSONB, TRUE);
                """,
                "null",
            )
            await ctx.send(f"Deleted global setting for the bot.")

        await self.cleanup_after_setting_delete(command_name)

    @delete_setting.command(name="global-server", aliases=["gs", "globalserver"])
    @commands.is_owner()
    async def delete_global_server_setting(
        self, ctx, server: discord.Guild, command_name: CommandName = None
    ):
        """Deletes the global setting for a server's access to a command or to the bot"""
        if command_name:
            try:
                del self.all_cmd_settings[command_name]["global_servers"][
                    str(server.id)
                ]
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET cmd_settings = cmd_settings #- ARRAY[$1, $2]::TEXT[]
                    WHERE cmd_name = $3;
                    """,
                    "global_servers",
                    str(server.id),
                    command_name,
                )
                await ctx.send(
                    f"Deleted global setting for command `{command_name}` for server: {server.name}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")
        else:
            try:
                del self.all_bot_settings["global_servers"][str(server.id)]
                await self.bot.db.execute(
                    """
                    UPDATE bot_access_settings
                    SET bot_settings = bot_settings #- ARRAY[$1, $2]::TEXT[];
                    """,
                    "global_servers",
                    str(server.id),
                )
                await ctx.send(
                    f"Deleted global setting for the bot for server: {server.name}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")

        await self.cleanup_after_setting_delete(command_name)

    @delete_setting.command(name="global-user", aliases=["gu", "globaluser"])
    @commands.is_owner()
    async def delete_global_user_setting(
        self, ctx, user: discord.User, command_name: CommandName = None
    ):
        """Deletes the global setting for a user's access to a command or to the bot"""
        if command_name:
            try:
                del self.all_cmd_settings[command_name]["global_users"][str(user.id)]
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET cmd_settings = cmd_settings #- ARRAY[$1, $2]::TEXT[]
                    WHERE cmd_name = $3;
                    """,
                    "global_users",
                    str(user.id),
                    command_name,
                )
                await ctx.send(
                    f"Deleted global setting for command `{command_name}` for user: {user.name}#{user.discriminator}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")
        else:
            try:
                del self.all_bot_settings["global_users"][str(user.id)]
                await self.bot.db.execute(
                    """
                    UPDATE bot_access_settings
                    SET bot_settings = bot_settings #- ARRAY[$1, $2]::TEXT[];
                    """,
                    "global_users",
                    str(user.id),
                )
                await ctx.send(
                    f"Deleted global setting for the bot for user: {user.name}#{user.discriminator}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")

        await self.cleanup_after_setting_delete(command_name)

    @delete_setting.command(name="server", aliases=["s"])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_server_setting(self, ctx, command_name: CommandName = None):
        """Deletes this server's overall setting for a command or to the bot"""
        if command_name:
            self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)][
                "server"
            ] = None
            await self.bot.db.execute(
                """
                UPDATE command_access_settings
                SET cmd_settings = JSONB_SET(cmd_settings, ARRAY[$1, $2, $3]::TEXT[], $4::JSONB, TRUE)
                WHERE cmd_name = $5;
                """,
                "servers",
                str(ctx.guild.id),
                "server",
                "null",
                command_name,
            )
            await ctx.send(
                f"Deleted setting for command `{command_name}` for this server."
            )
        else:
            self.all_bot_settings["servers"][str(ctx.guild.id)]["server"] = None
            await self.bot.db.execute(
                """
                UPDATE bot_access_settings
                SET bot_settings = JSONB_SET(bot_settings, ARRAY[$1, $2, $3]::TEXT[], $4::JSONB, TRUE);
                """,
                "servers",
                str(ctx.guild.id),
                "server",
                "null",
            )
            await ctx.send(f"Deleted setting for the bot for this server.")

        await self.cleanup_after_setting_delete(command_name, ctx.guild.id)

    @delete_setting.command(name="channel", aliases=["c"])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_channel_setting(
        self, ctx, channel: discord.TextChannel, command_name: CommandName = None
    ):
        """Deletes the setting for a channel's access to a command or to the bot"""
        if command_name:
            try:
                del self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)][
                    "channels"
                ][str(channel.id)]
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET cmd_settings = cmd_settings #- ARRAY[$1, $2, $3, $4]::TEXT[]
                    WHERE cmd_name = $5;
                    """,
                    "servers",
                    str(ctx.guild.id),
                    "channels",
                    str(channel.id),
                    command_name,
                )
                await ctx.send(
                    f"Deleted setting for command `{command_name}` for channel: {channel.name}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")
        else:
            try:
                del self.all_bot_settings["servers"][str(ctx.guild.id)]["channels"][
                    str(channel.id)
                ]
                await self.bot.db.execute(
                    """
                    UPDATE bot_access_settings
                    SET bot_settings = bot_settings #- ARRAY[$1, $2, $3, $4]::TEXT[];
                    """,
                    "servers",
                    str(ctx.guild.id),
                    "channels",
                    str(channel.id),
                )
                await ctx.send(
                    f"Deleted setting for the bot for channel: {channel.name}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")

        await self.cleanup_after_setting_delete(command_name, ctx.guild.id)

    @delete_setting.command(name="role", aliases=["r"])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_role_setting(
        self, ctx, role: discord.Role, command_name: CommandName = None
    ):
        """Deletes the setting for a role's access to a command or to the bot"""
        if command_name:
            try:
                del self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)][
                    "roles"
                ][str(role.id)]
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET cmd_settings = cmd_settings #- ARRAY[$1, $2, $3, $4]::TEXT[]
                    WHERE cmd_name = $5;
                    """,
                    "servers",
                    str(ctx.guild.id),
                    "roles",
                    str(role.id),
                    command_name,
                )
                await ctx.send(
                    f"Deleted setting for command `{command_name}` for role: {role.name}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")
        else:
            try:
                del self.all_bot_settings["servers"][str(ctx.guild.id)]["roles"][
                    str(role.id)
                ]
                await self.bot.db.execute(
                    """
                    UPDATE bot_access_settings
                    SET bot_settings = bot_settings #- ARRAY[$1, $2, $3, $4]::TEXT[];
                    """,
                    "servers",
                    str(ctx.guild.id),
                    "roles",
                    str(role.id),
                )
                await ctx.send(f"Deleted setting for the bot for role: {role.name}.")
            except KeyError:
                raise commands.BadArgument("No settings found.")

        await self.cleanup_after_setting_delete(command_name, ctx.guild.id)

    @delete_setting.command(name="member", aliases=["m"])
    @commands.has_guild_permissions(manage_guild=True)
    async def delete_member_setting(
        self, ctx, member: discord.Member, command_name: CommandName = None
    ):
        """Deletes the setting for a member's access to a command or to the bot"""
        if command_name:
            try:
                del self.all_cmd_settings[command_name]["servers"][str(ctx.guild.id)][
                    "members"
                ][str(member.id)]
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET cmd_settings = cmd_settings #- ARRAY[$1, $2, $3, $4]::TEXT[]
                    WHERE cmd_name = $5;
                    """,
                    "servers",
                    str(ctx.guild.id),
                    "members",
                    str(member.id),
                    command_name,
                )
                await ctx.send(
                    f"Deleted setting for command `{command_name}` for member: {member.name}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")
        else:
            try:
                del self.all_bot_settings["servers"][str(ctx.guild.id)]["members"][
                    str(member.id)
                ]
                await self.bot.db.execute(
                    """
                    UPDATE bot_access_settings
                    SET bot_settings = bot_settings #- ARRAY[$1, $2, $3, $4]::TEXT[];
                    """,
                    "servers",
                    str(ctx.guild.id),
                    "members",
                    str(member.id),
                )
                await ctx.send(
                    f"Deleted setting for the bot for member: {member.name}."
                )
            except KeyError:
                raise commands.BadArgument("No settings found.")

        await self.cleanup_after_setting_delete(command_name, ctx.guild.id)

    async def cleanup_after_setting_delete(
        self, command_name: CommandName = None, server_id: int = None
    ) -> None:
        """Deletes a command's or the bot's settings if and only if they are empty

        If server_id is given, this function will only check that server's settings.
        If server_id is not given, all the settings will be checked.
        The data is deleted from both the settings dict and the database.

        This function should be called each time settings have just been deleted, except for commands
        that clean up after themselves already (such as the `set del global-all` command).
        """
        if command_name:
            if server_id:
                settings = self.all_cmd_settings[command_name]["servers"][
                    str(server_id)
                ]
            else:
                settings = self.all_cmd_settings[command_name]
            for value in settings.values():
                if value is not None:
                    if isinstance(value, bool):
                        # Found non-empty bool setting.
                        return
                    elif len(value):
                        # Found non-empty dict setting.
                        return

            # Found empty settings. Delete them.
            if server_id:
                del self.all_cmd_settings[command_name]["servers"][str(server_id)]
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET cmd_settings = cmd_settings #- ARRAY[$1, $2]::TEXT[]
                    WHERE cmd_name = $3;
                    """,
                    "servers",
                    str(server_id),
                    command_name,
                )
            else:
                del self.all_cmd_settings[command_name]
                await self.bot.db.execute(
                    """
                    DELETE FROM command_access_settings
                    WHERE cmd_name = $1;
                    """,
                    command_name,
                )
        else:
            if server_id:
                settings = self.all_bot_settings["servers"][str(server_id)]
            else:
                settings = self.all_bot_settings
            for value in settings.values():
                if value is not None:
                    if isinstance(value, bool):
                        # Found non-empty bool setting.
                        return
                    elif len(value):
                        # Found non-empty dict setting.
                        return

            # Found empty settings. Delete them.
            if server_id:
                del self.all_bot_settings["servers"][str(server_id)]
                await self.bot.db.execute(
                    """
                    UPDATE command_access_settings
                    SET bot_settings = bot_settings #- ARRAY[$1, $2]::TEXT[];
                    """,
                    "servers",
                    str(server_id),
                )
            else:
                del self.all_bot_settings
                await self.bot.db.execute("""TRUNCATE TABLE bot_access_settings;""")
                await self.bot.db.execute("""INSERT INTO bot_access_settings;""")

    ###############################
    # list_settings command group #
    ###############################

    @setting.group(name="list", aliases=["l"], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def list_settings(self, ctx):
        """A group of commands that show lists of settings for multiple commands"""
        await ctx.send_help("setting list")

    @list_settings.command(name="all", aliases=["a"])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_all_settings(self, ctx):
        """Shows the names of commands that have any non-default settings for any server"""
        entries = []
        for key, value in sorted(self.all_cmd_settings.items()):
            if value["global"]:
                entries.append(f"??? {key}")
            elif value["global"] is None:
                entries.append(f"??? {key}")
            else:
                entries.append(f"??? {key}")
        if len(entries):
            title = (
                "all commands with any non-default settings, and their global setting"
            )
            paginator = MyPaginator(
                title=title, embed=True, timeout=90, entries=entries, length=15
            )
            await paginator.start(ctx)
        else:
            raise commands.BadArgument("No settings found.")

    @list_settings.command(name="global", aliases=["g"])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_global_settings(self, ctx):
        """Shows the names and global settings of commands that have non-default global settings"""
        entries = await self.get_cmd_setting_entries(["global"])
        if len(entries):
            await self.paginate_settings(ctx, "for global", entries)
        else:
            raise commands.BadArgument("No settings found.")

    @list_settings.command(name="global-server", aliases=["gs", "globalserver"])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_global_server_settings(self, ctx, server: discord.Guild = None):
        """Shows the global-server command settings that apply to a server"""
        if server is None:
            server = ctx.guild
        entries = await self.get_cmd_setting_entries(["global_servers", str(server.id)])
        if len(entries):
            await self.paginate_settings(
                ctx, f"for global-server: {server.name}", entries
            )
        else:
            raise commands.BadArgument("No settings found.")

    @list_settings.command(name="global-user", aliases=["gu", "globaluser"])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_global_user_settings(self, ctx, user: discord.User = None):
        """Shows the global-user command settings that apply to a user"""
        if user is None:
            user = ctx.author
        entries = await self.get_cmd_setting_entries(["global_users", str(user.id)])
        if len(entries):
            await self.paginate_settings(
                ctx, f"for global-user: {user.name}#{user.discriminator}", entries
            )
        else:
            raise commands.BadArgument("No settings found.")

    @list_settings.command(name="server", aliases=["s"])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_server_settings(self, ctx):
        """Shows the serverwide command settings for this server"""
        entries = await self.get_cmd_setting_entries(
            ["servers", str(ctx.guild.id), "server"]
        )
        if len(entries):
            await self.paginate_settings(ctx, "for this server", entries)
        else:
            raise commands.BadArgument("No settings found.")

    @list_settings.command(name="channel", aliases=["c"])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_channel_settings(self, ctx, channel: discord.TextChannel):
        """Shows the command settings that apply to a text channel"""
        entries = await self.get_cmd_setting_entries(
            ["servers", str(ctx.guild.id), "channels", str(channel.id)]
        )
        if len(entries):
            await self.paginate_settings(ctx, f"for channel: {channel.name}", entries)
        else:
            raise commands.BadArgument("No settings found.")

    @list_settings.command(name="role", aliases=["r"])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_role_settings(self, ctx, role: discord.Role):
        """Shows the command settings that apply to a role"""
        entries = await self.get_cmd_setting_entries(
            ["servers", str(ctx.guild.id), "roles", str(role.id)]
        )
        if len(entries):
            await self.paginate_settings(ctx, f"for role: {role.name}", entries)
        else:
            raise commands.BadArgument("No settings found.")

    @list_settings.command(name="member", aliases=["m"])
    @commands.has_guild_permissions(manage_guild=True)
    async def list_member_settings(self, ctx, member: discord.Member):
        """Shows the command settings that apply to a member of this server"""
        entries = await self.get_cmd_setting_entries(
            ["servers", str(ctx.guild.id), "members", str(member.id)]
        )
        if len(entries):
            await self.paginate_settings(
                ctx, f"for member: {member.name}#{member.discriminator}", entries
            )
        else:
            raise commands.BadArgument("No settings found.")

    async def paginate_settings(self, ctx, title: str, entries: List[str]) -> None:
        """Sends ctx a list of settings and their names, paginated and with reaction buttons"""
        if len(entries):
            title = f"command settings {title}"
            paginator = MyPaginator(
                title=title, embed=True, timeout=90, entries=entries, length=15
            )
            await paginator.start(ctx)
        else:
            await ctx.send(f"No command settings found {title}")

    async def get_cmd_setting_entries(self, keys: List[str]) -> List[str]:
        """Gets the setting and command name of non-default settings for all commands for a specific object

        The name or ID of that specific object must be the last key. The last key may only be a server ID if the second-to-last key is 'global_servers'.
        """
        if len(keys) <= 2:
            if keys[0] == "servers":
                raise ValueError
        else:
            if keys[0] != "servers":
                raise ValueError

        entries = []
        for command_name, sub_dict in self.all_cmd_settings.items():
            try:
                if len(keys) == 1:
                    is_allowed = sub_dict[keys[0]]
                elif len(keys) == 2:
                    is_allowed = sub_dict[keys[0]][keys[1]]
                elif len(keys) == 3:
                    is_allowed = sub_dict[keys[0]][keys[1]][keys[2]]
                elif len(keys) == 4:
                    is_allowed = sub_dict[keys[0]][keys[1]][keys[2]][keys[3]]
                else:
                    raise ValueError

                if is_allowed is not None:
                    is_allowed = "???" if is_allowed else "???"
                    entries.append(is_allowed + " " + command_name)
            except KeyError:
                pass

        return entries


def setup(bot):
    bot.add_cog(Settings(bot))
