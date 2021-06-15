from replit import db
from cogs.reminders import continue_reminder
from cogs.rand import continue_daily_quote


async def create_task_key(task_type: str = '', author_id: int = 0, target_time: str = ''):
    '''Create a task key string
    
    If one or more of the last arguments are missing, a key
    prefix will be returned.
    '''
    if not len(target_time):
        if not author_id:
            if not len(task_type):
                return 'task:'
            return f'task:{task_type} '
        return f'task:{task_type} {author_id} '
    return f'task:{task_type} {author_id} {target_time}'


async def sorted_task_keys():
    '''Return all task keys, sorted by target time'''
    prefix = await create_task_key()
    task_keys = db.prefix(prefix)
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
    prefix = await create_task_key('reminder')
    if task_key.startswith(prefix):
        await continue_reminder(bot, task_key)
        return

    prefix = await create_task_key('daily_quote')
    if task_key.startswith(prefix):
        await continue_daily_quote(bot, task_key)


async def delete_task(**kwargs):
    '''Deletes task(s) from the database

    kwargs: task, author_id, task_type, target_time.
    Either use the task kwarg, or the author_id kwarg, or both
    author_id and task_type, or all but the task kwarg.

    Use of the task kwarg will delete only that task.
    Use of author_id will delete all tasks by that user.
    Use of author_id and task_type will delete all tasks of that
    type by that user.
    Use of author_id, task_type, and target_time will delete the
    one task with that key.
    '''
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
        # TODO:
        # log_message = f'could not find task to delete: {self}'
        # logger.log(logging.WARNING, log_message)
