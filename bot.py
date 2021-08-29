# external imports
import discord
from discord.ext import commands
from datetime import datetime, timezone
import aiohttp
import os
import re
import sys
import platform
import logging
from logging.handlers import RotatingFileHandler
import traceback
from copy import copy
from typing import List, Dict

# internal imports
from cogs.utils.io import dev_mail
from cogs.utils.common import get_prefixes_message, get_prefixes_list
from cogs.settings import Dev_Settings


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.presences = False

        super().__init__(intents=intents, command_prefix=self.get_command_prefixes)

        self.add_check(self.check_global_cooldown, call_once=True)

        self.app_info: commands.Bot.AppInfo = None
        self.owner_id: int = None
        self.launch_time = datetime.now(timezone.utc)
        self.global_cd = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user)
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.custom_prefixes: Dict[int, List[str]] = dict()
        self.removed_default_prefixes: Dict[int, List[str]] = dict()
        self.logger: logging.Logger = None
        self.previous_command_ctxs: List[commands.Context] = []
        self.command_use_count = 0
        self.error_is_reported = False

        self.load_default_extensions()


    def load_default_extensions(self) -> None:
        default_extensions = [
            'cogs.docs',
            'cogs.info',
            'cogs.mod',
            'cogs.notes',
            'cogs.other',
            'cogs.owner',
            'cogs.reminders',
            'cogs.settings',
            'cogs.tags',
            'jishaku',
        ]

        for extension in default_extensions:
            self.load_extension(extension)


    def get_command_prefixes(self, bot, message: discord.Message) -> List[str]:
        """Returns the bot's server-aware unrendered command prefixes

        This function is called each time a command is invoked, so the prefixes can be customized based on where the message is from.
        This function is intended to only be used when initializing the bot; to get unrendered prefixes elsewhere, it may be safer to use `bot.command_prefix(bot, message)`.
        """
        prefixes = copy(Dev_Settings.default_bot_prefixes)

        if not message.guild:
            prefixes.append('')
        else:
            try:
                removed_default_prefixes = copy(self.removed_default_prefixes[message.guild.id])
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

        if message.guild and '' in prefixes:
            prefixes.remove('')
        return commands.when_mentioned_or(*prefixes)(bot, message)


    async def close(self):
        await self.db.close()
        await self.session.close()
        await super().close()


    async def on_connect(self):
        print('Loading . . . ')
        await self.wait_until_ready()
        self.app_info = await self.application_info()
        self.owner_id = self.app_info.owner.id
        self.logger = await self.set_up_logger(__name__, logging.INFO)


    async def on_resumed(self):
        print('Resumed . . . ')


    async def on_ready(self):
        # This function may be called many times while the
        # bot is running, so it should not do much.
        print('------------------------------------')
        print(f'Python v{platform.python_version()}')
        print(f'discord.py v{discord.__version__}')
        print(f'{self.user.name}#{self.user.discriminator} ready!')
        print('------------------------------------')


    async def on_message(self, message: discord.Message):
        await self.detect_token(message)
        if message.author.bot:
            return
        if await self.is_only_bot_mention(message):
            await self.answer_mention(message)
        else:
            await self.process_commands(message)


    async def detect_token(self, message: discord.Message) -> None:
        """Detects bot tokens and warns people about them"""
        token_regex = re.compile(r'([a-zA-Z0-9]{24}\.[a-zA-Z0-9]{6}\.[a-zA-Z0-9_\-]{27}|mfa\.[a-zA-Z0-9_\-]{84})')
        match = token_regex.search(message.content)
        if match is not None:
            await self.publish_token(match[0], message)


    async def publish_token(self, discord_bot_token: str, message: discord.Message) -> None:
        """Publishes tokens in GitHub gists to invalidate them and protect bots"""
        url = 'https://api.github.com/gists'
        data = '{"public":true,"files":{"discord-bot-token.txt":{"content":"%s"}}}' % discord_bot_token
        github_token = os.environ['ALTERNATE_GITHUB_GISTS_TOKEN']
        auth = aiohttp.BasicAuth('beep-boop-82197842', password=github_token)

        async with self.session.post(url, data=data, auth=auth) as response:
            if not response.ok:
                raise ValueError(f'GitHub API request failed with status code {response.status}.')

        await message.reply(f'Bot token detected and invalidated! If the token was in use, the bot it belonged to will need to get a new token before being able to reconnect to Discord. For more details, see <https://gist.github.com/beep-boop-82197842/4255864be63966b8618e332d1df30619>')


    async def is_only_bot_mention(self, message: discord.Message) -> bool:
        """Returns True if the entire message is a bot mention"""
        if self.user.mention == message.content.replace('!', '', 1):
            return True
        return False


    async def answer_mention(self, message: discord.Message) -> None:
        """Shows a list of the bot's command prefixes"""
        prefixes = await get_prefixes_list(self, message)
        prefixes_message = await get_prefixes_message(self, message, prefixes)
        
        await message.channel.send(f'Hello {message.author.display_name}! My command {prefixes_message}. Use `{prefixes[0]}help` to get help with commands.')


    async def on_command(self, ctx):
        log_message = f'[author {ctx.author.display_name}][guild {ctx.guild}][command {ctx.message.content}]'
        self.logger.info(log_message)

        self.command_use_count += 1
        await self.save_owners_command(ctx)


    async def save_owners_command(self, ctx) -> None:
        """Saves the owner's commands for easy reuse"""
        if ctx.author.id == self.owner_id:
            if 'reinvoke' not in ctx.command.aliases \
                    and 'reinvoke' != ctx.command.name:
                self.previous_command_ctxs.append(ctx)
                if len(self.previous_command_ctxs) > 5:
                    self.previous_command_ctxs = self.previous_command_ctxs[1:]


    async def on_command_error(self, ctx, error: commands.CommandError):
        if hasattr(ctx.command, 'on_error'):
            return
        if isinstance(error, commands.CommandInvokeError):
            # All errors from command invocations are
            # temporarily wrapped in commands.CommandInvokeError
            error = error.original

        # Exception hierarchy: https://discordpy.readthedocs.io/en/latest/ext/commands/api.html?highlight=permissions#exception-hierarchy
        if isinstance(error, commands.CommandNotFound):
            pass
        elif isinstance(error, commands.DisabledCommand):
            await ctx.send('This command has been disabled.')
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f'Commands on cooldown. Please try again in {error.retry_after:.2f} seconds.')
        elif isinstance(error, commands.UserInputError):
            await ctx.send(error)
        elif isinstance(error, commands.NotOwner):
            await ctx.send('Only the owner can use this command.')
        elif isinstance(error, commands.MissingRole):
            await ctx.send(f'You do not have the necessary role to use this command: {error.missing_role}')
        elif isinstance(error, commands.MissingPermissions):
            message = f'You do not have the necessary permissions to use this command'
            try: message += ': ' + error.missing_perms
            except: pass
            await ctx.send(message)
        elif isinstance(error, commands.BotMissingPermissions):
            perms_needed = ', '.join(error.missing_perms).replace('_', ' ')
            await ctx.send(f'I have not been granted some permission(s) needed for this command to work: {perms_needed}. Permissions can be managed in the server\'s settings.')
            await dev_mail(self, f'The invite link may need to be updated with more permission(s): {perms_needed}')
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send('This command cannot be used in private messages.')
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(f'You do not have access to this command.')
        elif isinstance(error, commands.BadUnionArgument):
            await ctx.send('Error: one or more inputs could not be understood.')
        else:
            tb = traceback.format_exception(type(error), error, error.__traceback__)
            log_message = f'[command {ctx.message.content}][type(error) {type(error)}][error {error}]\n{"".join(tb)}'
            channel = self.get_channel(Dev_Settings.error_log_channel_id)
            await channel.send(log_message)

            if not self.error_is_reported:
                await dev_mail(self, 'I encountered and logged an error')
                self.error_is_reported = True

            await ctx.send('I encountered an error and notified my developer. If you would like to' \
                f' join the support server, here\'s the link: {Dev_Settings.support_server_link}')

            print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


    async def on_guild_join(self, guild: discord.Guild):
        message = 'I\'ve joined a new server called ' \
        f'"{guild.name}"!\nI am now in ' \
        f'{len(self.guilds)} servers.'
        await dev_mail(self, message, use_embed=False)


    async def check_global_cooldown(self, ctx) -> bool:
        """Checks if ctx.author used any command recently
        
        If the user has not triggered the global cooldown, the global
        cooldown is triggered and True is returned. Otherwise, the
        commands.CommandOnCooldown exception is raised.
        This function must be called only once per command
        invocation for the help command to work. So, with
        bot.add_check use call_once=True.
        """
        bucket = self.global_cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()

        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after)
        return True


    async def set_up_logger(self, name: str, level: int) -> logging.Logger:
        """Sets up a logger for this module"""
        # Discord logging guide: https://discordpy.readthedocs.io/en/latest/logging.html#logging-setup
        # Python's intro to logging: https://docs.python.org/3/howto/logging.html#logging-basic-tutorial
        # Documentation for RotatingFileHandler: https://docs.python.org/3/library/logging.handlers.html?#logging.handlers.RotatingFileHandler
        logger = logging.getLogger(name)
        logger.setLevel(level)
        max_bytes = 1024 * 1024  # 1 MiB
        handler = RotatingFileHandler(filename='bot.log', encoding='utf-8', mode='a', maxBytes=max_bytes, backupCount=1)
        formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger
