# external imports
from replit import db
from datetime import datetime, timedelta
from typing import Any

# internal imports
from common import create_task_key
from task import Task, Reminder, Daily_Quote


async def save_task(ctx, task_type: str, target_time: str, duration: str, constructor, *args) -> Any:
    """Saves one task to the database and returns it

    duration is for output only and can be empty or in any format
    without commas.

    *args is the list of the task's constructor arguments that
    are not inherited from Task, and must be in the same order
    as in the task's constructor. (The task constructor must
    take these uninherited arguments before all the inherited
    arguments.)
    """
    start_time = datetime.utcnow()
    author_id = ctx.author.id
    try:
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        is_dm = False
    except AttributeError:
        is_dm = True
        guild_id = 0
        channel_id = 0

    task = constructor(*args, author_id, start_time, target_time, duration, is_dm, guild_id, channel_id)
    task_key = await create_task_key(task_type, author_id, target_time)
    
    db[task_key] = repr(task)
    return task


async def delete_task(**kwargs):
    """Deletes task(s) from the database

    kwargs: task, author_id, task_type, target_time.
    Either use the task kwarg, or the author_id kwarg, or both
    author_id and task_type, or all but the task kwarg.

    Use of the task kwarg will delete only that task.
    Use of author_id will delete all tasks by that user.
    Use of author_id and task_type will delete all tasks of that
    type by that user.
    Use of author_id, task_type, and target_time will delete the
    one task with that key.
    """
    try:
        if 'task' in kwargs.keys():
            task = kwargs['task']
            task_key = await create_task_key(task.task_type, task.author_id, task.target_time)
            del db[task_key]
        else:
            author_id = kwargs['author_id']
            
            if 'task_type' in kwargs.keys():
                task_type = kwargs['task_type']

                if 'target_time' in kwargs.keys():
                    target_time = kwargs['target_time']
                    task_key = await create_task_key(task_type, author_id, target_time)
                    del db[task_key]
                else:
                    prefix = await create_task_key(task_type, author_id)
                    task_keys = db.prefix(prefix)
                    for task_key in task_keys:
                        del db[task_key]
            else:
                task_keys = []
                prefix = await create_task_key()
                for task_key in db.prefix(prefix):
                    if str(author_id) == task_key.split()[1]:
                        task_keys.append(task_key)
                for task_key in task_keys:
                    del db[task_key]
    except KeyError:
        # The task may have been deleted by the user.
        pass


async def eval_task(string: str) -> Any:
    """Turns a task str into an object
    
    The task constructor must take any uninherited arguments
    before all the inherited arguments.
    """
    i = string.find('(')
    constructor_name = string[:i]
    args = string[i+1:-1].split(', ')

    author_id = int(args[-7])
    start_time: str = args[-6][1:-1]
    target_time: str = args[-5][1:-1]
    duration: str = args[-4][1:-1]
    is_dm: bool = args[-3][1:-1] == 'True'
    guild_id = int(args[-2])
    channel_id = int(args[-1])

    if constructor_name == 'Reminder':
        message: str = args[0][1:-1]
        task = Reminder(message, author_id, start_time, target_time, duration, is_dm, guild_id, channel_id)
    elif constructor_name == 'Daily_Quote':
        task = Daily_Quote(author_id, start_time, target_time, duration, is_dm, guild_id, channel_id)
    else:
        print(f'Error: constructor name not found.')
    
    return task


async def target_tomorrow(old_datetime: datetime) -> datetime:
    """Changes the target day to tomorrow without changing the time"""
    tomorrow = datetime.utcnow() + timedelta(days=1)
    return old_datetime.replace(day=tomorrow.day)
