import logging
import os
import platform
import re
import sys
import traceback
from copy import copy
from datetime import datetime
from datetime import timezone
from logging.handlers import RotatingFileHandler
from typing import Any
from typing import Callable
from typing import Union

import aiohttp  # https://pypi.org/project/aiohttp/
import discord  # https://pypi.org/project/discord.py/
from discord import app_commands  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/

from cogs.utils.common import DevSettings
from cogs.utils.common import get_prefixes_list
from cogs.utils.common import get_prefixes_message
from cogs.utils.io import dev_mail


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = False
        super().__init__(intents=intents, command_prefix=self.get_command_prefixes)
        self.add_check(self.check_global_cooldown, call_once=True)
        self.global_cd = commands.CooldownMapping.from_cooldown(
            1, 5, commands.BucketType.user
        )
        self.tree.on_error = self.on_app_command_error
        self.app_info: commands.Bot.AppInfo = None
        self.owner_id: int = None
        self.launch_time = datetime.now(timezone.utc)
        connector = aiohttp.TCPConnector(force_close=True)
        self.session = aiohttp.ClientSession(connector=connector)
        self.custom_prefixes: dict[int, list[str]] = dict()
        self.removed_default_prefixes: dict[int, list[str]] = dict()
        self.logger: logging.Logger = None
        self.previous_command_ctxs: list[commands.Context] = []
        self.command_use_count = 0
        self.error_is_reported = False

    async def setup_hook(self) -> None:
        default_extensions = [
            "cogs.docs",
            "cogs.info",
            "cogs.mod",
            "cogs.notes",
            "cogs.other",
            "cogs.owner",
            "cogs.reminders",
            "cogs.settings",
            "cogs.tags",
            "jishaku",
        ]
        for extension in default_extensions:
            await self.load_extension(extension)

    def get_command_prefixes(self, bot, message: discord.Message) -> list[str]:
        """Returns the bot's server-aware unrendered command prefixes

        This function is called each time a command is invoked, so the prefixes can be
        customized based on where the message is from. This function is intended to only
        be used when initializing the bot; to get unrendered prefixes elsewhere, it may
        be safer to use `bot.command_prefix(bot, message)`.
        """
        prefixes = copy(DevSettings.default_bot_prefixes)
        if not message.guild:
            prefixes.append("")
        else:
            try:
                removed_default_prefixes = copy(
                    self.removed_default_prefixes[message.guild.id]
                )
                if removed_default_prefixes is not None:
                    for p in removed_default_prefixes:
                        prefixes.remove(p)
            except KeyError:
                pass
            try:
                custom_prefixes = copy(self.custom_prefixes[message.guild.id])
                if custom_prefixes is not None:
                    prefixes.extend(custom_prefixes)
            except KeyError:
                pass
        if message.guild and "" in prefixes:
            prefixes.remove("")
        return commands.when_mentioned_or(*prefixes)(bot, message)

    async def close(self) -> None:
        self.logger.info("Shutting down . . .")
        await self.db.close()
        await self.session.close()
        await super().close()

    async def on_connect(self) -> None:
        print("Loading . . . ")
        await self.wait_until_ready()
        self.app_info = await self.application_info()
        self.owner_id = self.app_info.owner.id
        self.logger = await self.set_up_logger()
        self.logger.info("Loading . . .")

    async def on_resumed(self) -> None:
        print("Resumed . . . ")

    async def on_ready(self) -> None:
        # This function may be called many times while the
        # bot is running, so it should not do much.
        print("------------------------------------")
        print(f"Python v{platform.python_version()}")
        print(f"discord.py v{discord.__version__}")
        print(f"{self.user.name}#{self.user.discriminator} ready!")
        print("------------------------------------")

    async def on_message(self, message: discord.Message) -> None:
        await self.detect_token(message)
        if message.author.bot:
            return
        if await self.is_only_bot_mention(message):
            await self.answer_mention(message)
        else:
            await self.process_commands(message)

    async def detect_token(self, message: discord.Message) -> None:
        """Detects bot tokens and warns people about them"""
        token_regex = re.compile(
            r"([a-zA-Z0-9]{24}\.[a-zA-Z0-9]{6}\.[a-zA-Z0-9_\-]{27}"
            r"|mfa\.[a-zA-Z0-9_\-]{84})"
        )
        match = token_regex.search(message.content)
        if match is not None:
            await self.publish_token(match[0], message)

    async def publish_token(
        self, discord_bot_token: str, message: discord.Message
    ) -> None:
        """Publishes tokens in GitHub gists to invalidate them and protect bots"""
        url = "https://api.github.com/gists"
        data = (
            '{"public":true,"files":{"discord-bot-token.txt":{"content":"%s"}}}'
            % discord_bot_token
        )
        github_account_name = os.environ["alternate_github_account_name"]
        github_token = os.environ["alternate_github_gists_token"]
        auth = aiohttp.BasicAuth(github_account_name, password=github_token)
        async with self.session.post(url, data=data, auth=auth) as response:
            if not response.ok:
                raise ValueError(
                    f"GitHub API request failed with status code {response.status}."
                )
        await message.reply(
            "Bot token detected and invalidated! If the token was in use, the bot it"
            " belonged to will need to get a new token before being able to reconnect"
            " to Discord. For more details, see"
            " <https://gist.github.com/beep-boop-82197842/"
            "4255864be63966b8618e332d1df30619>"
        )

    async def is_only_bot_mention(self, message: discord.Message) -> bool:
        """Returns True if the entire message is a bot mention"""
        return self.user.mention == message.content.replace("!", "", 1)

    async def answer_mention(self, message: discord.Message) -> None:
        """Shows a list of the bot's command prefixes"""
        prefixes: list[str] = await get_prefixes_list(self, message)
        shortest_nonslash_prefix = None
        for p in prefixes:
            if p != "/":
                shortest_nonslash_prefix = p
                break
        prefixes_message = await get_prefixes_message(self, message, prefixes)
        await message.channel.send(
            f"Hello {message.author.display_name}! My command {prefixes_message}. Use"
            f" `{shortest_nonslash_prefix}help` to get help with commands."
        )

    async def on_command(self, ctx):
        log_message = (
            f"[author {ctx.author.name}#{ctx.author.discriminator}]"
            f"[guild {ctx.guild}]"
            f"[command {ctx.clean_prefix}{ctx.command.qualified_name}]"
        )
        self.logger.info(log_message)
        self.command_use_count += 1
        await self.save_owners_command(ctx)

    async def save_owners_command(self, ctx) -> None:
        """Saves the owner's commands for easy reuse"""
        if ctx.author.id == self.owner_id:
            if "reinvoke" not in ctx.command.aliases and "reinvoke" != ctx.command.name:
                self.previous_command_ctxs.append(ctx)
                if len(self.previous_command_ctxs) > 5:
                    self.previous_command_ctxs = self.previous_command_ctxs[1:]

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        messages = [
            f"Ignoring exception in {event_method}, which was called",
            "with args:",
        ]
        for arg in args:
            messages.append(f"  {type(arg)}: {arg}")
        if not args:
            messages.append("  (none)")
        messages.append("with kwargs:")
        for k, v in kwargs.items():
            messages.append(f"  {k} = {v}")
        if not kwargs:
            messages.append("  (none)")
        messages.append(f"{traceback.format_exc()}")
        message = "\n".join(messages)
        print(message)
        self.logger.error(message)

    async def on_command_error(self, ctx, error: commands.CommandError) -> None:
        """Handles errors from commands that are NOT app commands"""
        if hasattr(ctx.command, "on_error"):
            return
        await self.on_any_command_error(ctx.send, ctx.command.name, error)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Handles errors from app commands"""
        await self.on_any_command_error(
            interaction.response.send_message, interaction.command.name, error
        )

    async def on_any_command_error(
        self,
        send: Callable,
        cmd_name: str,
        error: Union[app_commands.AppCommandError, commands.CommandError],
    ) -> None:
        """Handles errors from both app commands and other commands"""
        if isinstance(error, commands.CommandInvokeError):
            # All errors from command invocations are
            # temporarily wrapped in commands.CommandInvokeError
            error = error.original
        # Exception hierarchy:
        # https://discordpy.readthedocs.io/en/latest/ext/commands/api.html?highlight=permissions#exception-hierarchy  # noqa: E501
        if isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, commands.DisabledCommand):
            await send("This command has been disabled.", ephemeral=True)
        elif isinstance(error, commands.UserInputError):
            await send(error, ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            await send(
                f"Commands on cooldown. Please try again in {error.retry_after:.2f}"
                " seconds.",
                ephemeral=True,
            )
        elif isinstance(error, commands.NotOwner):
            await send("Only the owner can use this command.", ephemeral=True)
        elif isinstance(error, commands.MissingRole):
            await send(
                "You do not have the necessary role to use this command:"
                f" {error.missing_role}",
                ephemeral=True,
            )
        elif isinstance(error, commands.MissingPermissions):
            message = "You do not have the necessary permissions to use this command"
            try:
                message += ": " + error.missing_permissions
            except Exception:
                pass
            await send(message, ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            perms_needed = ", ".join(error.missing_permissions).replace("_", " ")
            await send(
                "I have not been granted some permission(s) needed for this command to"
                f" work: {perms_needed}. Permissions can be managed in the server's"
                " settings."
            )
            await dev_mail(
                self,
                "The invite link may need to be updated with more permission(s):"
                f" {perms_needed}",
            )
        elif isinstance(error, commands.NoPrivateMessage):
            await send("This command cannot be used in private messages.")
        elif isinstance(error, commands.CheckFailure):
            await send("You do not have access to this command.", ephemeral=True)
        elif isinstance(error, commands.BadUnionArgument):
            await send(
                "Error: one or more inputs could not be understood.", ephemeral=True
            )
        else:
            tb = traceback.format_exception(type(error), error, error.__traceback__)
            message = (
                f"[command {cmd_name}]"
                f"[type(error) {type(error)}]"
                f"[error {error}]"
                f'\n{"".join(tb)}'
            )
            self.logger.error(message)
            print(f"Ignoring exception in command {cmd_name}:", file=sys.stderr)
            traceback.print_exception(
                type(error), error, error.__traceback__, file=sys.stderr
            )
            if not self.error_is_reported and self.logger.level <= logging.ERROR:
                await dev_mail(self, "I encountered and logged an error")
                self.error_is_reported = True
            if not DevSettings.support_server_link:
                await send(
                    "I encountered an error and notified my developer.",
                    ephemeral=True,
                )
            else:
                await send(
                    "I encountered an error and notified my developer. If you would"
                    " like to join the support server, here's the link:"
                    f" {DevSettings.support_server_link}",
                    ephemeral=True,
                )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        message = (
            f"I've joined a new server called `{guild.name}`!\nI am now in "
            f"{len(self.guilds)} servers."
        )
        await dev_mail(self, message, use_embed=False)

    async def check_global_cooldown(self, ctx) -> bool:
        """Checks if ctx.author used any command recently

        If the user has not triggered the global cooldown, the global cooldown is
        triggered and True is returned. Otherwise, the commands.CommandOnCooldown
        exception is raised. This function must be called only once per command
        invocation for the help command to work. So, with bot.add_check use
        call_once=True.
        """
        bucket = self.global_cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(
                bucket, retry_after, commands.BucketType.user
            )
        return True

    async def set_up_logger(self) -> logging.Logger:
        """Sets up a logger for the bot"""
        # Discord logging guide:
        # https://discordpy.readthedocs.io/en/stable/logging.html
        # Python's intro to logging:
        # https://docs.python.org/3/howto/logging.html#logging-basic-tutorial
        # Documentation for RotatingFileHandler:
        # https://docs.python.org/3/library/logging.handlers.html?#logging.handlers.RotatingFileHandler  # noqa: E501
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(
            filename="bot.log",
            encoding="utf-8",
            mode="a",
            maxBytes=50000,  # 50 kB, which might be Discord's max file preview size.
            backupCount=10,
        )
        formatter = logging.Formatter(
            "{asctime}[{levelname}]{message}", datefmt="%Y-%m-%d %H:%M:%S", style="{"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
