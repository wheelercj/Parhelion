# external imports
from discord.ext import commands
from datetime import datetime, timedelta
import dateparser
from typing import Tuple

# internal imports
from cogs.utils.common import plural


async def get_14_digit_datetime() -> str:
    """Gets a timestamp in the format YYYYMMDDhhmmss"""
    now = str(datetime.utcnow())
    now = now[:19]  # Remove the microseconds.
    now = now.replace('-', '').replace(':', '').replace(' ', '')
    return now


async def format_date(dt: datetime) -> str:
    """Makes an easy-to-read date message"""
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    return f'{dt.day} {months[dt.month-1]} {dt.year}'


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

    output = []
    if days:
        output.append(plural(days, 'day||s'))
    if hours:
        output.append(plural(hours, 'hour||s'))
    if minutes:
        output.append(plural(minutes, 'minute||s'))
    if seconds:
        output.append(plural(seconds, 'second||s'))

    return ', '.join(output)


async def format_relative_time_stamp(dt: datetime) -> str:
    """Creates a relative timestamp string

    E.g., 'a month ago', or 'in two hours'
    """
    return f'<t:{dt.strftime("%s")}:R>'


async def format_long_datetime_stamp(dt: datetime) -> str:
    """Creates a long datetime stamp that shows the correct time in each viewer's timezone

    E.g., 'Tuesday, June 22, 2021 11:14 AM'
    """
    return f'<t:{dt.strftime("%s")}:F>'


async def format_short_datetime_stamp(dt: datetime) -> str:
    """Creates a short datetime stamp that shows the correct time in each viewer's timezone

    E.g., 'June 22, 2021 11:14 AM'
    """
    return f'<t:{dt.strftime("%s")}:f>'


async def parse_time_message(ctx, user_input: str) -> Tuple[datetime, str]:
    """Parses a string containing both a time description and a message

    The time can be a date, duration, etc. written in natural language. The time description must be at the front of the input string.
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
    
    The time can be a date, duration, etc. written in natural language. The time description must be at the front of the input string.
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
