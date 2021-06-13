from replit import db
import discord
from discord.ext import commands
import random
from datetime import datetime, timezone, time, timedelta
import asyncio


async def sorted_daily_quote_keys():
    '''Return the sorted daily quote task keys'''
    # TODO: abstract this, move it to common.py, and reuse in cogs/reminders.py.
    q_keys = []
    for key in db.keys():
        if key.startswith('daily_quote'):
            q_keys.append(key)

    return sorted(q_keys, key=lambda x: x.split()[1])


async def send_quote(ctx, bot):
    params = {
        'lang':'en',
        'method':'getQuote',
        'format':'json'
    }
    async with bot.session.get('http://api.forismatic.com/api/1.0/', params=params) as response:
        json_text = await response.json()
    quote, author = json_text['quoteText'], json_text['quoteAuthor']
    embed = discord.Embed(description=f'"{quote}"\n — {author}')
    await ctx.send(embed=embed)


async def continue_daily_quote(bot, q_key):
    author_id = q_key.split()[1]
    destination = await bot.fetch_user(author_id)
    await send_quote(destination, bot)


async def continue_daily_quotes(bot):
    '''Continue daily quote tasks that were stopped by a server restart'''
    q_keys = await sorted_daily_quote_keys()
    print(f'q_keys: {q_keys}')
    for q_key in q_keys:
        await continue_daily_quote(bot, q_key)


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


    async def send_daily_quote(self, ctx, target_time):
        def error_callback(task):
            # Tasks fail silently without this function.
            if task.exception():
                task.print_stack()
        
        task = asyncio.create_task(self.subscription_loop(ctx, self.bot, target_time))
        task.add_done_callback(error_callback)


    async def subscription_loop(self, ctx, bot, target_time):
        while True:
            # TODO: should this really be a while loop? What if multiple people try to set up a daily quote?
            now = datetime.now(timezone.utc)
            date = now.date()
            if now.time() > target_time:
                date = now.date() + timedelta(days=1)
            target_datetime = datetime.combine(date, target_time)
            await discord.utils.sleep_until(target_datetime)
            await send_quote(ctx, bot)


    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def quote(self, ctx, daily_utc_time: str = ''):
        '''Shows a random famous quote
        
        If a UTC time is provided in HH:mm format, a quote will be
        sent each day at that time. You can use the time command
        to see the current UTC time. You can cancel a daily quote
        by using the command `quote stop`.
        '''
        if not len(daily_utc_time):
            await send_quote(ctx, self.bot)
        else:
            if daily_utc_time == 'stop':
                del db[f'daily_quote {ctx.author.id}']
                return

            hour, minute = daily_utc_time.split(':')
            target_time = time(hour=int(hour), minute=int(minute))
            db[f'daily_quote {ctx.author.id}'] = daily_utc_time
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
