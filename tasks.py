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


async def delete_task(**kwargs):
    '''Deletes task(s) from the database

    kwargs:
        task: for deleting one task
        author_id: for deleting all of a specific user's tasks
        task_type: for deleting all of a specific user's tasks of a certain type

    Either use the task kwarg, or the author_id kwarg, or both author_id and task_type.
    '''
    try:
        if 'task' in kwargs.keys():
            task = kwargs['task']
            del db[f'task:{task.task_type} {task.author_id} {task.target_time}']
        else:
            author_id = kwargs['author_id']
            
            if 'task_type' in kwargs.keys():
                task_type = kwargs['task_type']
                task_keys = db.prefix(f'task:{task_type} {author_id}')
                for task_key in task_keys:
                    del db[task_key]
            else:
                task_keys = []
                for task_key in db.prefix('task:'):
                    if str(author_id) == task_key.split()[1]:
                        task_keys.append(task_key)
                for task_key in task_keys:
                    del db[task_key]
    except KeyError:
        # The task may have been deleted by the user.
        pass
        # TODO:
        # log_message = f'could not find task to delete: {self}'
        # logger.log(logging.WARNING, log_message)
