# External imports
from replit import db
import os
import sys
import discord
from discord.ext import commands
import logging
import traceback
from datetime import datetime, timezone

# Internal imports
from common import dev_mail, get_prefixes_str, BOT_MENTION
from keep_alive import keep_alive
from cogs.reminders import continue_reminder


# Discord logging guide: https://discordpy.readthedocs.io/en/latest/logging.html#logging-setup
# Python's intro to logging: https://docs.python.org/3/howto/logging.html#logging-basic-tutorial
logger = logging.getLogger('discord')
COMMANDS = 25  # Logs each command use (as well as warnings, errors, and criticals).
logger.setLevel(COMMANDS)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=(';', 'par ', 'Par ', BOT_MENTION), intents=intents)

# Custom bot variables.
bot.launch_time = datetime.now(timezone.utc)
bot.previous_command_ctxs = []


extensions = [
    'cogs.docs',
    'cogs.music',
    'cogs.other',
    'cogs.owner',
    'cogs.rand',
    'cogs.reminders',
]


if __name__ == '__main__':
    for extension in extensions:
        bot.load_extension(extension)


@bot.event
async def on_connect():
    print('Loading . . . ')
    await bot.wait_until_ready()
    for key in db.keys():
        await continue_reminder(bot, db[key])


@bot.event
async def on_ready():
    print('------------------------------------')
    print(f'Discord v{discord.__version__}')
    print(f'{bot.user.name}#{bot.user.discriminator} ready!')
    print('------------------------------------')


@bot.event
async def on_message(message: str):
    if message.author != bot.user:
        await answer_mention(message, bot)
        await bot.process_commands(message)


async def answer_mention(message: str, bot):
    '''If mentioned, respond and show command prefixes'''
    if BOT_MENTION[:-1:] == message.content:
        # Get the message author's name.
        nickname = message.author.nick
        if nickname is not None:
            name = nickname.split()[0]
        else:
            name = message.author.name.split()[0]
            
        # Get the command prefixes.
        prefixes_str = await get_prefixes_str(bot)
        if len(bot.command_prefix) > 1:
            prefixes_message = 'prefixes are ' + prefixes_str
        elif len(bot.command_prefix) == 1:
            prefixes_message = 'prefix is ' + prefixes_str
        else:
            bot.command_prefix = (BOT_MENTION + ' ')
            prefixes_message = f'prefix is `@Parhelion `'
        
        await message.channel.send(f'Hello {name}! My command {prefixes_message}')


@bot.event
async def on_command(ctx):
    log_message = f'author: {ctx.author.display_name}; guild: {ctx.guild}; command: {ctx.message.content}'
    logger.log(COMMANDS, log_message)

    # Save owner's commands for easy reuse.
    if ctx.author.id == int(os.environ['MY_USER_ID']):
        if ctx.command.name != 'r':
            bot.previous_command_ctxs.append(ctx)
            if len(bot.previous_command_ctxs) > 5:
                bot.previous_command_ctxs = bot.previous_command_ctxs[1:]


@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx.command, 'on_error'):
        return

    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(error)
    elif isinstance(error, commands.UserInputError):
        await ctx.send(error)
    else:
        print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


@bot.event
async def on_guild_join(guild):
    message = f'I\'ve joined a new server called "{guild}"!' \
            f'\nI am now in {len(bot.guilds)} servers.'
    await dev_mail(bot, message, use_embed=False)


keep_alive()
token = os.environ.get('DISCORD_BOT_SECRET_TOKEN')
bot.run(token, bot=True, reconnect=True)
