import traceback

async def send_traceback(ctx, e):
    etype = type(e)
    trace = e.__traceback__
    lines = traceback.format_exception(etype, e, trace)
    traceback_text = ''.join(lines)
    await ctx.send(f'```\n{traceback_text}\n```')


def remove_backticks(statement: str):
    '''Removes backticks around a code block, if they are there'''
    if statement.startswith('```'):
        statement = statement[3:]
        if statement.startswith('py\n'):
            statement = statement[3:]
        elif statement.startswith('\n'):
            statement = statement[1:]
        if statement.endswith('\n```'):
            statement = statement[:-3]
        if statement.endswith('\n'):
            statement = statement[:-1]

    return statement
