# External imports
import discord
from discord.ext import commands
from datetime import datetime, timezone
import aiohttp
import sys
import traceback

# Internal imports
from common import dev_mail, get_prefixes_message, get_display_prefixes
from common import dev_settings
from startup import continue_tasks


extensions = [
    'cogs.docs',
    'cogs.help',
    'cogs.music',
    'cogs.other',
    'cogs.owner',
    'cogs.rand',
    'cogs.reminders',
]


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(intents=intents, command_prefix=self.get_command_prefixes)

        for extension in extensions:
            self.load_extension(extension)

        self.launch_time = datetime.now(timezone.utc)
        self.previous_command_ctxs = []
        self.session = aiohttp.ClientSession(loop=self.loop)
        
        self.add_check(self.check_cooldown, call_once=True)


    def get_command_prefixes(self, bot, message):
        prefixes = dev_settings.bot_prefixes
        # TODO: after changing hosts and setting up a new database,
        # allow server-side prefix customization here.
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
        print('------------------------------------')
        print(f'discord.py v{discord.__version__}')
        print(f'{self.user.name}#{self.user.discriminator} ready!')
        print('------------------------------------')


    async def on_message(self, message: str):
        if message.author.bot:
            return
        
        await self.answer_mention(message)
        await self.process_commands(message)


    async def on_command(self, ctx):
        # log_message = f'author: {ctx.author.display_name}; guild: {ctx.guild}; command: {ctx.message.content}'
        # logger.log(COMMANDS, log_message)

        # Save the owner's commands for easy reuse.
        if ctx.author.id == self.owner_id:
            if 'reinvoke' not in ctx.command.aliases \
                    and 'reinvoke' != ctx.command.name:
                self.previous_command_ctxs.append(ctx)
                if len(self.previous_command_ctxs) > 5:
                    self.previous_command_ctxs = self.previous_command_ctxs[1:]


    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(error, commands.CommandOnCooldown):
            if error.cooldown.per <= 3:
                await ctx.send('Command on cooldown.')
            else:
                await ctx.send(f'Command on cooldown. Please try again in {error.retry_after:.2f} seconds.')
        elif isinstance(error, commands.UserInputError):
            await ctx.send(error)
        elif isinstance(error, commands.CheckFailure):
            await ctx.send('Only the owner can use this command.')
        else:
            print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


    async def on_guild_join(self, guild):
        message = f'I\'ve joined a new server called "{guild}"!' \
                f'\nI am now in {len(self.guilds)} servers.'
        await dev_mail(self, message, use_embed=False)


    async def answer_mention(self, message: str):
        """If the entire message is the bot's mention, respond
        
        Show a list of the bot's command prefixes.
        """
        if self.user.mention == message.content.replace('!', '', 1):
            # Get the message author's name.
            nickname = message.author.nick
            if nickname is not None:
                name = nickname.split()[0]
            else:
                name = message.author.name.split()[0]
                
            display_prefixes = await get_display_prefixes(self.bot)
            prefixes_message = await get_prefixes_message(self.bot, display_prefixes)
            
            await message.channel.send(f'Hello {name}! My command {prefixes_message}. Use `{display_prefixes[0]}help` to get help with commands.')


    async def check_cooldown(self, ctx):
        global_cooldown = commands.CooldownMapping.from_cooldown(1, 2, commands.BucketType.user)
        bucket = global_cooldown.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after)
        return True
