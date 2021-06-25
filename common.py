import re
import traceback
import discord


class Dev_Settings:
    def __init__(self):
        self.dev_name = '(chris)#3047'
        self.bot_prefixes = [';', 'par ', 'Par ']
        self.bot_name = 'Parhelion'
        self.bot_full_name = f'{self.bot_name}#3922'
        self.bot_id = 836071320328077332
        self.bot_mention = f'<@!{self.bot_id}> '
        self.mention_regex = rf'<@!?\d{{len(str(self.bot_id))}}>'
        self.bot_invite_link = 'https://discordapp.com/api/oauth2/authorize?scope=bot&client_id=836071320328077332&permissions=3595328'
        self.bot_repository_link = 'https://replit.com/@wheelercj/simple-Discord-bot'

dev_settings = Dev_Settings()


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
    user = await bot.fetch_user(bot.owner_id)
    if use_embed:
        embed = discord.Embed(title=embed_title, description=message)
        await user.send(embed=embed)
    else:
        await user.send(message)


async def get_display_prefixes(bot) -> list:
    '''Lists the prefixes as they appear in Discord
    
    The prefixes are sorted from shortest to longest.
    '''
    raw_prefixes: list = bot.command_prefix(bot, '')

    # The unrendered mention pattern looks different here
    # than when a user types it in Discord, so remove both
    # unrendered mention prefixes, and add one with the
    # "correct" appearance.
    display_prefixes = [f'@{dev_settings.bot_name} ']
    for prefix in raw_prefixes:
        if re.match(rf'{dev_settings.mention_regex}', prefix) is None:
            display_prefixes.append(prefix)

    display_prefixes = sorted(display_prefixes, key=len)

    return display_prefixes


async def get_prefixes_str(bot) -> str:
    '''Returns a string with all prefixes, comma separated'''
    display_prefixes = await get_display_prefixes(bot)
    prefixes = [f'`{x}`' for x in display_prefixes]
    return ', '.join(prefixes)


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
