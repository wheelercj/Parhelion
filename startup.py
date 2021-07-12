# external imports
from datetime import datetime
import asyncio
import asyncpg
from typing import Tuple

# internal imports
from cogs.rand import send_quote, update_quote_day
from cogs.reminders import delete_reminder_from_db


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


async def get_destination(bot, task_record: asyncpg.Record) -> object:
    """Gets the destination of a task
    
    The destination can be a channel object or a user object.
    """
    if task_record['is_dm']:
        return bot.get_user(task_record['author_id'])
    guild = bot.get_guild(task_record['guild_id'])
    return guild.get_channel(task_record['channel_id'])


async def continue_daily_quote(bot, task_record: asyncpg.Record, destination: object, remaining_seconds: int) -> None:
    """Continues a daily quote that had been stopped by a server restart
    
    destination can be ctx, a channel object, or a user object.
    """
    if remaining_seconds > 0:
        await asyncio.sleep(remaining_seconds)

    await send_quote(destination, bot)

    author_id = task_record['author_id']
    target_time = task_record['target_time']
    await update_quote_day(bot, author_id, target_time)


async def continue_reminder(bot, task_record: asyncpg.Record, destination: object, remaining_seconds: int) -> None:
    """Continues a reminder that had been stopped by a server restart
    
    destination can be ctx, a channel object, or a user object.
    """
    author_id = task_record['author_id']
    message = task_record['message']
    start_time = task_record['start_time']
    target_time = task_record['target_time']

    try:
        if remaining_seconds > 0:
            await asyncio.sleep(remaining_seconds)
            await destination.send(f'<@!{author_id}>, here is your reminder: {message}')
            await delete_reminder_from_db(bot, author_id, start_time)
        else:
            await destination.send(f'<@!{author_id}>, an error delayed your reminder: {message}\n' \
            f'The reminder had been set for {target_time} UTC')
            await delete_reminder_from_db(bot, author_id, start_time)

    except Exception as e:
        await destination.send(f'<@!{author_id}>, your reminder was cancelled because of an error: {e}')
        await delete_reminder_from_db(bot, author_id, start_time)
        raise e
