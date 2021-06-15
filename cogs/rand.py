# External imports
from replit import db
import discord
from discord.ext import commands
import random
from datetime import datetime, timezone, time, timedelta
import logging
import asyncio

# Internal imports
from task import Daily_Quote


daily_quotes_logger = logging.getLogger('daily_quotes')
daily_quotes_logger.setLevel(logging.ERROR)
daily_quotes_handler = logging.FileHandler(filename='daily_quotes.log', encoding='utf-8')
daily_quotes_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(lineno)s: %(message)s'))
if not daily_quotes_logger.hasHandlers():
    daily_quotes_logger.addHandler(daily_quotes_handler)


async def eval_daily_quote(string: str) -> Daily_Quote:
    '''Turns a daily quote task str into a Daily_Quote object'''
    if not string.startswith('Daily_Quote(') \
            or not string.endswith(')'):
        raise ValueError

    string = string[12:-1]
    args = string.split(', ')

    try:
        author_id = int(args[0])
        start_time: str = args[1][1:-1]
        target_time: str = args[2][1:-1]
        duration: str = args[3][1:-1]
        is_dm = bool(args[4][1:-1])
        guild_id = int(args[5])
        channel_id = int(args[6])

        daily_quote = Daily_Quote(author_id, start_time, target_time, duration, is_dm, guild_id, channel_id)

        if len(args) != 7:
            await delete_daily_quote(daily_quote.author_id)
            log_message = f'Incorrect number of args. Deleting {daily_quote}'
            daily_quotes_logger.log(logging.ERROR, log_message)
            raise ValueError(log_message)
        
        return daily_quote

    except IndexError as e:
        del db[f'task:daily_quote {author_id} {target_time}']
        log_message = f'Index error. Deleting {author_id} {target_time}. Error details: {e}'
        daily_quotes_logger.log(logging.ERROR, log_message)
        raise IndexError(log_message)


async def save_daily_quote(ctx, target_time: str) -> Daily_Quote:
    '''Saves one daily quote task to the database'''
    start_time = datetime.now(timezone.utc)
    target_time = target_time.isoformat()
    author_id = ctx.author.id
    try:
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        is_dm = False
    except AttributeError:
        is_dm = True
        guild_id = 0
        channel_id = 0

    daily_quote = Daily_Quote(author_id, start_time, target_time, '', is_dm, guild_id, channel_id)
    
    db[f'task:daily_quote {author_id} {target_time}'] = repr(daily_quote)
    return daily_quote


async def delete_daily_quote(author_id: int):
    q_keys = db.prefix(f'task:daily_quote {author_id}')
    del db[q_keys[0]]


async def send_quote(destination, bot):
    '''Send a random quote to destination
    
    destination can be ctx.
    '''
    params = {
        'lang':'en',
        'method':'getQuote',
        'format':'json'
    }
    async with bot.session.get('http://api.forismatic.com/api/1.0/', params=params) as response:
        json_text = await response.json()
    quote, author = json_text['quoteText'], json_text['quoteAuthor']
    embed = discord.Embed(description=f'"{quote}"\n — {author}')
    await destination.send(embed=embed)


async def continue_daily_quote(bot, q_key):
    daily_quote = eval_daily_quote(db[q_key])
    destination = daily_quote.get_destination(bot)
    await send_quote(destination, bot)


class Random(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['random'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def rand(self, ctx, low: int = 1, high: int = 6):
        '''Gives a random number (default bounds: 1 and 6)'''
        low = int(low)
        high = int(high)
        if  low <= high:
            await ctx.send(str(random.randint(low, high)))
        else:
            await ctx.send(str(random.randint(high, low)))


    @commands.command(name='flip-coin', aliases=['flip', 'coin-flip'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def flip_coin(self, ctx):
        '''Flips a coin'''
        n = random.randint(1, 2)
        if n == 1:
            await ctx.send('heads')
        else:
            await ctx.send('tails')


    async def send_daily_quote(self, destination, target_time):
        def error_callback(task):
            # Tasks fail silently without this function.
            if task.exception():
                task.print_stack()
        
        task = asyncio.create_task(self.subscription_loop(destination, self.bot, target_time))
        task.add_done_callback(error_callback)


    async def subscription_loop(self, destination, bot, target_time):
        '''destination can be ctx'''
        while True:
            # TODO: should this really be a while loop? What if multiple people try to set up a daily quote?
            now = datetime.now(timezone.utc)
            date = now.date()
            if now.time() > target_time:
                date = now.date() + timedelta(days=1)
            target_datetime = datetime.combine(date, target_time)
            await discord.utils.sleep_until(target_datetime)
            await send_quote(destination, bot)


    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def quote(self, ctx, daily_utc_time: str = ''):
        '''Shows a random famous quote
        
        If a UTC time is provided in HH:mm format, a quote will be
        sent each day at that time. You can use the time command
        to see the current UTC time. You can cancel daily quotes
        with `quote stop`.
        '''
        if not len(daily_utc_time):
            await send_quote(ctx, self.bot)
            return

        # Allow only one daily quote task per user.
        try:
            await delete_daily_quote(ctx.author.id)
        except:
            pass
        
        if daily_utc_time == 'stop':
            return

        hour, minute = daily_utc_time.split(':')
        target_time = time(hour=int(hour), minute=int(minute))

        await save_daily_quote(ctx, target_time)
        await ctx.send(f'Time set! At {daily_utc_time} UTC each day, I will send you a random quote.')

        await self.send_daily_quote(ctx, target_time)


    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def choose(self, ctx, choice_count: int, *choices: str):
        '''Chooses randomly from multiple choices'''
        choices_made = []
        for _ in range(0, choice_count):
            choices_made.append(random.choice(choices))
        await ctx.send(''.join(choices_made))


    @choose.error
    async def choose_error(self, ctx, error):
        if isinstance(error, commands.errors.BadArgument) \
        or isinstance(error, commands.errors.CommandInvokeError) \
        or isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.send(f'Error: the first argument must be the number of choices you want to be made. Following arguments must be the choices to choose from.')
        else:
            await ctx.send(error)


def setup(bot):
    bot.add_cog(Random(bot))
