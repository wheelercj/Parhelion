import re
import traceback
import discord
from typing import List


class Dev_Settings:
    def __init__(self):
        self.dev_name = '(chris)#3047'
        self.bot_prefixes = [';', 'par ', 'Par ']
        self.bot_invite_link = 'https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3595328'
        self.support_server_link = 'https://discord.gg/mCqGhPJVcN'
        self.bot_repository_link = 'https://github.com/wheelercj/Parhelion'
        self.privacy_policy_link = 'https://github.com/wheelercj/Parhelion/blob/master/privacy_policy.md'

dev_settings = Dev_Settings()


async def send_traceback(ctx, error):
    etype = type(error)
    trace = error.__traceback__
    lines = traceback.format_exception(etype, error, trace)
    traceback_text = ''.join(lines)
    await ctx.send(f'```\n{traceback_text}\n```')


def remove_backticks(statement: str, languages=['py', 'python']) -> str:
    '''Removes language name and backticks around a code block, if they are there'''
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
    user = await bot.fetch_user(bot.owner_id)
    if use_embed:
        embed = discord.Embed(title=embed_title, description=message)
        await user.send(embed=embed)
    else:
        await user.send(message)


async def get_display_prefixes(bot, message: discord.Message) -> List[str]:
    '''Lists the prefixes as they appear in Discord
    
    The prefixes are sorted from shortest to longest.
    '''
    raw_prefixes: List[str] = bot.command_prefix(bot, message)
    if '' in raw_prefixes:
        raw_prefixes.remove('')

    # The unrendered mention pattern looks different in code
    # than when a user types it in Discord, so remove both
    # unrendered mention prefixes, and add one with the
    # "correct" appearance.
    display_prefixes = [f'@{bot.user.name} ']
    mention_regex = re.compile(rf'<@!?{bot.user.id}>')
    for prefix in raw_prefixes:
        if mention_regex.match(prefix) is None:
            display_prefixes.append(prefix)

    display_prefixes = sorted(display_prefixes, key=len)

    return display_prefixes


async def get_prefixes_str(bot, message: discord.Message, display_prefixes: list = None) -> str:
    '''Returns a string with all prefixes, comma separated
    
    The prefixes are sorted from shortest to longest.    
    '''
    if display_prefixes is None:
        display_prefixes = await get_display_prefixes(bot, message)
    prefixes = [f'`{x}`' for x in display_prefixes]
    return ', '.join(prefixes)


async def get_prefixes_message(bot, message: discord.Message, display_prefixes: list = None) -> str:
    '''Returns a message that explains the command prefixes
    
    The prefixes are sorted from shortest to longest.
    '''
    if display_prefixes is None:
        display_prefixes = await get_display_prefixes(bot, message)
    prefixes_str = await get_prefixes_str(bot, message, display_prefixes)
    if len(display_prefixes) > 1:
        return 'prefixes are ' + prefixes_str
    elif len(display_prefixes) == 1:
        return 'prefix is ' + prefixes_str
    else:
        raise ValueError


async def create_task_key(task_type: str = '', author_id: int = 0, target_time: str = '') -> str:
    '''Create a task key
    
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
