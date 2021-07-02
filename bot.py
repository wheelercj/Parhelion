# External imports
import discord
from discord.ext import commands
from datetime import datetime, timezone
import aiohttp
import sys
import traceback
from copy import copy
from typing import List

# Internal imports
from common import dev_settings, dev_mail, get_prefixes_message, get_display_prefixes
from startup import continue_tasks


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents, command_prefix=self.get_command_prefixes)

        self.load_default_extensions()

        self.launch_time = datetime.now(timezone.utc)
        self.previous_command_ctxs = []
        self.session = aiohttp.ClientSession(loop=self.loop)
        
        self.add_check(self.check_global_cooldown, call_once=True)


    def load_default_extensions(self):
        default_extensions = [
            'cogs.admin',
            'cogs.help',
            'cogs.info',
            'cogs.music',
            'cogs.other',
            'cogs.owner',
            'cogs.rand',
            'cogs.reminders',
        ]

        for extension in default_extensions:
            self.load_extension(extension)


    def get_command_prefixes(self, bot, message: discord.Message) -> List[str]:
        """Returns the bot's command prefixes
        
        This function is called each time a command is invoked,
        and so the prefixes can be customized based on where
        the message is from.
        """
        prefixes = copy(dev_settings.default_bot_prefixes)
        # TODO: after changing hosts and setting up a new
        # database, allow server-side prefix customization
        # here.
        
        if not message.guild:
            prefixes.append('')
        
        return commands.when_mentioned_or(*prefixes)(bot, message)


    async def close(self):
        await super().close()
    

    async def on_connect(self):
        print('Loading . . . ')
        await self.wait_until_ready()
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
        if message.author.bot:
            return
        if await self.is_only_bot_mention(message):
            await self.answer_mention(message)
        else:
            await self.process_commands(message)


    async def is_only_bot_mention(self, message: discord.Message):
        """Returns True if the entire message is a bot mention"""
        if self.user.mention == message.content.replace('!', '', 1):
            return True
        return False


    async def on_command(self, ctx):
        await self.save_owners_command(ctx)


    async def save_owners_command(self, ctx):
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

        # Exception hierarchy: https://discordpy.readthedocs.io/en/latest/ext/commands/api.html?highlight=permissions#exception-hierarchy
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f'Command not found.')
        elif isinstance(error, commands.DisabledCommand):
            await ctx.send('This command has been disabled.')
        elif isinstance(error, commands.CommandOnCooldown):
            if error.cooldown.per <= 3:
                # The global cooldown was triggered, and error.retry_after is inaccurate.
                await ctx.send('Command on cooldown.')
            else:
                await ctx.send(f'Command on cooldown. Please try again in {error.retry_after:.2f} seconds.')
        elif isinstance(error, commands.UserInputError):
            await ctx.send(error)
        elif isinstance(error, commands.NotOwner):
            await ctx.send('Only the owner can use this command.')
        elif isinstance(error, commands.MissingRole):
            await ctx.send(f'You do not have the necessary role to use this command: {error.missing_role}')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(f'You do not have the necessary permissions to use this command: {error.missing_perms}')
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(f'This server has not given the bot the permissions needed for this command to work: {error.missing_perms}')
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send('This command cannot be used in private messages.')
        else:
            print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


    async def on_guild_join(self, guild: discord.Guild):
        message = 'I\'ve joined a new server called ' \
        f'"{guild.name}"!\nI am now in ' \
        f'{len(self.guilds)} servers.'
        await dev_mail(self, message, use_embed=False)


    async def answer_mention(self, message: discord.Message):
        """Shows a list of the bot's command prefixes"""
        display_prefixes = await get_display_prefixes(self, message)
        prefixes_message = await get_prefixes_message(self, message, display_prefixes)
        
        await message.channel.send(f'Hello {message.author.display_name}! My command {prefixes_message}. Use `{display_prefixes[0]}help` to get help with commands.')


    async def check_global_cooldown(self, ctx):
        """Checks if ctx.author used any command recently
        
        Returns True if the user has not triggered the global
        cooldown, raises commands.CommandOnCooldown otherwise.
        This function must be called only once per command
        invocation for the help command to work. So, with
        bot.add_check use call_once=True.
        """
        global_cooldown = commands.CooldownMapping.from_cooldown(1, 2, commands.BucketType.user)
        bucket = global_cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after)
        return True
