# external imports
import discord
from discord.ext import commands
from datetime import datetime
import aiohttp
import json
import os
import re
import sys
import logging
import traceback
from copy import copy
from typing import List, Dict

# internal imports
from common import dev_settings, dev_mail, get_prefixes_message, get_prefixes_list
from startup import continue_tasks, load_all_custom_prefixes, set_up_logger
from cogs.settings import CmdSettings


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents, command_prefix=self.get_command_prefixes)

        self.add_check(self.check_global_cooldown, call_once=True)

        self.app_info: commands.Bot.AppInfo = None
        self.owner_id: int = None
        self.launch_time = datetime.utcnow()
        self.global_cd = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user)
        self.all_cmd_settings: Dict[str, CmdSettings] = dict()
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.custom_prefixes: Dict[int, List[str]] = load_all_custom_prefixes()
        self.logger: logging.Logger = None
        self.previous_command_ctxs: List[commands.Context] = []
        self.command_use_count = 0

        self.load_default_extensions()


    def load_default_extensions(self) -> None:
        default_extensions = [
            'cogs.help',
            'cogs.info',
            'cogs.mod',
            'cogs.music',
            'cogs.other',
            'cogs.owner',
            'cogs.quotes',
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
        prefixes = copy(dev_settings.default_bot_prefixes)

        if not message.guild:
            prefixes.append('')
        else:
            try:
                server_prefixes = copy(self.custom_prefixes[message.guild.id])
                for p in server_prefixes:
                    if p.startswith('␝'):
                        prefixes.remove(p[1:])
                    else:
                        prefixes.append(p)
            except KeyError:
                pass

        if message.guild and '' in prefixes:
            prefixes.remove('')
        return commands.when_mentioned_or(*prefixes)(bot, message)


    async def save_all_custom_prefixes(self) -> None:
        """Saves all the custom prefixes for all servers"""
        with open('custom_prefixes.json', 'w') as file:
            json.dump(self.custom_prefixes, file)
            # This converts all the integer keys to strings
            # because JSON dict keys cannot be ints.


    async def close(self):
        await self.db.close()
        await super().close()


    async def on_connect(self):
        print('Loading . . . ')
        await self.wait_until_ready()

        self.app_info = await self.application_info()
        self.owner_id = self.app_info.owner.id
        self.logger = await set_up_logger(__name__, logging.INFO)

        await continue_tasks(self)


    async def on_resumed(self):
        print('Resumed . . . ')


    async def on_ready(self):
        # This function may be called many times while the
        # bot is running, so it should not do much.
        print('------------------------------------')
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
        # if isinstance(error, commands.CommandNotFound):
        #     await ctx.send(f'Command not found.')
        if isinstance(error, commands.DisabledCommand):
            await ctx.send('This command has been disabled.')
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f'Commands on cooldown. Please try again in {error.retry_after:.2f} seconds.')
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(f'This command is disabled.')
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
        elif isinstance(error, commands.BadUnionArgument):
            await ctx.send('Error: one or more inputs could not be understood.')
        else:
            print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


    async def on_guild_join(self, guild: discord.Guild):
        message = 'I\'ve joined a new server called ' \
        f'"{guild.name}"!\nI am now in ' \
        f'{len(self.guilds)} servers.'
        await dev_mail(self, message, use_embed=False)


    async def answer_mention(self, message: discord.Message) -> None:
        """Shows a list of the bot's command prefixes"""
        prefixes = await get_prefixes_list(self, message)
        prefixes_message = await get_prefixes_message(self, message, prefixes)
        
        await message.channel.send(f'Hello {message.author.display_name}! My command {prefixes_message}. Use `{prefixes[0]}help` to get help with commands.')


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
