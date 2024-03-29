import os
import platform
from datetime import datetime
from datetime import timezone as tz
from functools import lru_cache
from textwrap import dedent
from typing import Mapping

import discord  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/

from cogs.utils.common import get_bot_invite_link
from cogs.utils.common import get_prefixes_list
from cogs.utils.common import get_prefixes_message
from cogs.utils.paginator import Paginator
from cogs.utils.time import create_long_datetime_stamp
from cogs.utils.time import create_relative_timestamp
from cogs.utils.time import format_datetime
from cogs.utils.time import format_timedelta
from cogs.utils.time import parse_time_message


def yes_or_no(boolean: bool) -> str:
    """Returns either 'yes' or 'no'"""
    return "yes" if boolean else "no"


class MyHelp(commands.HelpCommand):
    # Guide on subclassing HelpCommand:
    # https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96
    def __init__(self) -> None:
        super().__init__()
        self.command_attrs = {
            "name": "help",
            "aliases": ["h", "helps", "command", "commands"],
            "help": "Shows help for a command, category, or the entire bot",
        }

    async def get_clean_prefix(self) -> str:
        """Returns the rendered mention command prefix

        May or may not return self.context.prefix.
        """
        if self.context.bot.user.mention + " " == self.context.prefix.replace(
            "!", "", 1
        ):
            return f"@{self.context.bot.user.display_name} "
        return self.context.prefix

    async def get_command_signature(self, command: commands.Command) -> str:
        """Returns a prefix, the command name, and the command argument(s)"""
        prefix = await self.get_clean_prefix()
        return f"{prefix}{command.qualified_name} {command.signature}"

    async def send_bot_help(
        self, mapping: Mapping[commands.Cog | None, list[commands.Command]]
    ) -> None:
        """Gets called with `<prefix>help`"""
        prefix: str = await self.get_clean_prefix()
        help_cmd_name: str = self.context.invoked_with
        message = (
            f"Use `{prefix}{help_cmd_name} [category]` for more info on a category."
            "\n\u200b"
        )
        for cog, commands_ in mapping.items():
            if cog is None:
                continue
            filtered_commands = await self.filter_commands(commands_, sort=True)
            if filtered_commands:
                cog_name = getattr(cog, "qualified_name", "No Category")
                if not cog.description:
                    raise ValueError("Each cog must have a description.")
                cog_short_doc = cog.description.split("\n")[0]
                message += f"\n**__{cog_name}__**: {cog_short_doc}"
        message += "\u200b\n\n"
        support_link: str = self.context.bot.dev_settings.support_server_link
        if support_link:
            message += f"[support server]({support_link}) \u2800❂\u2800 "
        privacy_link: str = self.context.bot.dev_settings.privacy_policy_link
        message += (
            f"[invite]({await get_bot_invite_link(self.context.bot)})"
            f" \u2800❂\u2800 [privacy policy]({privacy_link})"
        )
        membership_link: str = self.context.bot.dev_settings.membership_link
        if membership_link:
            message += f" \u2800❂\u2800 [donate]({membership_link})"
        embed = discord.Embed(description=message)
        destination = self.get_destination()
        await destination.send(embed=embed)

    async def send_cog_help(self, cog: commands.Cog) -> None:
        """Gets called with `<prefix>help <cog>`"""
        cmds = cog.get_commands()
        filtered_commands = await self.filter_commands(cmds, sort=True)
        if not filtered_commands:
            raise commands.BadArgument("You do not have access to this category here.")
        cmd_signatures = []
        for c in filtered_commands:
            signature = await self.get_command_signature(c)
            cmd_signatures.append(f"`{signature}`\n{c.short_doc}")
        prefix: str = await self.get_clean_prefix()
        help_cmd_name: str = self.context.invoked_with
        entries = [cog.description]
        entries.append(
            f"\nUse `{prefix}{help_cmd_name} [command]` for more info on a command."
            " Some command arguments are <required> and others are [optional]."
        )
        entries.append("\n**Commands**")
        entries.extend(cmd_signatures)
        cog_name = getattr(cog, "qualified_name", "No Category")
        paginator = Paginator(
            title=f"{cog_name}",
            entries=entries,
            length=10,
        )
        await paginator.run(self.context)

    async def send_group_help(self, group: commands.Group) -> None:
        """Gets called with `<prefix>help <group>`"""
        message = await self.get_command_signature(group)
        if group.aliases:
            aliases = "**Aliases:** " + ", ".join(group.aliases)
            message += "\n" + aliases
        prefix: str = await self.get_clean_prefix()
        help_cmd_name: str = self.context.invoked_with
        if not help_cmd_name.startswith("help"):
            cmd_parents: list[str] = self.context.invoked_parents
            if cmd_parents:
                help_cmd_name = "help " + " ".join(cmd_parents)
            else:
                help_cmd_name = "help " + help_cmd_name
        message += (
            f"\n\n{group.help}"
            f"\n\nUse `{prefix}{help_cmd_name} [command]` for more info on a command."
            " Some command arguments are <required> and others are [optional]."
            "\n\n**Commands**"
        )
        filtered_commands = await self.filter_commands(group.commands, sort=True)
        for c in filtered_commands:
            message += f"\n{prefix}{c.qualified_name} – {c.short_doc}"
        embed = discord.Embed(description=message)
        destination = self.get_destination()
        await destination.send(embed=embed)

    async def send_command_help(self, command: commands.Command) -> None:
        """Gets called with `<prefix>help <command>`"""
        message = await self.get_command_signature(command)
        if command.aliases:
            aliases = "**Aliases:** " + ", ".join(command.aliases)
            message += "\n" + aliases
        if command.help:
            message += "\n\n" + command.help
        embed = discord.Embed(description=message)
        destination = self.get_destination()
        await destination.send(embed=embed)


class Info(commands.Cog):
    """See info about this bot or the server."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self.old_help_command = bot.help_command
        bot.help_command = MyHelp()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self.old_help_command

    @commands.hybrid_command(name="time", aliases=["clock", "utc"])
    async def _time(self, ctx):
        """Shows the current time in UTC"""
        current_time = await format_datetime(datetime.now(tz.utc))
        now_timestamp = await create_long_datetime_stamp(datetime.now(tz.utc))
        message = (
            f"The current time in UTC is {current_time}\n"
            f"The current time in your device's timezone is {now_timestamp}"
        )
        await ctx.send(message)

    @commands.hybrid_command(name="timestamp", aliases=["ts"])
    async def _timestamp(self, ctx, *, time: str):
        """Shows how you can create timestamps that work with each device's timezone

        You can enter the date/time/duration in natural language, and you can copy and
        paste a raw timestamp into your discord messages. If you have not chosen a
        timezone with the `timezone set` command, UTC will be assumed. The unusual
        number that appears in the raw timestamps is the Unix time.

        Parameters
        ----------
        time: str
            A description of the date and/or time for the timestamp.
        """
        dt, _ = await parse_time_message(ctx, time)
        unix_time = int(dt.timestamp())
        output = dedent(
            f"""
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
            """
        )
        await ctx.send(output)

    #####################
    # bot info commands #
    #####################

    @commands.hybrid_command()
    async def prefixes(self, ctx):
        """Lists the bot's current prefixes for this server"""
        prefixes = await get_prefixes_message(self.bot, ctx.message)
        await ctx.send(f"My current {prefixes}")

    @commands.hybrid_command(hidden=True)
    async def ping(self, ctx):
        """Shows the bot's latency"""
        await ctx.send(f"Pong! Websocket latency: {self.bot.latency * 1000:.2f} ms")

    @commands.hybrid_command(hidden=True)
    async def uptime(self, ctx):
        """Shows the time since the bot last restarted"""
        _uptime = await self.get_uptime()
        await ctx.send(f"Uptime: {_uptime}")

    async def get_uptime(self) -> str:
        """Returns the amount of time the bot has been running"""
        _uptime = datetime.now(tz.utc) - self.bot.launch_time
        time_message = await format_timedelta(_uptime)
        return time_message

    @commands.hybrid_command()
    async def stats(self, ctx):
        """Shows statistics about this bot"""
        embed = discord.Embed()
        try:
            bot_loc = self.count_bot_loc()
        except UnicodeDecodeError:
            bot_loc = -1
        if ctx.interaction:
            author_cmd_count = ""
        else:
            n = await self.count_available_cmds(ctx)
            author_cmd_count = f"commands {ctx.author} can use here: {n}\n"
        embed.add_field(
            name="stats",
            value=dedent(
                f"""\
                websocket latency: {self.bot.latency * 1000:.2f} ms
                uptime: {await self.get_uptime()}
                servers: {len(self.bot.guilds)}
                users: {len(self.bot.users)}
                commands: {len(self.bot.commands)}
                commands used since last restart: {self.bot.command_use_count}
                {author_cmd_count}lines of code: {bot_loc}
                Python files: {self.count_bot_files()}
                """
            ),
        )
        await ctx.send(embed=embed)

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

    @lru_cache
    def count_bot_files(self) -> int:
        """Counts the Python files in the entire bot"""
        if "parhelion" == os.path.basename(os.getcwd()).lower():
            path = "."
        else:
            path = os.path.join(os.getcwd(), "Documents/programming/Parhelion")
            if not os.path.exists(path):
                return -1
        return self.count_dir_files(path)

    def count_dir_files(self, dir_path: str) -> int:
        """Counts the Python files in a directory and its subdirectories"""
        file_count = 0
        for name in os.listdir(dir_path):
            if name in (".git", ".vs", ".vscode", "__pycache__"):
                continue
            if name.startswith("venv"):
                continue
            if name.lower().startswith("python"):
                continue
            path = os.path.join(dir_path, name)
            if os.path.isdir(path):
                file_count += self.count_dir_files(path)
            elif os.path.isfile(path):
                if path.endswith(".py"):
                    file_count += 1
        return file_count

    @lru_cache
    def count_bot_loc(self) -> int:
        """Counts the lines of Python code in the entire bot"""
        if "parhelion" == os.path.basename(os.getcwd()).lower():
            path = "."
        else:
            path = os.path.join(os.getcwd(), "Documents/programming/Parhelion")
            if not os.path.exists(path):
                return -1
        return self.count_dir_loc(path)

    def count_dir_loc(self, dir_path: str) -> int:
        """Counts the lines of Python code in a directory and its subdirectories"""
        line_count = 0
        for name in os.listdir(dir_path):
            if name in (".git", ".vs", ".vscode", "__pycache__"):
                continue
            if name.startswith("venv"):
                continue
            if name.lower().startswith("python"):
                continue
            path = os.path.join(dir_path, name)
            if os.path.isdir(path):
                line_count += self.count_dir_loc(path)
            elif os.path.isfile(path):
                if path.endswith(".py"):
                    with open(path, encoding="utf8") as file:
                        line_count += len(file.readlines())
        return line_count

    @commands.hybrid_command(hidden=True)
    async def invite(self, ctx):
        """Shows the link to invite this bot to another server"""
        bot_invite_link = await get_bot_invite_link(self.bot)
        await ctx.send(
            f"Here's the link to invite me to another server: <{bot_invite_link}>"
        )

    @commands.hybrid_command(aliases=["contact", "server"], hidden=True)
    async def support(self, ctx):
        """Shows the link to this bot's support server"""
        if self.bot.dev_settings.support_server_link:
            await ctx.send(
                "Here's the link to my support server:"
                f" <{self.bot.dev_settings.support_server_link}>"
            )
        else:
            await ctx.send("A support server has not been set by the developer.")

    @commands.hybrid_command(aliases=["privacy-policy", "privacypolicy"], hidden=True)
    async def privacy(self, ctx):
        """Shows the link to this bot's privacy policy"""
        await ctx.send(
            f"Here's my privacy policy: <{self.bot.dev_settings.privacy_policy_link}>"
        )

    @commands.hybrid_command()
    async def donate(self, ctx):
        """Help keep the server running and support the bot's development"""
        if self.bot.dev_settings.membership_link:
            await ctx.send(
                "Thanks for your interest! You can support this project here:"
                f" <{self.bot.dev_settings.membership_link}>"
            )
        else:
            await ctx.send(
                "Thanks for your interest! However, donations are currently not being"
                " accepted."
            )

    @commands.hybrid_command(aliases=["i", "info"])
    async def about(self, ctx) -> None:
        """Shows general info about this bot"""
        embed = discord.Embed()
        owner = self.bot.get_user(self.bot.owner_id)
        prefixes: list[str] = await get_prefixes_list(self.bot, ctx.message)
        shortest_nonslash_prefix = None
        for p in prefixes:
            if p != "/":
                shortest_nonslash_prefix = p
                break
        py_info = f"Python v{platform.python_version()}"
        discord_link = "[discord.py](https://discordpy.readthedocs.io/en/latest/)"
        discord_info = f"{discord_link} v{discord.__version__}"
        links_s = ""
        support_link: str = self.bot.dev_settings.support_server_link
        if support_link:
            links_s += f"[support server]({support_link}) \u2800❂\u2800 "
        privacy_link: str = self.bot.dev_settings.privacy_policy_link
        links_s += (
            f"[invite]({await get_bot_invite_link(self.bot)})"
            f" \u2800❂\u2800 [privacy policy]({privacy_link})"
        )
        if self.bot.dev_settings.membership_link:
            links_s += (
                f" \u2800❂\u2800 [donate]({self.bot.dev_settings.membership_link})"
            )
        help_instruction = ""
        if ctx.bot_permissions.read_messages:
            help_instruction = (
                f"Use `{shortest_nonslash_prefix}help` for help with commands.\n\n"
            )
        embed.add_field(
            name=f"{self.bot.user.name} {self.bot.dev_settings.version}",
            value=dedent(
                f"""
                \u200b
                {help_instruction}{links_s}

                **owner**
                {owner.name}

                **made with**
                {py_info} and {discord_info}
                """
            ),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(hidden=True)
    async def source(self, ctx):
        """See the bot's source code!"""
        await ctx.send("https://github.com/wheelercj/Parhelion")

    @commands.hybrid_command()
    async def tips(self, ctx):
        """Shows tips on how to use this bot"""
        _tips = [
            "For each command with a hyphen in its name, typing the hyphen is"
            " optional.",
            "Most commands have aliases that are easier to type; see a command's"
            f" aliases with `{ctx.prefix}help [command]`.",
        ]
        paginator = Paginator(
            title="tips",
            entries=_tips,
            length=10,
            prefix="•",
        )
        await paginator.run(ctx)

    #########################
    # Discord info commands #
    #########################

    @commands.hybrid_command()
    @commands.guild_only()
    async def avatar(self, ctx, *, member: discord.Member):
        """Shows a member's avatar

        Parameters
        ----------
        member: discord.Member
            The member to view the avatar of.
        """
        if member.avatar is None:
            await ctx.send(f"{member.nick} does not have an avatar.")
        else:
            await ctx.send(member.avatar)

    @commands.hybrid_command(
        name="server-info",
        aliases=["si", "gi", "serverinfo", "guild-info", "guildinfo"],
    )
    @commands.guild_only()
    async def server_info(self, ctx):
        """Shows info about the current server"""
        if ctx.guild.unavailable:
            raise commands.UserInputError("The server's data is unavailable.")
        server = self.bot.get_guild(ctx.guild.id)
        bot_count = await self.get_bot_count(server)
        cat_count = len(server.categories)
        created = await create_relative_timestamp(server.created_at)
        member_count = f"{server.member_count}/{server.max_members} ({bot_count} bots)"
        embed = discord.Embed(title="server info")
        embed.add_field(
            name="\u200b",
            value=dedent(
                f"""\
                name: {server.name}
                owner: {server.owner.name}
                description: {server.description}
                created: {created}
                preferred locale: {server.preferred_locale}
                total members: {member_count}
                roles: {len(server.roles)}
                current boosts: {server.premium_subscription_count}
                boost level: {server.premium_tier}
                emojis: {len(server.emojis)}/{server.emoji_limit}
                file size limit: {server.filesize_limit / 1000000:.2f} MB
                bitrate limit: {server.bitrate_limit / 1000} kbps

                **channels**
                categories: {cat_count}
                total channels: {len(server.channels) - cat_count}
                text channels: {len(server.text_channels)}
                voice channels: {len(server.voice_channels)}
                stages: {len(server.stage_channels)}
                max video channel users: {server.max_video_channel_users}
                """
            ),
        )
        features = await self.get_server_features(server)
        if len(features):
            embed.add_field(name="\u2800", value="**features**\n" + features)
        if server.icon is not None:
            embed.set_thumbnail(url=server.icon)
        await ctx.send(embed=embed)

    async def get_bot_count(self, server: discord.Guild) -> int:
        """Counts the bots in the server"""
        return sum(m.bot for m in server.members)

    async def get_server_features(self, server: discord.Guild) -> str:
        """Gets the server's features or returns any empty string if there are none"""
        features = ""
        for feature in sorted(server.features):
            features += "\n• " + feature.replace("_", " ").lower()
        return features

    @commands.hybrid_command(
        name="member-info",
        aliases=["mi", "ui", "whois", "who-is", "memberinfo", "user-info", "userinfo"],
    )
    @commands.guild_only()
    async def member_info(self, ctx, *, member: discord.Member):
        """Shows info about a member of the current server

        To see member permissions, use the `info perms` command.

        Parameters
        ----------
        member: discord.Member
            The member to view info about.
        """
        creation_timestamp = await create_relative_timestamp(member.created_at)
        join_timestamp = await create_relative_timestamp(member.joined_at)
        embed = discord.Embed()
        embed.add_field(
            name=f"{member.name}\n\u2800",
            value=(
                f"**display name:** {member.display_name}\n"
                f"{await self.get_whether_bot(member)}"
                f"**account created:** {creation_timestamp}\n"
                f"**joined server:** {join_timestamp}\n"
                f"**top server role:** {member.top_role}\n"
                f"{await self.get_server_roles(member)}"
                f"{await self.get_premium_since(member)}"
                f"{await self.get_global_roles(member)}"
            ),
        )
        if member.avatar is not None:
            embed.set_thumbnail(url=member.avatar)
        await ctx.send(embed=embed)

    async def get_whether_bot(self, member: discord.Member) -> str:
        """Returns a message if member is a bot, otherwise returns an empty string"""
        if member.bot:
            return f"**{member.display_name} is a bot**\n"
        else:
            return ""

    async def get_server_roles(self, member: discord.Member) -> str:
        """Returns a message listing all of a member's server roles if len(roles) <= 10

        Otherwise returns an empty string.
        """
        if len(member.roles) <= 10:
            return "**server roles:** " + ", ".join(x.name for x in member.roles)
        else:
            return ""

    async def get_premium_since(self, member: discord.Member) -> str:
        """Gets the datetime of when a member's premium began

        Returns an empty string if the member does not have premium.
        """
        r = member.premium_since
        if r is not None:
            return f"**premium since:** {r}\n"
        else:
            return ""

    async def get_global_roles(self, member: discord.Member) -> str:
        """Gets the global Discord roles of a member

        For example, Discord staff, bug hunter, verified bot, etc. Returns an empty
        string if the member has no global roles.
        """
        flags = ", ".join(member.public_flags.all())
        if len(flags):
            return f"**global roles:**: {flags}\n"
        else:
            return ""

    @commands.hybrid_command(name="role-info", aliases=["ri", "roleinfo"])
    @commands.guild_only()
    async def role_info(self, ctx, *, role: discord.Role):
        """Shows info about a role on the current server

        To see role permissions, use the `info perms` command.

        Parameters
        ----------
        role: discord.Role
            The role to view info about.
        """
        managing_bot = None
        creation_timestamp = await create_relative_timestamp(role.created_at)
        if role.tags is not None:
            if role.tags.bot_id is not None:
                managing_bot = ctx.guild.get_member(role.tags.bot_id)
        embed = discord.Embed()
        embed.add_field(
            name="role info",
            value=dedent(
                f"""\
                name: {role.name}
                members: {len(role.members)}
                hierarcy position: {role.position}
                created: {creation_timestamp}
                mentionable: {yes_or_no(role.mentionable)}
                default: {yes_or_no(role.is_default())}
                premium: {yes_or_no(role.is_premium_subscriber())}
                3rd-party integration: {yes_or_no(role.managed)}
                managing bot: {managing_bot}
                """
            ),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="permissions", aliases=["perms"])
    @commands.guild_only()
    async def server_permissions(
        self, ctx, *, member_or_role: discord.Member | discord.Role | None = None
    ) -> None:
        """Shows the server and channel permissions of a member or role

        If a user and role have the same ID and/or name, the permissions for the user
        will be shown. User permissions include the permissions for all roles that user
        has.

        Parameters
        ----------
        member_or_role: discord.Member | discord.Role | None
            The member or role to view permissions of.
        """
        if member_or_role is None:
            member_or_role = ctx.author
        server_perms, overwrites, title = await self.get_perms(ctx, member_or_role)
        if not server_perms:
            raise commands.BadArgument("Could not find the user or role.")
        embed = discord.Embed(title=title)
        embed.add_field(name="server permissions", value=server_perms)
        if overwrites:
            embed = await self.embed_overwrites(embed, server_perms, overwrites)
        await ctx.send(embed=embed)

    async def embed_overwrites(
        self, embed: discord.Embed, server_perms: str | bool, overwrites: str
    ) -> discord.Embed:
        """Adds embed fields listing channel perm overwrites of server perms"""
        server_n = 0 if isinstance(server_perms, bool) else server_perms.count("\n")
        channel_n = overwrites.count("\n")
        if server_n > channel_n:
            embed.add_field(name="channel overwrites", value=overwrites)
        else:
            half = channel_n // 2
            embed.add_field(name="channel overwrites", value=overwrites[:half])
            embed.add_field(name="channel overwrites cont.", value=overwrites[half:])
        return embed

    async def format_perms(self, permissions: discord.Permissions) -> str | bool:
        """Converts a permissions object to a printable string

        Returns False if the permissions are for a hidden text channel.
        """
        if not permissions.read_messages and permissions.read_messages is not None:
            return False
        perm_list = sorted(list(permissions), key=lambda x: x[0])
        return await self.perm_list_message(perm_list)

    async def get_perms(
        self, ctx, member_or_role: discord.Member | discord.Role
    ) -> tuple[str | bool, str, str]:
        """Gets the formatted server perms, channel overwrites, and embed title

        The value of the returned server permissions is False if the permissions are for
        a hidden text channel.
        """
        if isinstance(member_or_role, discord.Member):
            member = member_or_role
            server_perms = await self.format_perms(member.guild_permissions)
            overwrites = await self.get_perm_overwrites(ctx, member)
            title = f"{member.name}'s permissions"
            return server_perms, overwrites, title
        elif isinstance(member_or_role, discord.Role):
            role = member_or_role
            if role is not None:
                server_perms = await self.format_perms(role.permissions)
                overwrites = await self.get_perm_overwrites(ctx, role)
                title = f"{role.name} role permissions"
                return server_perms, overwrites, title
        return "", "", ""

    async def get_perm_overwrites(
        self, ctx, member_or_role: discord.Member | discord.Role
    ) -> str:
        """Gets the permissions for each channel that overwrite the server permissions

        Any hidden text channels are not named, but counted.
        """
        overwrites = ""
        hidden_text_count = 0
        for channel in ctx.guild.channels:
            channel_perms = await self.format_perms(
                channel.overwrites_for(member_or_role)
            )
            if not channel_perms and channel_perms != "" and channel.category:
                hidden_text_count += 1
            elif channel_perms:
                overwrites += f"**\u2800{channel.name}**\n" f"{channel_perms}\n"
        if hidden_text_count:
            overwrites += (
                f"**\u2800({hidden_text_count} hidden text channels)**\n"
                f"\u2800❌ read messages\n"
            )
        return overwrites

    async def perm_list_message(self, perm_list: list[tuple[str, bool]]) -> str:
        """Converts a permissions list to a printable string

        perm_list is a list of tuples in the format (perm_name, is_perm_granted). Using
        `list(perm_obj)` where `perm_obj` is of type discord.Permissions gives the
        correct format. If a permission's bool is set to None, the permission will be
        ignored.
        """
        perm_str = ""
        for name, value in perm_list:
            name = name.replace("_", " ")
            if value:
                perm_str += f"\u2800✅ {name}\n"
            elif value is not None:
                perm_str += f"\u2800❌ {name}\n"
        return perm_str


async def setup(bot):
    await bot.add_cog(Info(bot))
