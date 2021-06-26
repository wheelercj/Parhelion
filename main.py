# External imports
import os
import discord
from discord.ext import commands
import logging

# Internal imports
from bot import Bot
from common import dev_settings
from keep_alive import keep_alive


def main(bot):
    keep_alive()
    token = os.environ.get('DISCORD_BOT_SECRET_TOKEN')
    bot.run(token, bot=True, reconnect=True)


# Discord logging guide: https://discordpy.readthedocs.io/en/latest/logging.html#logging-setup
# Python's intro to logging: https://docs.python.org/3/howto/logging.html#logging-basic-tutorial
logger = logging.getLogger('discord')
COMMANDS = 25  # Logs each command use (as well as warnings, errors, and criticals).
logger.setLevel(COMMANDS)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


def get_command_prefixes(bot, message):
    prefixes = dev_settings.bot_prefixes
    # TODO: after changing hosts and setting up a new database,
    # allow server-side prefix customization here.
    return commands.when_mentioned_or(*prefixes)(bot, message)


# Create the bot.
intents = discord.Intents.default()
intents.members = True
bot = Bot(
    command_prefix=get_command_prefixes,
    intents=intents
)


# Set a global cooldown across all commands.
global_cooldown = commands.CooldownMapping.from_cooldown(1, 2, commands.BucketType.user)


@bot.check
async def check_cooldown(ctx):
    # The help command must not have the global cooldown
    # because it puts all the other commands on cooldown
    # which hides all of them.
    if ctx.command == bot.help_command:
        return True

    # This check is called once for each of the bot's
    # commands when the help command is used, so
    # prevent the cooldown for those too.
    if ctx.command.name not in ctx.message.content:
        return True

    bucket = global_cooldown.get_bucket(ctx.message)
    retry_after = bucket.update_rate_limit()
    if retry_after:
        raise commands.CommandOnCooldown(bucket, retry_after)

    return True


if __name__ == '__main__':
    main(bot)
