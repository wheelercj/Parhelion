# External imports
import discord
from discord.ext import commands
import random
from datetime import datetime, timezone, time, timedelta
import logging
import asyncio

# Internal imports
from task import Daily_Quote
from tasks import save_task, delete_task


daily_quotes_logger = logging.getLogger('daily_quotes')
daily_quotes_logger.setLevel(logging.ERROR)
daily_quotes_handler = logging.FileHandler(filename='daily_quotes.log', encoding='utf-8')
daily_quotes_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(lineno)s: %(message)s'))
if not daily_quotes_logger.hasHandlers():
    daily_quotes_logger.addHandler(daily_quotes_handler)


async def save_daily_quote(ctx, target_time: str) -> Daily_Quote:
    '''Saves one daily quote task to the database'''
    daily_quote = await save_task(ctx, 'daily_quote', target_time, '', Daily_Quote)
    return daily_quote


async def send_quote(destination, bot):
    '''Send a random quote to destination
    
    destination can be ctx, a channel object, or a user object.
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
        '''Send a quote once a day at a specific time
        
        destination can be ctx, a channel object, or a user object.
        '''
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
            await delete_task(author_id=ctx.author.id)
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
