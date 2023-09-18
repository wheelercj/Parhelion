from datetime import datetime
from datetime import timedelta

import asyncpg  # https://pypi.org/project/asyncpg/
import dateparser  # https://pypi.org/project/dateparser/
from discord.ext import commands  # https://pypi.org/project/discord.py/

from cogs.utils.common import plural


async def create_relative_timestamp(dt: datetime) -> str:
    """Creates a relative timestamp string

    E.g., 'a month ago', or 'in two hours'
    """
    unix_time = int(dt.timestamp())
    return f"<t:{unix_time}:R>"


async def create_long_datetime_stamp(dt: datetime) -> str:
    """Creates a long datetime stamp showing the correct time in each viewer's timezone

    E.g., 'Tuesday, June 22, 2021 11:14 AM'
    """
    unix_time = int(dt.timestamp())
    return f"<t:{unix_time}:F>"


async def create_short_datetime_stamp(dt: datetime) -> str:
    """Creates a short datetime stamp showing the correct time in each viewer's timezone

    E.g., 'June 22, 2021 11:14 AM'
    """
    unix_time = int(dt.timestamp())
    return f"<t:{unix_time}:f>"


async def create_short_timestamp(dt: datetime) -> str:
    """Creates a short timestamp that shows the correct time in each viewer's timezone

    E.g., '11:14 AM'
    """
    unix_time = int(dt.timestamp())
    return f"<t:{unix_time}:t>"


async def get_14_digit_datetime() -> str:
    """Gets a timestamp in the format YYYYMMDDhhmmss"""
    now = str(datetime.utcnow())
    now = now[:19]  # Remove the microseconds.
    now = now.replace("-", "").replace(":", "").replace(" ", "")
    return now


async def format_datetime(dt: datetime) -> str:
    """Makes an easy-to-read date and time message"""
    months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    minute = str(dt.minute).zfill(2)
    return f"{dt.hour}:{minute} on {dt.day} {months[dt.month-1]} {dt.year}"


async def format_timedelta(td: timedelta) -> str:
    """Makes an easy-to-read time duration message"""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    output = []
    if days:
        output.append(plural(days, "day||s"))
    if hours:
        output.append(plural(hours, "hour||s"))
    if minutes:
        output.append(plural(minutes, "minute||s"))
    if seconds:
        output.append(plural(seconds, "second||s"))
    return ", ".join(output)


async def parse_time_message(
    ctx, user_input: str, to_timezone: str = "UTC"
) -> tuple[datetime, str]:
    """Parses a string containing a time description & optionally a message

    The user's input can have a date, duration, etc. written in natural language, and
    that time description must be at the front of the user's input. The entered time
    will be assumed to be in UTC unless the user set a timezone for the bot. The
    timezone-aware result will be in UTC unless the optional to_timezone argument is
    used. If the entire user_input is converted to a datetime, the second returned
    value will be an empty string. If a valid time description cannot be found,
    commands.BadArgument will be raised.
    """
    tz = await get_timezone(ctx.bot.db, ctx.author.id)
    if tz is None:
        tz = "UTC"
    # https://dateparser.readthedocs.io/en/latest/
    dateparser_settings = {
        "TIMEZONE": str(tz),
        "TO_TIMEZONE": str(to_timezone),
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
    }
    split_input = user_input.split(" ")
    max_length = len(
        split_input[:7]
    )  # The longest possible time description accepted is 7 words long.
    # Gradually try parsing fewer words until a valid time description is found.
    message = ""
    for i in range(max_length, 0, -1):
        time_description = " ".join(split_input[:i])
        date_time = dateparser.parse(time_description, settings=dateparser_settings)
        if date_time is not None:
            message = user_input.replace(time_description, "")[1:]
            break
    if date_time is None:
        raise commands.BadArgument("Invalid time description")
    return date_time, message


async def get_timezone(db: asyncpg.Pool, user_id: int) -> str | None:
    """Gets a user's chosen timezone from the database"""
    return await db.fetchval(
        """
        SELECT timezone
        FROM timezones
        WHERE user_id = $1;
        """,
        user_id,
    )
