# External imports
from replit import db
from datetime import datetime, timezone
import asyncio

# Internal imports
from common import send_traceback, create_task_key
from tasks import delete_task, eval_task
from cogs.rand import send_quote


async def continue_tasks(bot):
    '''Restarts all saved tasks, one at a time
    
    This function processes only one task at a time,
    which is one of the reasons the keys should be
    sorted by target time.
    '''
    task_keys = await sorted_task_keys()
    for task_key in task_keys:
        await continue_task(bot, task_key)


async def continue_task(bot, task_key: str):
    task = await eval_task(db[task_key])
    if task.task_type == 'reminder':
        await continue_reminder(bot, task)
    elif task.task_type == 'daily_quote':
        await continue_daily_quote(bot, task)


async def sorted_task_keys():
    '''Return all task keys, sorted by target time'''
    prefix = await create_task_key()
    task_keys = db.prefix(prefix)
    return sorted(task_keys, key=lambda x: x.split()[2])


async def continue_daily_quote(bot, daily_quote):
    destination = await daily_quote.get_destination(bot)
    await send_quote(destination, bot)


async def continue_reminder(bot, reminder):
    '''Continues a reminder that had been stopped by a server restart'''
    try:
        destination = await reminder.get_destination(bot)

        current_time = datetime.now(timezone.utc)
        target_time = datetime.fromisoformat(reminder.target_time)
        remaining_time = target_time - current_time
        remaining_seconds = remaining_time.total_seconds()

        if remaining_seconds > 0:
            await asyncio.sleep(remaining_seconds)
            await destination.send(f'<@!{reminder.author_id}>, here is your {reminder.duration} reminder: {reminder.message}')
            await delete_task(task=reminder)
            # reminders_logger.log(logging.INFO, f'deleting {reminder}')  # TODO
        else:
            await destination.send(f'<@!{reminder.author_id}>, an error delayed your reminder: {reminder.message}')
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
