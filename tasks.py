from replit import db
from cogs.reminders import continue_reminder
from cogs.rand import continue_daily_quote


# Task key format: f'task:{task_type} {author_id} {target_time}'
# where target_time is in Python's default ISO format (with no spaces).


async def sorted_task_keys():
    '''Return all task keys, sorted by target time'''
    task_keys = db.prefix('task:')
    return sorted(task_keys, key=lambda x: x.split()[2])


async def continue_tasks(bot):
    '''Restarts all saved tasks, one at a time
    
    This function processes only one task at a time,
    which is one of the reasons the keys should be
    sorted by target time.
    '''
    task_keys = await sorted_task_keys()
    for key in task_keys:
        await continue_task(bot, db[key])


async def continue_task(bot, task_key: str):
    if task_key.startswith('task:reminder'):
        await continue_reminder(bot, task_key)
    elif task_key.startswith('task:daily_quote'):
        await continue_daily_quote(bot, task_key)
