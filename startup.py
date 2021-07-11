# external imports
from datetime import datetime, timedelta
import asyncio
import asyncpg
from typing import Tuple

# internal imports
from common import send_traceback
from cogs.rand import send_quote


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
    print(f'{table_name = }')
    return await bot.db.fetchrow('''
        SELECT *
        FROM $1
        ORDER BY target_time
        LIMIT 1;
        ''', table_name)


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
        return await bot.get_user(task_record['author_id'])
    guild = await bot.get_guild(task_record['guild_id'])
    return await guild.get_member(task_record['author_id'])


async def target_tomorrow(old_datetime: datetime) -> datetime:
    """Changes the target day to tomorrow without changing the time"""
    tomorrow = datetime.utcnow() + timedelta(days=1)
    return old_datetime.replace(day=tomorrow.day)


async def update_daily_quote_target_time(bot, task_record: asyncpg.Record, new_target_time: str) -> None:
    """Updates the database"""
    author_id = task_record['author_id']
    await bot.db.execute('''
        UPDATE daily_quotes
        SET target_time = $1
        WHERE author_id = $2
        ''', new_target_time, author_id)


async def delete_reminder(bot, task_record: asyncpg.Record) -> None:
    """Deletes a reminder from the database"""
    await bot.db.execute('''
        DELETE FROM reminders
        WHERE author_id = $1
            AND start_time = $2
        ''', task_record['author_id'], task_record['start_time'])


async def continue_daily_quote(bot, task_record: asyncpg.Record, destination: object, remaining_seconds: int) -> None:
    """Continues a daily quote that had been stopped by a server restart
    
    destination can be ctx, a channel object, or a user object.
    """
    if remaining_seconds > 0:
        await asyncio.sleep(remaining_seconds)

    await send_quote(destination, bot)
    new_target_time = await target_tomorrow(task_record['target_time'])
    await update_daily_quote_target_time(bot, task_record, new_target_time)


async def continue_reminder(bot, task_record: asyncpg.Record, destination: object, remaining_seconds: int) -> None:
    """Continues a reminder that had been stopped by a server restart
    
    destination can be ctx, a channel object, or a user object.
    """
    try:
        if remaining_seconds > 0:
            await asyncio.sleep(remaining_seconds)
            
            author_id = task_record['author_id']
            message = task_record['message']
            await destination.send(f'<@!{author_id}>, here is your reminder: {message}')
            await delete_reminder(bot, task_record)
        else:
            author_id = task_record['author_id']
            message = task_record['message']
            target_time = task_record['target_time']

            await destination.send(f'<@!{author_id}>, an error delayed your reminder: {message}\n' \
            f'The reminder had been set for {target_time} UTC')
            await delete_reminder(bot, task_record)

    except Exception as e:
        author_id = task_record['author_id']
        await destination.send(f'<@!{author_id}>, your reminder was cancelled because of an error: {e}')
        if await bot.is_owner(author_id):
            await send_traceback(destination, e)
        await delete_reminder(bot, task_record)
        raise e
