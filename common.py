import re
import traceback
import discord
from discord.ext import commands
from typing import List, Tuple
from datetime import datetime, timedelta
import dateparser


class Dev_Settings:
    def __init__(self):
        self.default_bot_prefixes = [';', 'par ', 'Par ']
        self.bot_invite_link = 'https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3402816'
        self.support_server_link = 'https://discord.gg/mCqGhPJVcN'
        self.privacy_policy_link = 'https://gist.github.com/wheelercj/033bbaf78b08ff0335943d5119347853'

dev_settings = Dev_Settings()


async def escape_json(text: str) -> str:
    """Escapes slashes, backslashes, double quotes, and all JSON escape sequences"""
    text = text.replace('\\', '\\\\').replace('"', r'\"').replace('\n', r'\n').replace('\t', r'\t').replace('\r', r'\r').replace('\b', r'\b').replace('\f', r'\f').replace(r'\u', r'\\u').replace('/', '\/')
    return text

    
async def get_14_digit_timestamp() -> str:
    """Gets a timestamp in the format YYYYMMDDhhmmss"""
    now = str(datetime.utcnow())
    now = now[:19]  # Remove the microseconds.
    now = now.replace('-', '').replace(':', '').replace(' ', '')
    return now


async def format_date(dt: datetime) -> str:
    """Makes an easy-to-read date message"""
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    return f'{dt.day} {months[dt.month+1]} {dt.year}'


async def format_time(dt: datetime) -> str:
    """Makes an easy-to-read time message"""
    minute = str(dt.minute).zfill(2)
    return f'{dt.hour}:{minute}'


async def format_datetime(dt: datetime) -> str:
    """Makes an easy-to-read date and time message"""
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    minute = str(dt.minute).zfill(2)
    return f'{dt.hour}:{minute} on {dt.day} {months[dt.month-1]} {dt.year}'


async def format_timedelta(td: timedelta) -> str:
    """Makes an easy-to-read time duration message"""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    async def plural(n: int, msg: str) -> str:
        if n > 1:
            return f'{n} {msg}s'
        return f'{n} {msg}'

    output = []
    if days:
        output.append(await plural(days, 'day'))
    if hours:
        output.append(await plural(hours, 'hour'))
    if minutes:
        output.append(await plural(minutes, 'minute'))
    if seconds:
        output.append(await plural(seconds, 'second'))

    return ', '.join(output)


async def send_traceback(ctx, error: BaseException) -> None:
    """Sends the traceback of an exception to ctx"""
    etype = type(error)
    trace = error.__traceback__
    lines = traceback.format_exception(etype, error, trace)
    traceback_text = ''.join(lines)
    await ctx.send(f'```\n{traceback_text}\n```')


async def dev_mail(bot, message: str, use_embed: bool = True, embed_title: str = 'dev mail') -> None:
    """Sends a private message to the bot owner"""
    user = await bot.fetch_user(bot.owner_id)
    if use_embed:
        embed = discord.Embed(title=embed_title, description=message)
        await user.send(embed=embed)
    else:
        await user.send(message)


async def target_tomorrow(old_datetime: datetime) -> datetime:
    """Changes a datetime to tomorrow without changing anything else"""
    tomorrow = datetime.utcnow() + timedelta(days=1)
    return old_datetime.replace(day=tomorrow.day)


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


async def parse_time_message(ctx, user_input: str) -> Tuple[datetime, str]:
    """Parses a string containing both a time description and a message

    The time can be a date, duration, etc. written in natural language.
    """
    if not user_input.strip().startswith('in '):
        user_input = f'in {user_input}'
    date_time, time_description = await split_time_message(user_input)

    if date_time is None:
        raise commands.BadArgument('Invalid time description')

    now = ctx.message.created_at
    date_time = date_time.replace(tzinfo=now.tzinfo)
    message = user_input.replace(time_description, '')[1:]

    return date_time, message


async def split_time_message(user_input: str) -> Tuple[datetime, str]:
    """Splits a string of a time description and a message
    
    The time can be a date, duration, etc. written in natural language.
    """
    split_input = user_input.split(' ')
    dateparser_settings = {
        'TIMEZONE': 'UTC',
        'TO_TIMEZONE': 'UTC',
        'RETURN_AS_TIMEZONE_AWARE': True,
        'PREFER_DATES_FROM': 'future'
    }

    # The longest possible time description accepted is 7 words long.
    max_length = len(split_input[:7])
    date_time = None
    time_description = ''
    
    # Gradually try parsing fewer words as a time description until a valid one is found.
    for i in range(max_length, 0, -1):
        time_description = ' '.join(split_input[:i])
        date_time = dateparser.parse(time_description, settings=dateparser_settings)
        if date_time is not None:
            break

    return date_time, time_description


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
