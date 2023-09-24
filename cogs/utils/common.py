import re
from typing import Awaitable

import discord  # https://pypi.org/project/discord.py/
from discord import PartialMessageable  # https://pypi.org/project/discord.py/
from discord.abc import Messageable  # https://pypi.org/project/discord.py/
from discord.ext import commands  # https://pypi.org/project/discord.py/


async def get_bot_invite_link(bot) -> str:
    """Creates a link for inviting this bot to a server

    The link will request some basic permissions.
    """
    # Permissions docs:
    # https://discordpy.readthedocs.io/en/latest/api.html?#discord.Permissions
    perms = discord.Permissions.none()
    perms.add_reactions = True
    perms.attach_files = True
    perms.embed_links = True
    perms.manage_messages = True
    perms.mention_everyone = True
    perms.read_message_history = True
    perms.read_messages = True
    perms.send_messages = True
    perms.use_application_commands = True
    bot_invite_link = discord.utils.oauth_url(bot.user.id, permissions=perms)
    return bot_invite_link


def plural(number: int | float, root_and_suffixes: str) -> str:
    """Returns the number and either a singular or plural word

    Separate the root and each suffix with | (pipe symbols).
    Put the singular suffix before the plural one.
    If there is no singular suffix, separate the root and plural suffix with || (two
    pipe symbols).
    Example uses:
        plural(25, 'pe|rson|ople') → '25 people'
        plural(1, 'pe|rson|ople') → '1 person'
        plural(0, 'societ|y|ies') → '0 societies'
        plural(1, 'child||ren') → '1 child'
        plural(-4.5, '|is|are') → '-4.5 are'
    """
    if not isinstance(number, (int, float)):
        number = float(number)
    if root_and_suffixes.count("|") != 2:
        raise ValueError("Two pipe symbols required in root_and_suffixes.")
    root, singular, plural = root_and_suffixes.split("|")
    if number == 1:
        return f"{number} {root}{singular}"
    return f"{number} {root}{plural}"


async def escape_json(text: str) -> str:
    """Escapes slashes, backslashes, double quotes, and all JSON escape sequences"""
    text = (
        text.replace("\\", "\\\\")
        .replace('"', r"\"")
        .replace("\n", r"\n")
        .replace("\t", r"\t")
        .replace("\r", r"\r")
        .replace("\b", r"\b")
        .replace("\f", r"\f")
        .replace(r"\u", r"\\u")
        .replace("/", r"\/")
    )
    return text


async def block_nsfw_channels(channel: Messageable | PartialMessageable) -> None:
    """Raises commands.UserInputError if channel is a nsfw channel"""
    if channel.guild is None:
        return  # DM channels don't have an is_nsfw method.
    if channel.is_nsfw():
        raise commands.UserInputError("This command cannot be used in NSFW channels")


async def check_ownership_permission(
    bot,
    author: discord.User | discord.Member,
    category: str,
    membership_removes_limit: bool,
    ownership_limit: int,
    ownership_counter: Awaitable[int],
) -> None:
    """Raises commands.UserInputError if author has reached the ownership limit

    Parameters
    ----------
    bot
        The bot.
    author : discord.User | discord.Member
        The person requesting to create something.
    category : str
        The plural name of what is being requested.
    membership_removes_limit : bool
        Whether membership should remove the ownership limit.
    ownership_limit : int
        How many of the requested thing a person can have.
    ownership_counter : Awaitable[int]
        A coroutine that takes a Discord user ID and returns the number of a thing that
        user currently owns.
    """
    if author.id == bot.owner_id:
        return
    if bot.dev_settings.support_server_id and membership_removes_limit:
        support_server = bot.get_guild(bot.dev_settings.support_server_id)
        member = support_server.get_member(author.id)
        if member:
            for role in member.roles:
                if role.id in bot.dev_settings.membership_role_ids:
                    return
    c = await ownership_counter(author.id)
    if c < ownership_limit:
        return
    message = f"The current free {category} limit is {ownership_limit}."
    if bot.dev_settings.membership_link and membership_removes_limit:
        message += (
            f" Support development and unlock unlimited {category} here:"
            f" <{bot.dev_settings.membership_link}>"
        )
    raise commands.UserInputError(message)


#####################
# prefixes commands #
#####################


async def get_prefixes_list(bot, message: discord.Message) -> list[str]:
    """Returns a list of the bot's rendered server-aware command prefixes

    The prefixes are sorted from shortest to longest. Use `bot.command_prefix(bot,
    message)` if you want the unrendered prefixes.
    """
    raw_prefixes: list[str] = bot.command_prefix(bot, message)
    if "" in raw_prefixes:
        raw_prefixes.remove("")
    # The unrendered mention pattern looks different in code
    # than when a user types it in Discord, so remove both
    # unrendered mention prefixes, and add one with the
    # "correct" appearance.
    display_prefixes = ["/", f"@{bot.user.name} "]
    mention_regex = re.compile(rf"<@!?{bot.user.id}>")
    for prefix in raw_prefixes:
        if mention_regex.match(prefix) is None:
            display_prefixes.append(prefix)
    display_prefixes = sorted(display_prefixes, key=len)
    return display_prefixes


async def get_prefixes_str(
    bot, message: discord.Message, display_prefixes: list[str] = None
) -> str:
    """Returns a string of the rendered server-aware command prefixes, comma separated

    The prefixes should be sorted from shortest to longest. If display_prefixes is not
    provided, it will be retrieved.
    """
    if display_prefixes is None:
        display_prefixes = await get_prefixes_list(bot, message)
    prefixes = [f"`{x}`" for x in display_prefixes]
    return ", ".join(prefixes)


async def get_prefixes_message(
    bot, message: discord.Message, display_prefixes: list[str] = None
) -> str:
    """Returns a message of the bot's rendered server-aware command prefixes

    The message starts with `prefixes are` or `prefix is`, depending on how many there
    are. The prefixes should be sorted from shortest to longest. If display_prefixes is
    not provided, it will be retrieved.
    """
    if display_prefixes is None:
        display_prefixes = await get_prefixes_list(bot, message)
    prefixes_str = await get_prefixes_str(bot, message, display_prefixes)
    if len(display_prefixes) > 1:
        return "prefixes are " + prefixes_str
    elif len(display_prefixes) == 1:
        return "prefix is " + prefixes_str
    else:
        raise ValueError
