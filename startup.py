# external imports
import discord
from discord.ext import commands
import os
from datetime import datetime
import asyncio
import asyncpg
from typing import Union, Tuple, Dict, List
import json
import logging
from logging.handlers import RotatingFileHandler

# internal imports
from cogs.rand import send_quote, update_quote_day
from cogs.reminders import delete_reminder_from_db


def load_all_custom_prefixes() -> Dict[int, List[str]]:
    """Gets all the custom prefixes for all servers
    
    Returns an empty dict if there are none.
    """
    with open('custom_prefixes.json', 'r') as file:
        try:
            string_key_dict = json.load(file)
            return str_keys_to_ints(string_key_dict)
        except json.decoder.JSONDecodeError:
            return dict()


def str_keys_to_ints(string_key_dict: Dict[str, List[str]]) -> Dict[int, List[str]]:
    """Converts a dict's keys from strings to ints"""
    correct_dict = dict()
    for key, value in string_key_dict.items():
        correct_dict[int(key)] = value

    return correct_dict


async def get_db_connection() -> asyncpg.Pool:
    """Connects to the PostgreSQL database"""
    user = os.environ['PostgreSQL user']
    password = os.environ['PostgreSQL password']
    database = os.environ['PostgreSQL database']
    host = os.environ['PostgreSQL host']

    credentials = {'user': user, 'password': password, 'database': database, 'host': host}

    return await asyncpg.create_pool(**credentials, command_timeout=60)


async def set_up_logger(name: str, level: int) -> logging.Logger:
    """Sets up a logger for this module"""
    # Discord logging guide: https://discordpy.readthedocs.io/en/latest/logging.html#logging-setup
    # Python's intro to logging: https://docs.python.org/3/howto/logging.html#logging-basic-tutorial
    # Documentation for RotatingFileHandler: https://docs.python.org/3/library/logging.handlers.html?#logging.handlers.RotatingFileHandler
    logger = logging.getLogger(name)
    logger.setLevel(level)
    max_bytes = 1024 * 1024  # 1 MiB
    handler = RotatingFileHandler(filename='bot.log', encoding='utf-8', mode='a', maxBytes=max_bytes, backupCount=1)
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


async def continue_tasks(bot) -> None:
    """Runs all saved tasks, one at a time
    
    This function processes only one task at a time,
    which is one of the reasons the tasks must be
    sorted by target time.
    """
    while True:
        table_name, task_record = await get_first_global_task(bot)
        if task_record is None:
            return
        await continue_task(bot, table_name, task_record)


async def get_first_global_task(bot) -> Tuple[str, asyncpg.Record]:
    """Gets the task with the earliest target time
    
    The first value returned is the name of the table the task is from. The second value is the task's record.
    """
    table_names = ['reminders', 'daily_quotes']
    first_record = await get_first_local_task(bot, table_names[0])
    first_table_name = table_names[0]

    for name in table_names[1:]:
        record = await get_first_local_task(bot, name)
        if record is None:
            continue
        if first_record is None \
                or record['target_time'] < first_record['target_time']:
            first_record = record
            first_table_name = name

    return first_table_name, first_record


async def get_first_local_task(bot, table_name: str) -> asyncpg.Record:
    """Gets a table's record with the earliest target time"""
    if table_name == 'reminders':
        return await bot.db.fetchrow('''
            SELECT *
            FROM reminders
            ORDER BY target_time
            LIMIT 1;
            ''')
    elif table_name == 'daily_quotes':
        return await bot.db.fetchrow('''
            SELECT *
            FROM daily_quotes
            ORDER BY target_time
            LIMIT 1;
            ''')
    else:
        raise ValueError('Unhandled table name.')


async def continue_task(bot, table_name: str, task_record: asyncpg.Record) -> None:
    """Continues a task that had been stopped by a server restart"""
    destination: object = await get_destination(bot, task_record)
    now = datetime.utcnow()
    remaining_time = task_record['target_time'] - now
    remaining_seconds = remaining_time.total_seconds()

    if table_name == 'reminders':
        await continue_reminder(bot, task_record, destination, remaining_seconds)
    elif table_name == 'daily_quotes':
        await continue_daily_quote(bot, task_record, destination, remaining_seconds)


async def get_destination(bot, task_record: asyncpg.Record) -> Union[discord.User, discord.TextChannel, None]:
    """Gets the destination of a task"""
    if task_record['is_dm']:
        return bot.get_user(task_record['author_id'])
    server = bot.get_guild(task_record['server_id'])
    return server.get_channel(task_record['channel_id'])


async def continue_daily_quote(bot, task_record: asyncpg.Record, destination: Union[discord.User, discord.TextChannel, commands.Context], remaining_seconds: int) -> None:
    """Continues a daily quote that had been stopped by a server restart"""
    if remaining_seconds > 0:
        await asyncio.sleep(remaining_seconds)

    await send_quote(destination, bot)

    author_id = task_record['author_id']
    target_time = task_record['target_time']
    await update_quote_day(bot, author_id, target_time)


async def continue_reminder(bot, task_record: asyncpg.Record, destination: Union[discord.User, discord.TextChannel, commands.Context], remaining_seconds: int) -> None:
    """Continues a reminder that had been stopped by a server restart"""
    author_id = task_record['author_id']
    message = task_record['message']
    start_time = task_record['start_time']
    target_time = task_record['target_time']

    if remaining_seconds > 0:
        await asyncio.sleep(remaining_seconds)
        await destination.send(f'<@!{author_id}>, here is your reminder: {message}')
        await delete_reminder_from_db(bot, author_id, start_time)
    else:
        await destination.send(f'<@!{author_id}>, an error delayed your reminder: {message}\n' \
        f'The reminder had been set for {target_time} UTC')
        await delete_reminder_from_db(bot, author_id, start_time)
