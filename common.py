import os
import re
import traceback
import discord
from discord.ext import commands
from typing import List, Tuple, Optional, Union


class Dev_Settings:
    def __init__(self):
        self.default_bot_prefixes = [';', 'par ', 'Par ']
        self.support_server_link = 'https://discord.gg/mCqGhPJVcN'
        self.privacy_policy_link = 'https://gist.github.com/wheelercj/033bbaf78b08ff0335943d5119347853'

dev_settings = Dev_Settings()


async def get_bot_invite_link(bot) -> str:
    """Creates a link to invite a bot to a server

    The link will request some basic permissions.
    """
    # Permissions docs: https://discordpy.readthedocs.io/en/latest/api.html?#discord.Permissions
    perms = discord.Permissions.none()
    
    # Text channel permissions.
    perms.read_messages = True
    perms.send_messages = True
    perms.embed_links = True
    perms.attach_files = True
    perms.add_reactions = True
    perms.mention_everyone = True
    perms.manage_messages = True
    perms.read_message_history = True

    # Voice channel permissions.
    perms.view_channel = True
    perms.connect = True
    perms.speak = True
    
    bot_invite_link = discord.utils.oauth_url(bot.user.id, perms)
    return bot_invite_link


def plural(number: Union[int, float], root_and_suffixes: str) -> str:
    """Returns the number and either a singular or plural word

    Separate the root and each suffix with | (pipe symbols).
    Put the singular suffix before the plural one.
    If there is no singular suffix, separate the root and plural suffix with || (two pipe symbols).
    Example uses:
        plural(1, 'societ|y|ies') -> '1 society'
        plural(2, 'societ|y|ies') -> '2 societies'
        plural(0, 'p|erson|eople') -> '0 people'
        plural(1, 'child||ren') -> '1 child'
        plural(2, '|cow|kine') -> '2 kine'
    """
    if not isinstance(number, (int, float)):
        number = float(number)
    if root_and_suffixes.count('|') != 2:
        raise ValueError('Two pipe symbols required in root_and_suffixes.')

    root, singular, plural = root_and_suffixes.split('|')

    if number == 1:
        return f'{number} {root}{singular}'
    return f'{number} {root}{plural}'


async def escape_json(text: str) -> str:
    """Escapes slashes, backslashes, double quotes, and all JSON escape sequences"""
    text = text.replace('\\', '\\\\').replace('"', r'\"').replace('\n', r'\n').replace('\t', r'\t').replace('\r', r'\r').replace('\b', r'\b').replace('\f', r'\f').replace(r'\u', r'\\u').replace('/', '\/')
    return text


async def get_attachment_url(ctx) -> Optional[str]:
    """Gets the proxy URL of an attachment if there is one

    Attempts to filter out invalid URLs.
    """
    if ctx.message.attachments:
        file_url = ctx.message.attachments[0].proxy_url
        file_type = file_url.split('.')[-1]

        if not await is_supported_type(file_type):
            raise ValueError(f'Attachment links do not work for files of type {file_type}')

        return file_url


async def is_supported_type(file_type: str) -> bool:
    """Says whether the file type is supported by Discord's CDN
    
    This function is incomplete; more file types need to be tested.
    """
    unsupported_types = ['md', 'pdf']
    # TODO: find a complete list of supported file types and use that instead.
    if file_type in unsupported_types:
        return False
    return True


async def send_traceback(ctx, error: BaseException) -> None:
    """Sends the traceback of an exception to ctx"""
    etype = type(error)
    trace = error.__traceback__
    lines = traceback.format_exception(etype, error, trace)
    traceback_text = ''.join(lines)
    await ctx.send(f'```\n{traceback_text}\n```')


async def safe_send(ctx, message: str, protect_postgres_host: bool = False) -> None:
    """Same as ctx.send but with extra security options"""
    if protect_postgres_host:
        postgres_host = os.environ['PostgreSQL host']
        if postgres_host in message:
            message = message.replace(postgres_host, '(PostgreSQL host)')
            await ctx.send(message)
            return
    
    await ctx.send(message)


async def dev_mail(bot, message: str, use_embed: bool = True, embed_title: str = 'dev mail') -> None:
    """Sends a private message to the bot owner"""
    user = await bot.fetch_user(bot.owner_id)
    if use_embed:
        embed = discord.Embed(title=embed_title, description=message)
        await user.send(embed=embed)
    else:
        await user.send(message)


async def unwrap_code_block(statement: str) -> Tuple[str, str]:
    """Removes triple backticks and a syntax name around a code block
    
    Returns any syntax name found and the unwrapped code. Any syntax name must be on the same line as the leading triple backticks, and code must be on the next line(s). If there are not triple backticks, the returns are 'txt' and the unchanged input. If there are triple backticks and no syntax is specified, the returns will be 'txt' and the unwrapped code block. The result is not dedented. Closing triple backticks are optional.
    """
    if not statement.startswith('```'):
        return 'txt', statement

    statement = statement[3:]

    # Find the syntax name if one is given.
    syntax = 'txt'
    i = statement.find('\n')
    if i != -1:
        first_line = statement[:i].strip()
        if len(first_line):
            syntax = first_line
            statement = statement[i:]

    if statement.startswith('\n'):
        statement = statement[1:]

    if statement.endswith('\n```'):
        statement = statement[:-4]
    if statement.endswith('\n'):
        statement = statement[:-1]

    return syntax, statement


async def split_input(message: str) -> Tuple[str,str]:
        """Splits a string into two strings
        
        If the input string begins with double quotes and has another double quotes later, the contents of those double quotes will be the first string returned. Otherwise, the first string returned will be the first word of the input string. The second string returned will be what remains of the input string.
        """
        name = None
        if message.startswith('"'):
            i = message.find('"', 2)
            if i != -1:
                name = message[1:i]
                content = message[i+1:].strip()

        if name is None:
            name = message.split()[0]
            content = ' '.join(message.split()[1:])

        return name, content


async def get_prefixes_list(bot, message: discord.Message) -> List[str]:
    """Returns a list of the bot's rendered server-aware command prefixes
    
    The prefixes are sorted from shortest to longest. Use `bot.command_prefix(bot, message)` if you want the unrendered prefixes.
    """
    raw_prefixes: List[str] = bot.command_prefix(bot, message)
    if '' in raw_prefixes:
        raw_prefixes.remove('')

    # The unrendered mention pattern looks different in code
    # than when a user types it in Discord, so remove both
    # unrendered mention prefixes, and add one with the
    # "correct" appearance.
    display_prefixes = [f'@{bot.user.name} ']
    mention_regex = re.compile(rf'<@!?{bot.user.id}>')
    for prefix in raw_prefixes:
        if mention_regex.match(prefix) is None:
            display_prefixes.append(prefix)

    display_prefixes = sorted(display_prefixes, key=len)

    return display_prefixes


async def get_prefixes_str(bot, message: discord.Message, display_prefixes: List[str] = None) -> str:
    """Returns a string of the bot's rendered server-aware command prefixes, comma separated
    
    The prefixes should be sorted from shortest to longest. If display_prefixes is not provided, it will be retrieved.
    """
    if display_prefixes is None:
        display_prefixes = await get_prefixes_list(bot, message)
    prefixes = [f'`{x}`' for x in display_prefixes]
    return ', '.join(prefixes)


async def get_prefixes_message(bot, message: discord.Message, display_prefixes: List[str] = None) -> str:
    """Returns a message of the bot's rendered server-aware command prefixes
    
    The message starts with `prefixes are` or `prefix is`, depending on how many there are. The prefixes should be sorted from shortest to longest. If display_prefixes is not provided, it will be retrieved.
    """
    if display_prefixes is None:
        display_prefixes = await get_prefixes_list(bot, message)
    prefixes_str = await get_prefixes_str(bot, message, display_prefixes)
    if len(display_prefixes) > 1:
        return 'prefixes are ' + prefixes_str
    elif len(display_prefixes) == 1:
        return 'prefix is ' + prefixes_str
    else:
        raise ValueError


class Channel(commands.Converter):
    """Converter for all types of Discord channels

    Precedence:
        TextChannelConverter
        VoiceChannelConverter
        StageChannelConverter
        StoreChannelConverter
        CategoryChannelConverter
    """
    async def convert(self, ctx, argument):
        converters = [
            commands.TextChannelConverter,
            commands.VoiceChannelConverter,
            commands.StageChannelConverter,
            commands.StoreChannelConverter,
            commands.CategoryChannelConverter,
        ]

        for converter in converters:
            try:
                channel = await converter().convert(ctx, argument)
                return channel
            except commands.ChannelNotFound:
                pass
        
        raise commands.BadArgument(f'Channel "{argument}" not found.')
