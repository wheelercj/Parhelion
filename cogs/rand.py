# External imports
import discord
from discord.ext import commands
import random
from datetime import datetime, timezone, timedelta
import asyncio
from aiohttp.client_exceptions import ContentTypeError

# Internal imports
from task import Daily_Quote
from tasks import save_task, delete_task, target_tomorrow
from common import dev_mail


async def save_daily_quote(ctx, target_time: str) -> Daily_Quote:
    """Saves one daily quote task to the database"""
    daily_quote = await save_task(ctx, 'daily_quote', target_time, '', Daily_Quote)
    return daily_quote


async def send_quote(destination, bot, daily_quote: Daily_Quote = None):
    """Send a random quote to destination
    
    destination can be ctx, a channel object, or a user object.
    If a daily_quote is received, its target time will be updated to
    the same time the following day.
    """
    params = {
        'lang': 'en',
        'method': 'getQuote',
        'format': 'json'
    }
    try:
        async with bot.session.get('http://api.forismatic.com/api/1.0/', params=params) as response:
            json_text = await response.json()
        quote, author = json_text['quoteText'], json_text['quoteAuthor']
        embed = discord.Embed(description=f'"{quote}"\n — {author}')
        await destination.send(embed=embed)
        if daily_quote is not None:
            await target_tomorrow(daily_quote)
    except ContentTypeError as error:
        print(f'forismatic {error = }')
        params = {
            'lang': 'en',
            'method': 'getQuote',
            'format': 'text/html'
        }
        async with bot.session.get('http://api.forismatic.com/api/1.0/', params=params) as response:
            text = await response.text()
        if 'Why do I have to complete a CAPTCHA?' in text:
            await dev_mail(bot, 'forismatic is requesting a CAPTCHA.')


class Random(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(aliases=['random'])
    async def rand(self, ctx, low: int = 1, high: int = 6):
        """Gives a random number (default bounds: 1 and 6)"""
        low = int(low)
        high = int(high)
        if  low <= high:
            await ctx.send(str(random.randint(low, high)))
        else:
            await ctx.send(str(random.randint(high, low)))


    @commands.command(name='flip-coin', aliases=['flip', 'coin-flip'])
    async def flip_coin(self, ctx):
        """Flips a coin"""
        n = random.randint(1, 2)
        if n == 1:
            await ctx.send('heads')
        else:
            await ctx.send('tails')


    async def begin_daily_quote(self, destination, target_time: str, daily_quote: Daily_Quote):
        def error_callback(running_task):
            # Tasks fail silently without this function.
            if running_task.exception():
                running_task.print_stack()
        
        running_task = asyncio.create_task(self.daily_quote_loop(destination, self.bot, target_time))
        running_task.add_done_callback(error_callback)


    async def daily_quote_loop(self, destination, bot, target_time: str, daily_quote: Daily_Quote):
        """Send a quote once a day at a specific time
        
        destination can be ctx, a channel object, or a user object.
        """
        while True:
            target_time = datetime.fromisoformat(target_time)
            now = datetime.now(timezone.utc)
            if now > target_time:
                date = now.date() + timedelta(days=1)
            else:
                date = now.date()
            target_time = datetime.combine(date, target_time.time())
            await discord.utils.sleep_until(target_time)
            await send_quote(destination, bot, daily_quote)


    @commands.command()
    async def quote(self, ctx, daily_utc_time: str = ''):
        """Shows a random famous quote
        
        If a UTC time is provided in HH:mm format, a quote will be
        sent each day at that time. You can use the time command
        to see the current UTC time. You can cancel daily quotes
        with `quote stop`.
        """
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
        today = datetime.now(timezone.utc)
        target_time = datetime(today.year, today.month, today.day, int(hour), int(minute), tzinfo=timezone.utc)
        target_time = target_time.isoformat()

        daily_quote = await save_daily_quote(ctx, target_time)

        await ctx.send(f'Time set! At {daily_utc_time} UTC each day, I will send you a random quote.')
        await self.begin_daily_quote(ctx, target_time, daily_quote)


    @commands.command()
    async def choose(self, ctx, choice_count: int, *choices: str):
        """Chooses randomly from multiple choices"""
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
