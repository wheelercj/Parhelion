# External imports
from replit import db
from datetime import datetime, timezone, timedelta
import asyncio

# Internal imports
from common import send_traceback, create_task_key
from tasks import delete_task, eval_task
from task import Daily_Quote
from cogs.rand import send_quote


async def continue_tasks(bot):
    '''Runs all saved tasks, one at a time
    
    This function processes only one task at a time,
    which is one of the reasons the keys should be
    sorted by target time.
    '''
    task_keys = await sorted_task_keys()
    while len(task_keys):
        await continue_task(bot, task_keys[0])
        task_keys = await sorted_task_keys()


async def continue_task(bot, task_key: str):
    task = await eval_task(db[task_key])
    destination = await task.get_destination(bot)

    current_time = datetime.now(timezone.utc)
    target_time = datetime.fromisoformat(task.target_time)
    remaining_time = target_time - current_time
    remaining_seconds = remaining_time.total_seconds()

    if task.task_type == 'reminder':
        await continue_reminder(bot, task, destination, remaining_seconds)
    elif task.task_type == 'daily_quote':
        await continue_daily_quote(bot, task, destination, remaining_seconds)


async def sorted_task_keys():
    '''Return all task keys, sorted by target time'''
    prefix = await create_task_key()
    task_keys = db.prefix(prefix)
    return sorted(task_keys, key=lambda x: x.split()[2])


async def update_task_target_time(task, constructor, new_target_time: str):
    '''Update the database'''
    new_task_key = await create_task_key(task.task_type, task.author_id, new_target_time)
    new_task = task
    new_task.target_time = new_target_time
    
    db[new_task_key] = new_task
    await delete_task(task=task)


async def get_new_target_day(task) -> str:
    '''Keep the same target time, but change the target day to tomorrow'''
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    old_target_time = datetime.fromisoformat(task.target_time)
    hour = old_target_time.hour
    minute = old_target_time.minute
    new_target_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day, int(hour), int(minute), tzinfo=timezone.utc)

    return new_target_time.isoformat()


async def continue_daily_quote(bot, daily_quote, destination, remaining_seconds: int):
    '''destination can be ctx, a channel object, or a user object.'''
    if remaining_seconds > 0:
        await asyncio.sleep(remaining_seconds)
        await send_quote(destination, bot)
    else:
        new_target_time = await get_new_target_day(daily_quote)
        await update_task_target_time(daily_quote, Daily_Quote, new_target_time)
    

async def continue_reminder(bot, reminder, destination, remaining_seconds: int):
    '''Continues a reminder that had been stopped by a server restart
    
    destination can be ctx, a channel object, or a user object.
    '''
    try:
        if remaining_seconds > 0:
            await asyncio.sleep(remaining_seconds)
            await destination.send(f'<@!{reminder.author_id}>, here is your {reminder.duration} reminder: {reminder.message}')
            await delete_task(task=reminder)
            # reminders_logger.log(logging.INFO, f'deleting {reminder}')  # TODO
        else:
            await destination.send(f'<@!{reminder.author_id}>, an error delayed your reminder: {reminder.message}')
            target_time = datetime.fromisoformat(reminder.target_time)
            await destination.send(f'The reminder had been set for {target_time.year}-{target_time.month}-{target_time.day} at {target_time.hour}:{target_time.minute} UTC')
            await delete_task(task=reminder)
            # reminders_logger.log(logging.ERROR, f'Delayed delivery. Deleting {reminder}')  # TODO

    except Exception as e:
        await destination.send(f'<@!{reminder.author_id}>, your reminder was cancelled because of an error: {e}')
        if await bot.is_owner(reminder.author_id):
            await send_traceback(destination, e)
        await delete_task(task=reminder)
        # reminders_logger.log(logging.ERROR, f'deleting {reminder} because {e}')  # TODO
        raise e
