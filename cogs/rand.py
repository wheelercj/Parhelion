from replit import db
import discord
from discord.ext import commands
import random
from datetime import datetime, timezone, time, timedelta
import asyncio


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


    async def send_quote(self, ctx, bot):
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


    async def send_daily_quote(self, ctx, target_time):
        def error_callback(task):
            # Tasks fail silently without this function.
            if task.exception():
                task.print_stack()
        
        task = asyncio.create_task(self.subscription_loop(ctx, self.bot, target_time))
        task.add_done_callback(error_callback)


    async def subscription_loop(self, ctx, bot, target_time):
        while True:
            now = datetime.now(timezone.utc)
            date = now.date()
            if now.time() > target_time:
                date = now.date() + timedelta(days=1)
            target_datetime = datetime.combine(date, target_time)
            await discord.utils.sleep_until(target_datetime)
            await self.send_quote(ctx, bot)


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
            await self.send_quote(ctx, self.bot)
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
