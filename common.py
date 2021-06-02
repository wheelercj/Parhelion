import os
import traceback
import discord


BOT_ID = '836071320328077332'
BOT_MENTION = f'<@!{BOT_ID}> '


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


async def get_prefixes_str(bot) -> str:
    raw_prefixes = list(bot.command_prefix)
    for i, prefix in enumerate(raw_prefixes):
        if prefix == BOT_MENTION:
            raw_prefixes[i] = '`@Parhelion `'
    prefixes = [f'`{x}`' for x in raw_prefixes]
    
    return ', '.join(prefixes)
