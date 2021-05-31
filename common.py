import os
import traceback
import discord


async def send_traceback(ctx, e):
    etype = type(e)
    trace = e.__traceback__
    lines = traceback.format_exception(etype, e, trace)
    traceback_text = ''.join(lines)
    await ctx.send(f'```\n{traceback_text}\n```')


def remove_backticks(statement: str, languages=['py', 'python']) -> str:
    '''Removes backticks around a code block, if they are there'''
    if statement.startswith('```'):
        statement = statement[3:]
        for language in languages:
            if statement.startswith(f'{language}\n'):
                size = len(language) + 1
                statement = statement[size:]
                break
        if statement.startswith('\n'):
            statement = statement[1:]

        if statement.endswith('\n```'):
            statement = statement[:-4]
        if statement.endswith('\n'):
            statement = statement[:-1]

    return statement


async def dev_mail(bot, message: str, use_embed: bool = True, embed_title: str = 'dev mail'):
    user = await bot.fetch_user(int(os.environ['MY_USER_ID']))
    if use_embed:
        embed = discord.Embed(title=embed_title, description=message)
        await user.send(embed=embed)
    else:
        await user.send(message)
